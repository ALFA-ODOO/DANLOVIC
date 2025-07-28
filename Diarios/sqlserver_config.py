import os

# SQL Server connection settings
sql_server = {
    "server": os.getenv("SQL_SERVER", "WIN-TUNPH1OHJM9\\ALFANET"),
    "database": os.getenv("SQL_DATABASE", "DISTRIWALTERP"),
    "user": os.getenv("SQL_USER"),
    "password": os.getenv("SQL_PASSWORD"),
    "driver": os.getenv("SQL_DRIVER", "SQL Server Native Client 10.0"),
}

if sql_server["user"] is None or sql_server["password"] is None:
    raise EnvironmentError("SQL_USER and SQL_PASSWORD must be set in the environment")
