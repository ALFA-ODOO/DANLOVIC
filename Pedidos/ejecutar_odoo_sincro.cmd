@echo off
set FECHA=%DATE:/=-%
set HORA=%TIME::=-%
set LOGFILE=C:\TAREAS_ALFA\el_trebol\odoo\logs\log_odoo_%FECHA%_%HORA%.txt

echo [%DATE% %TIME%] Iniciando sincronización desde Odoo... > "%LOGFILE%"
"C:\Users\Alejandro\AppData\Local\Programs\Python\Python39-32\python.exe" "C:\ODOO\Pedidos\odoo_sincro_pedidos_v2.py" >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Finalizó sincronización. >> "%LOGFILE%"
exit /b 0