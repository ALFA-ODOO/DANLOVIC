# -*- coding: utf-8 -*-
"""Comparar productos y precios entre Odoo y Alfa Gestión.

Genera un archivo Excel con:
- Productos faltantes en Odoo
- Precios diferentes
- Productos que están en Odoo pero no en Alfa
"""

import pyodbc
import xmlrpc.client
import pandas as pd

from odoo_config import url, db, username, password
from sqlserver_config import sql_server

# --- Conexión a Odoo ---
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# --- Conexión a SQL Server ---
sql_conn = pyodbc.connect(
    f"DRIVER={sql_server['driver']};"
    f"SERVER={sql_server['server']};"
    f"DATABASE={sql_server['database']};"
    f"UID={sql_server['user']};"
    f"PWD={sql_server['password']}"
)
cursor = sql_conn.cursor()


def limpiar(valor):
    """Quitar espacios y decimales innecesarios."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto

# --- Datos desde Alfa Gestión ---
cursor.execute("SELECT IdArticulo, Nombre, Precio4 FROM V_MA_Precios WHERE TipoLista = 'V'")
cols = [col[0] for col in cursor.description]
precios_sql = [dict(zip(cols, row)) for row in cursor.fetchall()]

precios_map = {
    (limpiar(p['IdArticulo']), limpiar(p['Nombre'])): float(p['Precio4'] or 0)
    for p in precios_sql
}

codigos = list({codigo for codigo, _ in precios_map.keys()})
product_map = {}
chunk_size = 80
for i in range(0, len(codigos), chunk_size):
    chunk = codigos[i:i + chunk_size]
    productos = models.execute_kw(
        db,
        uid,
        password,
        'product.product',
        'search_read',
        [[['default_code', 'in', chunk]]],
        {'fields': ['id', 'default_code']}
    )
    for prod in productos:
        product_map[prod['default_code'].strip()] = prod['id']

nombres_listas = {nombre for _, nombre in precios_map.keys()}
odoo_pricelist_map = {}
for nombre in nombres_listas:
    lista = models.execute_kw(
        db, uid, password,
        'product.pricelist', 'search_read',
        [[['name', '=', nombre]]],
        {'fields': ['id'], 'limit': 1}
    )
    if lista:
        odoo_pricelist_map[nombre] = lista[0]['id']

odoo_price_map = {}
for nombre, lista_id in odoo_pricelist_map.items():
    items = models.execute_kw(
        db, uid, password,
        'product.pricelist.item', 'search_read',
        [[['pricelist_id', '=', lista_id], ['applied_on', '=', '0_product_variant']]],
        {'fields': ['product_id', 'fixed_price']}
    )
    product_ids = [item['product_id'][0] for item in items if item.get('product_id')]
    if product_ids:
        prods = models.execute_kw(
            db, uid, password,
            'product.product', 'read',
            [product_ids],
            {'fields': ['default_code']}
        )
        code_map = {p['id']: p['default_code'].strip() for p in prods}
    else:
        code_map = {}
    for item in items:
        pid = item.get('product_id')
        if not pid:
            continue
        code = code_map.get(pid[0])
        if code:
            odoo_price_map[(code, nombre)] = float(item.get('fixed_price') or 0)

faltantes_odoo = []
precios_diferentes = []
solo_odoo = []

for key, precio_alfa in precios_map.items():
    codigo, nombre = key
    if codigo not in product_map:
        faltantes_odoo.append({'IdArticulo': codigo, 'Nombre': nombre, 'Precio_Alfa': precio_alfa})
        continue
    precio_odoo = odoo_price_map.get(key)
    if precio_odoo is None:
        faltantes_odoo.append({'IdArticulo': codigo, 'Nombre': nombre, 'Precio_Alfa': precio_alfa})
    elif round(precio_odoo, 2) != round(precio_alfa, 2):
        precios_diferentes.append({
            'IdArticulo': codigo,
            'Nombre': nombre,
            'Precio_Alfa': precio_alfa,
            'Precio_Odoo': precio_odoo
        })

for key, precio_odoo in odoo_price_map.items():
    if key not in precios_map:
        codigo, nombre = key
        solo_odoo.append({'IdArticulo': codigo, 'Nombre': nombre, 'Precio_Odoo': precio_odoo})

with pd.ExcelWriter('comparacion_precios.xlsx') as writer:
    pd.DataFrame(faltantes_odoo).to_excel(writer, sheet_name='Faltantes_Odoo', index=False)
    pd.DataFrame(precios_diferentes).to_excel(writer, sheet_name='Precios_Diferentes', index=False)
    pd.DataFrame(solo_odoo).to_excel(writer, sheet_name='Solo_Odoo', index=False)

cursor.close()
sql_conn.close()
print("Excel 'comparacion_precios.xlsx' generado.")
