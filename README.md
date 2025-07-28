# DANLOVIC
Migracion Alfa Odoo

## Configuration

Connection credentials are no longer stored in the repository. The scripts read them from environment variables:

- `ODOO_USERNAME` and `ODOO_PASSWORD` for the Odoo API.
- `SQL_USER` and `SQL_PASSWORD` for the SQL Server database.

Optional variables can override default connection details:

- `ODOO_URL` (default `https://danlovic.odoo.com`)
- `ODOO_DB` (default `danlovic`)
- `SQL_SERVER` (default `WIN-TUNPH1OHJM9\ALFANET`)
- `SQL_DATABASE` (default `DISTRIWALTERP`)
- `SQL_DRIVER` (default `SQL Server Native Client 10.0`)
