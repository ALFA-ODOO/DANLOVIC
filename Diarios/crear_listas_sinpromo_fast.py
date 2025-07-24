# -*- coding: utf-8 -*-
"""Version optimizada de crear_listas_sinpromo.py.

Esta version evita realizar consultas repetidas a la base de datos
para obtener la moneda de cada articulo y precarga los productos desde
Odoo para minimizar llamadas via XML-RPC.
"""

import pyodbc
import xmlrpc.client
import pandas as pd
import datetime
from collections import defaultdict

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


# Obtener tasas de conversión solo una vez
cursor.execute("SELECT TOP 1 MONEDA2, MONEDA3, MONEDA4, MONEDA5 FROM TA_COTIZACION ORDER BY ID DESC")
tasas = cursor.fetchone()
tasas_conversion = {"2": float(tasas[0] or 1), "3": float(tasas[1] or 1), "4": float(tasas[2] or 1), "5": float(tasas[3] or 1)}

print("\n💰 Importando listas de precios...")
# Cargar los precios desde SQL
cursor.execute("SELECT IdArticulo, Nombre, Precio4 FROM V_MA_Precios WHERE TipoLista = 'V'")
cols = [col[0] for col in cursor.description]
precios_sql = [dict(zip(cols, map(limpiar, row))) for row in cursor.fetchall()]
precios_sql = precios_sql[1335:]

# Obtener moneda de todos los articulos en un solo paso
a_monedas = {}
cursor.execute("SELECT LTRIM(RTRIM(IDARTICULO)) AS IdArticulo, Moneda FROM v_ma_articulos")
for art, mon in cursor.fetchall():
    a_monedas[limpiar(art)] = limpiar(mon) or "1"

# Obtener ids de productos en Odoo de forma masiva
codigos = list({p['IdArticulo'].strip() for p in precios_sql})
product_map = {}
chunk_size = 80
for i in range(0, len(codigos), chunk_size):
    chunk = codigos[i:i + chunk_size]
    productos = models.execute_kw(
        db,
        uid,
        password,
        "product.product",
        "search_read",
        [[['default_code', 'in', chunk]]],
        {"fields": ["id", "product_tmpl_id", "active", "default_code"]},
    )
    for prod in productos:
        product_map[prod["default_code"].strip()] = {
            "variant_id": prod["id"],
            "template_id": prod["product_tmpl_id"][0],
            "active": prod["active"],
        }

nombres_listas_sql = set(precio['Nombre'] for precio in precios_sql)

errores_precios = []

def procesar_lista(nombre_lista_sql):
    nombre_lista_odoo = nombre_lista_sql
    lista_principal = models.execute_kw(db, uid, password, "product.pricelist", "search_read", [[['name', '=', nombre_lista_odoo]]], {"fields": ["id"], "limit": 1})
    if not lista_principal:
        lista_principal_id = models.execute_kw(db, uid, password, "product.pricelist", "create", [{"name": nombre_lista_odoo, "currency_id": 19}])
        print(f"\n✨ Creada lista de precios en Odoo: {nombre_lista_odoo} (ID: {lista_principal_id})")
    else:
        lista_principal_id = lista_principal[0]["id"]
        existing_rules = models.execute_kw(db, uid, password, "product.pricelist.item", "search", [[('pricelist_id', '=', lista_principal_id)]])
        if existing_rules:
            models.execute_kw(db, uid, password, "product.pricelist.item", "unlink", [existing_rules])
            print(f"🗑️ Borradas {len(existing_rules)} reglas existentes para la lista de precios: {nombre_lista_odoo} (ID: {lista_principal_id})")

    precios_lista = [p for p in precios_sql if p['Nombre'] == nombre_lista_sql]
    reglas = []
    templates_publicar = []

    for data in precios_lista:
        codigo = data.get("IdArticulo").strip()
        prod = product_map.get(codigo)
        if not prod:
            registrar_error(errores_precios, IdArticulo=codigo, NombreLista=nombre_lista_sql, Motivo="Producto no encontrado en Odoo")
            continue

        precio4 = float(data.get("Precio4") or 0)
        moneda_articulo = a_monedas.get(codigo, "1")
        if moneda_articulo != "1" and moneda_articulo in tasas_conversion:
            precio4 *= tasas_conversion[moneda_articulo]

        if precio4 > 0:
            reglas.append({
                "pricelist_id": lista_principal_id,
                "applied_on": "0_product_variant",
                "product_id": prod["variant_id"],
                "compute_price": "fixed",
                "fixed_price": round(precio4, 2),
            })

        if prod["active"]:
            templates_publicar.append(prod["template_id"])

    # Crear reglas en lotes para reducir llamadas
    for i in range(0, len(reglas), chunk_size):
        batch = reglas[i:i + chunk_size]
        models.execute_kw(db, uid, password, "product.pricelist.item", "create", [batch])

    if templates_publicar:
        models.execute_kw(db, uid, password, "product.template", "write", [list(set(templates_publicar)), {"website_published": True}])

    models.execute_kw(db, uid, password, "product.pricelist.item", "create", [{
        "pricelist_id": lista_principal_id,
        # Use a global rule so no specific product is required
        "applied_on": "3_global",
        "min_quantity": 0,
        "compute_price": "fixed",
        "fixed_price": 0.0,
        "name": "PRECIO CERO",
    }])
    print(f"\n➕ Agregada regla de precio 0 para todos los productos en lista: {nombre_lista_odoo} (ID: {lista_principal_id})")


for nombre_lista_sql in nombres_listas_sql:
    procesar_lista(nombre_lista_sql)

cursor.close()
sql_conn.close()

if errores_precios:
    pd.DataFrame(errores_precios).to_csv("errores_carga_listas_precios.csv", index=False)
    print("\n⚠️ Archivo de errores guardado como errores_carga_listas_precios.csv")

fin_proceso = datetime.datetime.now()
duracion = fin_proceso - inicio_proceso
print(f"\n🎯 Carga de listas de precios finalizada. Tiempo total: {duracion}")
