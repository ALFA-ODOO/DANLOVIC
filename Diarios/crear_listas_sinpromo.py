# -*- coding: utf-8 -*-
import pyodbc
import xmlrpc.client
import pandas as pd
import datetime

from odoo_config import url, db, username, password
from sqlserver_config import sql_server

inicio_proceso = datetime.datetime.now()
print(f"\n✨ Inicio de la carga de listas de precios: {inicio_proceso.strftime('%Y-%m-%d %H:%M:%S')}")

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

sql_conn = pyodbc.connect(
    f"DRIVER={{SQL Server Native Client 10.0}};"
    f"SERVER={sql_server['server']};"
    f"DATABASE={sql_server['database']};"
    f"UID={sql_server['user']};"
    f"PWD={sql_server['password']}"
)
cursor = sql_conn.cursor()

def limpiar(valor):
    if pd.isna(valor) or valor is None:
        return ""
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto

def registrar_error(lista, **kwargs):
    lista.append(kwargs)

cursor.execute("SELECT TOP 1 MONEDA2, MONEDA3, MONEDA4, MONEDA5 FROM TA_COTIZACION ORDER BY ID DESC")
tasas = cursor.fetchone()
tasas_conversion = {"2": float(tasas[0] or 1), "3": float(tasas[1] or 1), "4": float(tasas[2] or 1), "5": float(tasas[3] or 1)}

print("\n💰 Importando listas de precios...")
cursor.execute("SELECT * FROM V_MA_Precios WHERE TipoLista = 'V'")
cols = [col[0] for col in cursor.description]
precios_sql = [dict(zip(cols, map(limpiar, row))) for row in cursor.fetchall()]
# Solo procesar desde el registro 1030 en adelante
precios_sql = precios_sql[1335:]  # índice 1029 porque empieza desde 0


# Obtener todos los nombres de lista únicos del SQL
nombres_listas_sql = set(precio['Nombre'] for precio in precios_sql)
total_registros_precios = len(precios_sql)
contador_registros_precios = 0
errores_precios = []

