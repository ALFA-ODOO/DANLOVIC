# --- interfaz_principal.py (raíz) ---

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os

def mostrar_mensaje(mensaje):
    mensaje_label.config(text=mensaje)

def ejecutar_comando_con_consola(comando, mensaje):
    ruta_completa = comando[0]
    print(f">>> Ejecutando: {ruta_completa}")  # ✅ Agregado para depurar

    try:
        subprocess.Popen(comando)
        mostrar_mensaje(f"Ejecutando: {mensaje}")
    except FileNotFoundError:
        mostrar_mensaje(f"Error: No se encontró el archivo: {ruta_completa}")
    except Exception as e:
        mostrar_mensaje(f"Error al ejecutar {mensaje}: {e}")

def ejecutar_actualizar_productos():
    ruta_exe = os.path.join("Diarios", "actualizar_productos_noarchivados.exe")
    ejecutar_comando_con_consola([ruta_exe], "Actualizar Productos")

def ejecutar_actualizar_precios():
    ruta_exe = os.path.join("Diarios", "actualizar_reglas_precio.exe")
    ejecutar_comando_con_consola([ruta_exe], "Actualizar Precios")

def ejecutar_actualizar_imagenes():
    ruta_exe = os.path.join("Diarios", "actualizar_imagenes_2.exe")
    ejecutar_comando_con_consola([ruta_exe], "Actualizar Imágenes")

def ejecutar_sincronizar_pedidos():
    ruta_exe = os.path.join("Diarios", "sincronizar_pedidos.exe")
    ejecutar_comando_con_consola([ruta_exe], "Sincronizar Pedidos")

def ejecutar_desactivar_suspendidos():
    ruta_exe = os.path.join("Diarios", "desactivar_suspendidos.exe")
    ejecutar_comando_con_consola([ruta_exe], "Desactivar suspendidos")

def ejecutar_actualizar_stock():
    ruta_exe = os.path.join("Diarios", "actualizar_stock.exe")
    ejecutar_comando_con_consola([ruta_exe], "Actualizar stock")

def abrir_ventana_clientes():
    ventana_clientes = tk.Toplevel(ventana)
    ventana_clientes.title("Actualizar Clientes")
    ventana_clientes.geometry("500x400")

    tk.Label(ventana_clientes, text="Actualizar Clientes", font=("Helvetica", 14)).pack(pady=10)

    def ejecutar_todos():
        ruta_exe = os.path.join("Diarios", "actualizar_clientes.exe")
        try:
            subprocess.Popen([ruta_exe])
            messagebox.showinfo("Actualizando", "Se está ejecutando la actualización completa.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Button(
        ventana_clientes,
        text="Actualizar TODOS los clientes",
        command=ejecutar_todos,
        # bg="green",
        # fg="white"
    ).pack(pady=10)

    tk.Label(
        ventana_clientes,
        text="Códigos de cliente (uno por línea o separados por coma):"
    ).pack()

    entrada_codigos = tk.Text(ventana_clientes, height=5, width=50)
    entrada_codigos.pack(pady=5)

    def ejecutar_por_codigos():
        codigos_raw = entrada_codigos.get("1.0", tk.END)
        # 🔧 Limpia saltos de línea y espacios, convierte todo a una lista
        codigos_list = [c.strip() for c in codigos_raw.replace('\n', ',').split(',') if c.strip()]
        if not codigos_list:
            messagebox.showwarning("Faltan datos", "Ingresá al menos un código.")
            return

        codigos_como_str = ",".join(codigos_list)
        ruta_script = os.path.join("Diarios", "actualizar_clientes_por_codigo.exe")

        try:
            subprocess.Popen([ruta_script, codigos_como_str])
            messagebox.showinfo("Actualizando", f"Se está ejecutando la actualización de {len(codigos_list)} código(s).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Button(
        ventana_clientes,
        text="Actualizar códigos Ingresados",
        command=ejecutar_por_codigos,
        # bg="blue",
        # fg="white"
    ).pack(pady=10)


ventana = tk.Tk()
ventana.title("Panel de Sincronización")
ventana.geometry("300x420")
ventana.resizable(False, False)

style = ttk.Style()
style.configure("TButton", padding=10, font=('Arial', 10))

ttk.Button(ventana, text="Actualizar Productos", command=ejecutar_actualizar_productos).pack(pady=5, padx=10, fill="x")
ttk.Button(ventana, text="Actualizar Precios", command=ejecutar_actualizar_precios).pack(pady=5, padx=10, fill="x")
ttk.Button(ventana, text="Actualizar stock", command=ejecutar_actualizar_stock).pack(pady=5, padx=10, fill="x")
ttk.Button(ventana, text="Actualizar Imágenes", command=ejecutar_actualizar_imagenes).pack(pady=5, padx=10, fill="x")
ttk.Button(ventana, text="Actualizar Clientes", command=abrir_ventana_clientes).pack(pady=5, padx=10, fill="x")
ttk.Button(ventana, text="Sincronizar Pedidos", command=ejecutar_sincronizar_pedidos).pack(pady=5, padx=10, fill="x")
ttk.Button(ventana, text="Desactivé productos", command=ejecutar_desactivar_suspendidos).pack(pady=5, padx=10, fill="x")

mensaje_label = tk.Label(ventana, text="", font=('Arial', 9), wraplength=280)
mensaje_label.pack(pady=10)

ventana.mainloop()