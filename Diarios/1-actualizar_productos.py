# -*- coding: utf-8 -*-
import pyodbc
import xmlrpc.client
import base64
import os
import pandas as pd
import datetime

from odoo_config import url, db, username, password
from sqlserver_config import sql_server

inicio_proceso = datetime.datetime.now()
print(f"Inicio de la carga de artículos (con categorías): {inicio_proceso.strftime('%Y-%m-%d %H:%M:%S')}")

MAP_UNIDADES = {"UN": 1, "KG": 15, "GR": 111, "LT": 12, "M": 8, "CM": 7, "MM": 6, "PA": 117, "CA": 116, "BL": 107, "CJ": 116, "PZ": 1}
carpeta_imagenes = r"C:\\Alfa Gestion\\Imagenes\\ImagenesWeb"

# --- Conexión Odoo ---
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# Obtener categorías existentes una vez
categorias_odoo = models.execute_kw(
    db, uid, password,
    'product.category', 'search_read',
    [[]],
    {'fields': ['id', 'name'], 'limit': 0}
)
map_categorias = {c['name'].strip().lower(): c['id'] for c in categorias_odoo}

# Obtener productos existentes una vez para acelerar la búsqueda
productos_existentes = models.execute_kw(
    db, uid, password,
    'product.template', 'search_read',
    [[]],
    {'fields': ['id', 'default_code'], 'limit': 0, 'context': {'active_test': False}}
)
map_productos = {p['default_code'].strip(): p['id'] for p in productos_existentes if p.get('default_code')}

# --- Conexión SQL Server ---
sql_conn = pyodbc.connect(
    f"DRIVER={sql_server['driver']};"
    f"SERVER={sql_server['server']};"
    f"DATABASE={sql_server['database']};"
    f"UID={sql_server['user']};"
    f"PWD={sql_server['password']}"
)
cursor = sql_conn.cursor()

cursor.execute("SELECT TOP 1 MONEDA2, MONEDA3, MONEDA4, MONEDA5 FROM TA_COTIZACION ORDER BY ID DESC")
tasas = cursor.fetchone()
tasas_conversion = {"2": float(tasas[0] or 1), "3": float(tasas[1] or 1), "4": float(tasas[2] or 1), "5": float(tasas[3] or 1)}

# --- Consulta de productos ---
cursor.execute("""
    SELECT
        a.IDARTICULO,
        a.DESCRIPCION,
        a.IDUNIDAD,
        LTRIM(RTRIM(a.CODIGOBARRA)) AS CODIGOBARRA,
        a.TasaIva,
        a.Moneda,
        a.PRECIO1,
        a.COSTO,
        a.SUSPENDIDO,
        a.SUSPENDIDOC,
        a.SUSPENDIDOV,
        a.RutaImagen,
        a.DescRubro,
        a.DescMarca
    FROM vt_ma_articulos a
    ORDER BY IdArticulo
""")
# a.SUSPENDIDOC = 1 es Suspendido para las compras si esta en 0 esta habilitado para compras
# a.SUSPENDIDOV = 1 es Suspendido para las Ventas si esta en 0 esta habilitado para Ventas
# a.SUSPENDIDO = 1 es Suspendido para las compras y ventas, esta de baja

productos_raw = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
print(f"Total productos a procesar: {len(productos_raw)}")

productos_actualizados = 0
productos_creados = 0
errores_productos = []

# Batch creation accumulators
BATCH_SIZE = 50
batch_vals = []
batch_info = []  # store (default_code, name) for logging and mapping

for producto in productos_raw:
    default_code = producto.get("IDARTICULO", "").strip()
    if not default_code:
        continue
    name = producto.get("DESCRIPCION")
    tasaIva = producto.get("TasaIVA")
    unidad_id = MAP_UNIDADES.get(producto.get("IDUNIDAD"), MAP_UNIDADES.get("UN"))
    precio = float(producto.get("PRECIO1") or 0)
    costo = float(producto.get("COSTO") or 0)
    activo = producto.get("SUSPENDIDO") != "1"
    venta_habilitada = producto.get("SUSPENDIDOV") != "1"
    compra_habilitada = producto.get("SUSPENDIDOC") != "1"
    barcode = (producto.get("CODIGOBARRA") or "").strip()
    marca = producto.get("DescMarca") or producto.get("Marca")
    categoria_desc = (producto.get("DescRubro") or "").strip()
    ruta_imagen = os.path.join(carpeta_imagenes, f"{default_code}.jpg")

    categoria_id = None
    if categoria_desc:
        key = categoria_desc.lower()
        categoria_id = map_categorias.get(key)
        if not categoria_id:
            categoria_id = models.execute_kw(db, uid, password, 'product.category', 'create', [{'name': categoria_desc}])
            map_categorias[key] = categoria_id

    producto_vals = {
        "name": name,
        "default_code": default_code,
        "uom_id": unidad_id,
        "standard_price": round(costo, 2),
        "list_price": round(precio, 2),
        "active": activo,
        "sale_ok": venta_habilitada,
        "purchase_ok": compra_habilitada,
    }

    if categoria_id:
        producto_vals["categ_id"] = categoria_id
    if barcode:
        producto_vals["barcode"] = barcode
    if marca:
        producto_vals["x_marca"] = marca

    if os.path.exists(ruta_imagen):
        with open(ruta_imagen, "rb") as img_file:
            producto_vals["image_1920"] = base64.b64encode(img_file.read()).decode("utf-8")

    try:
        producto_id = map_productos.get(default_code)
        if producto_id:
            models.execute_kw(db, uid, password, "product.template", "write", [[producto_id], producto_vals])
            productos_actualizados += 1
            print(f" Actualizado (ID: {producto_id}) - {name}")
        else:
            batch_vals.append(producto_vals)
            batch_info.append((default_code, name))
            if len(batch_vals) >= BATCH_SIZE:
                ids_creados = models.execute_kw(db, uid, password, "product.template", "create", batch_vals)
                for (codigo, nombre), pid in zip(batch_info, ids_creados):
                    map_productos[codigo] = pid
                    productos_creados += 1
                    print(f" Creado (ID: {pid}) - {nombre}")
                batch_vals.clear()
                batch_info.clear()

    except Exception as e:
        errores_productos.append({"IDARTICULO": default_code, "Descripcion": name, "Error": str(e)})
        print(f" Error procesando {default_code}: {e}")

# Enviar cualquier producto pendiente de creación
if batch_vals:
    try:
        ids_creados = models.execute_kw(db, uid, password, "product.template", "create", batch_vals)
        for (codigo, nombre), pid in zip(batch_info, ids_creados):
            map_productos[codigo] = pid
            productos_creados += 1
            print(f" Creado (ID: {pid}) - {nombre}")
    except Exception as e:
        for codigo, nombre in batch_info:
            errores_productos.append({"IDARTICULO": codigo, "Descripcion": nombre, "Error": str(e)})
        print(f" Error procesando lote final: {e}")

cursor.close()
sql_conn.close()

print(f"Resumen de la carga:")
print(f"  - Productos actualizados: {productos_actualizados}")
print(f"  - Productos creados: {productos_creados}")

if errores_productos:
    pd.DataFrame(errores_productos).to_csv("errores_actualizacion_productos.csv", index=False)
    print("Archivo de errores guardado como errores_actualizacion_productos.csv")

fin_proceso = datetime.datetime.now()
duracion = fin_proceso - inicio_proceso
print(f"Actualización de artículos finalizada. Tiempo total: {duracion}")