for nombre_lista_sql in nombres_listas_sql:
    nombre_lista_odoo = nombre_lista_sql
    lista_creada = False

    # Crear o buscar la lista de precios principal
    lista_principal = models.execute_kw(db, uid, password, "product.pricelist", "search_read", [[['name', '=', nombre_lista_odoo]]], {"fields": ["id"], "limit": 1})
    if not lista_principal:
        lista_principal_id = models.execute_kw(db, uid, password, "product.pricelist", "create", [{"name": nombre_lista_odoo, "currency_id": 19}])
        print(f"\n✨ Creada lista de precios en Odoo: {nombre_lista_odoo} (ID: {lista_principal_id})")
        lista_creada = True
    else:
        lista_principal_id = lista_principal[0]["id"]

        # Borrar todas las reglas existentes para esta lista de precios
        existing_rules_ids = models.execute_kw(db, uid, password, "product.pricelist.item", "search_read", [[('pricelist_id', '=', lista_principal_id)]], {"fields": ["id"]})
        if existing_rules_ids:
            rule_ids_to_delete = [rule['id'] for rule in existing_rules_ids]
            models.execute_kw(db, uid, password, "product.pricelist.item", "unlink", [rule_ids_to_delete])
            print(f"🗑️ Borradas {len(rule_ids_to_delete)} reglas existentes para la lista de precios: {nombre_lista_odoo} (ID: {lista_principal_id})")

    # Filtrar los precios de la lista actual
    precios_lista_actual = [p for p in precios_sql if p['Nombre'] == nombre_lista_sql]

    for data in precios_lista_actual:
        idart_precio = data.get("IdArticulo")

        # Buscar el product.product en Odoo por default_code
        producto_ids = models.execute_kw(db, uid, password, "product.product", "search_read", [[['default_code', '=', idart_precio.strip()]]], {"fields": ["id", "product_tmpl_id"], "limit": 1})

        if not producto_ids:
            registrar_error(errores_precios, IdArticulo=idart_precio, NombreLista=nombre_lista_sql, Motivo=f"Producto no encontrado en Odoo con default_code: '{idart_precio}'")
            continue

        producto = producto_ids[0]
        producto_variant_id = producto["id"]
        producto_template_id = producto["product_tmpl_id"][0]

        # Obtener la moneda del artículo desde SQL Server
        cursor.execute("SELECT Moneda FROM v_ma_articulos WHERE LTRIM(RTRIM(IDARTICULO)) = ?", idart_precio.strip())
        articulo_data = cursor.fetchone()
        moneda_articulo = limpiar(articulo_data[0]) if articulo_data else "1" # Default a pesos si no se encuentra

        contador_registros_precios += 1
        print(f"{contador_registros_precios}/{total_registros_precios} - Producto {idart_precio} (Odoo Variant ID: {producto_variant_id}, Template ID: {producto_template_id}) en lista {nombre_lista_odoo}", end="")

        try:
            precio4 = float(data.get("Precio4") or 0)
            if moneda_articulo != "1" and moneda_articulo in tasas_conversion:
                precio4 *= tasas_conversion[moneda_articulo]

            if precio4 > 0:
                # Buscar si ya existe una regla para este producto en esta lista de precios
                existing_rule = models.execute_kw(db, uid, password, "product.pricelist.item", "search_read", [[
                    ('pricelist_id', '=', lista_principal_id),
                    ('applied_on', '=', '0_product_variant'),
                    ('product_id', '=', producto_variant_id)
                ]], {"fields": ["id"], "limit": 1})

                if existing_rule:
                    # Si existe una regla, actualizarla
                    rule_id = existing_rule[0]["id"]
                    models.execute_kw(db, uid, password, "product.pricelist.item", "write", [[rule_id], {
                        "fixed_price": round(precio4, 2)
                    }])
                    print(f" -> Precio fijo actualizado: {round(precio4, 2)} (Regla ID: {rule_id})")
                else:
                    # Si no existe, crear una nueva regla
                    models.execute_kw(db, uid, password, "product.pricelist.item", "create", [{
                        "pricelist_id": lista_principal_id,
                        "applied_on": "3_global",  # Aplica globalmente a todos los productos
                        "min_quantity": 0,
                        "compute_price": "fixed",
                        "fixed_price": 0.0,
                        "name": "PRECIO CERO"
                    }])
                    print(f" -> Precio fijo insertado: {round(precio4, 2)}")
            else:
                print(" -> Precio 4 es cero o negativo, no se insertó/actualizó precio.")

            prod_data = models.execute_kw(db, uid, password, "product.template", "read", [[producto_template_id]], {"fields": ["active"]})
            if prod_data and prod_data[0]["active"]:
                models.execute_kw(db, uid, password, "product.template", "write", [[producto_template_id], {"website_published": True}])

        except Exception as e:
            print(f" -> Error al insertar/actualizar precio: {e}")
            registrar_error(errores_precios, IdArticulo=idart_precio, NombreLista=nombre_lista_odoo, Motivo=str(e))

    # Agregar una regla al final para todos los productos con precio 0 y cantidad 0
    try:
        models.execute_kw(db, uid, password, "product.pricelist.item", "create", [{
            "pricelist_id": lista_principal_id,
            "applied_on": "1_product",  # Aplica a todos los productos
            "min_quantity": 0,
            "compute_price": "fixed",
            "fixed_price": 0.0,
            "name": "PRECIO CERO" # Puedes darle un nombre descriptivo a la regla
        }])
        print(f"\n➕ Agregada regla de precio 0 para todos los productos en lista: {nombre_lista_odoo} (ID: {lista_principal_id})")
    except Exception as e:
        print(f"\n⚠️ Error al agregar la regla de precio 0: {e}")
        registrar_error(errores_precios, NombreLista=nombre_lista_odoo, Motivo=f"Error al crear regla de precio 0: {e}")

# === Cierre de la conexión FUERA del bucle ===
cursor.close()
sql_conn.close()

if errores_precios:
    pd.DataFrame(errores_precios).to_csv("errores_carga_listas_precios.csv", index=False)
    print("\n⚠️ Archivo de errores guardado como errores_carga_listas_precios.csv")

fin_proceso = datetime.datetime.now()
duracion = fin_proceso - inicio_proceso
print(f"\n🎯 Carga de listas de precios finalizada. Tiempo total: {duracion}")