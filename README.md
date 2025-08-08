# DANLOVIC
Migracion Alfa Odoo

This repository contains the Python utilities used to synchronize data
between an **Alfa Gestión** SQL Server database and the company's Odoo
instance.  The scripts automate daily tasks such as updating products,
prices, stock levels and clients as well as transferring orders from
Odoo back to Alfa.

## Requirements

- Python 3.9 or newer
- `pandas`
- `pyodbc` (plus the SQL Server ODBC driver)
- `tkinter` for the GUI (usually included with standard Python builds)

## Configuration

Connection credentials are no longer stored in the repository. The scripts read them from environment variables:

- `ODOO_USERNAME` and `ODOO_PASSWORD` for the Odoo API.
- `SQL_USER` and `SQL_PASSWORD` for the SQL Server database.

Optional variables can override default connection details:

- `ODOO_URL` (default ``)
- `ODOO_DB` (default ``)
- `SQL_SERVER` (default ``)
- `SQL_DATABASE` (default ``)
- `SQL_DRIVER` (default `SQL Server Native Client 10.0`)

## Usage

Install the required packages and set the environment variables shown
above.  Then run the GUI launcher:

```bash
pip install pandas pyodbc
python "Odoo Danlovic.py"
```

The window provides buttons to execute each daily task such as
updating products, prices, stock, images and customers or syncing
orders from Odoo.  Each script under the `Diarios/` folder can also be
executed directly with `python` if command‑line usage is preferred.
