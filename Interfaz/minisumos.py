import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from PIL import Image, ImageTk
from registro import mostrar_registro, cerrar_registro
from enfrentamientos import mostrar_enfrentamientos
from batallas import mostrar_batallas
from grupos import mostrar_grupos
from clasificaciones import mostrar_clasificaciones
from eliminatorias import mostrar_eliminatorias
from historial import mostrar_historial

# ============================================================
# CONFIGURACIÓN PRINCIPAL
# ============================================================

ventana = tk.Tk()

FONDO = "#FFFFFF"
ROJO = "#C62828"
ROJO_OSCURO = "#8E1B1B"
ROJO_CLARO = "#FA7B55"
GRIS_CLARO = "#E5E7EB"
TEXTO = "#222222"

ventana.title("MiniSumos RC")
ventana.state("zoomed")
ventana.configure(bg=FONDO)


# ============================================================
# RUTAS DE IMÁGENES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)

ruta_logo_metarobots = os.path.join(BASE_DIR,"Imagenes", "metarobots_logo.jpg")
ruta_logo_unillanos = os.path.join(BASE_DIR,"Imagenes", "unillanos_logo.jpg")


# ============================================================
# LOGO METAROBOTS
# ============================================================

imagen_metarobots = Image.open(
    ruta_logo_metarobots
)

imagen_metarobots.thumbnail(
    (80, 80),
    Image.LANCZOS
)

logo_metarobots = ImageTk.PhotoImage(
    imagen_metarobots
)


# ============================================================
# LOGO UNILLANOS
# ============================================================

imagen_unillanos = Image.open(
    ruta_logo_unillanos
)

imagen_unillanos.thumbnail(
    (90, 90),
    Image.LANCZOS
)

logo_unillanos = ImageTk.PhotoImage(
    imagen_unillanos
)


# ============================================================
# ESTILOS
# ============================================================

estilo = ttk.Style()
estilo.theme_use("clam")


# ============================================================
# ENCABEZADO PRINCIPAL
# ============================================================

cabecera = tk.Frame(
    ventana,
    bg=FONDO,
    height=105
)

cabecera.pack(
    fill="x"
)

cabecera.pack_propagate(False)


# ------------------------------------------------------------
# LOGO METAROBOTS
# ------------------------------------------------------------

tk.Label(
    cabecera,
    image=logo_metarobots,
    bg=FONDO
).pack(
    side="left",
    padx=(30, 20)
)


# ------------------------------------------------------------
# TÍTULO
# ------------------------------------------------------------

marco_titulo = tk.Frame(
    cabecera,
    bg=FONDO
)

marco_titulo.pack(
    side="left",
    expand=True
)

tk.Label(
    marco_titulo,
    text="MINI SUMOS RC - 2026 II",
    font=("Arial", 30, "bold"),
    fg=ROJO_OSCURO,
    bg=FONDO
).pack()

tk.Label(
    marco_titulo,
    text="CATEGORIA JUNIOR",
    font=("Arial", 30, "bold"),
    fg=ROJO_OSCURO,
    bg=FONDO
).pack(
    pady=(3, 0)
)


# ------------------------------------------------------------
# LOGO UNILLANOS
# ------------------------------------------------------------

tk.Label(
    cabecera,
    image=logo_unillanos,
    bg=FONDO
).pack(
    side="right",
    padx=(20, 30)
)


# ------------------------------------------------------------
# LÍNEA DEL ENCABEZADO
# ------------------------------------------------------------

tk.Frame(
    ventana,
    bg=GRIS_CLARO,
    height=1
).pack(
    fill="x"
)


# ============================================================
# ZONA PRINCIPAL
# ============================================================

zona_principal = tk.Frame(
    ventana,
    bg=FONDO
)

zona_principal.pack(
    fill="both",
    expand=True
)


# ============================================================
# MENÚ LATERAL
# ============================================================

menu = tk.Frame(
    zona_principal,
    bg=FONDO,
    width=240
)

menu.pack(
    side="left",
    fill="y"
)

menu.pack_propagate(False)


# ============================================================
# TÍTULO DEL MENÚ
# ============================================================

tk.Label(
    menu,
    text="MENÚ",
    font=("Arial", 20, "bold"),
    fg=ROJO_OSCURO,
    bg=FONDO
).pack(
    pady=(25, 15)
)


# ============================================================
# ÁREA DE CONTENIDO
# ============================================================

area_contenido = tk.Frame(
    zona_principal,
    bg=FONDO
)

area_contenido.pack(
    side="right",
    fill="both",
    expand=True
)


# ============================================================
# CAMBIO DE PÁGINAS
# ============================================================

pagina_actual = None
boton_actual = None


def limpiar_contenido():

    global pagina_actual

    if pagina_actual is not None:
        pagina_actual.destroy()

    pagina_actual = tk.Frame(
        area_contenido,
        bg=FONDO
    )

    pagina_actual.pack(
        fill="both",
        expand=True
    )

    return pagina_actual


# ============================================================
# CAMBIAR ESTADO DE BOTONES
# ============================================================

def seleccionar_boton(boton):

    global boton_actual

    if boton_actual is not None:

        boton_actual.config(
            bg=FONDO,
            fg=TEXTO
        )

    boton.config(
        bg="#FDECEC",
        fg=ROJO_OSCURO
    )

    boton_actual = boton


# ============================================================
# REGISTRO
# ============================================================

def mostrar_pagina_registro():

    contenedor = limpiar_contenido()

    mostrar_registro(
        contenedor
    )

    seleccionar_boton(
        botones_menu[0]
    )


# ============================================================
# ENFRENTAMIENTOS
# ============================================================

def mostrar_pagina_enfrentamientos():

    contenedor = limpiar_contenido()

    mostrar_enfrentamientos(
        contenedor
    )

    seleccionar_boton(
        botones_menu[2]
    )


# ============================================================
# BATALLAS
# ============================================================

def mostrar_pagina_batallas():
    contenedor = limpiar_contenido()
    # Se selecciona primero el botón para que el resaltado se actualice incluso
    # si la pantalla de Batallas no encuentra combates pendientes.
    seleccionar_boton(botones_menu[5])

    def al_terminar_fase(pagina, mensaje, demora_ms=3000):
        def redirigir():
            if pagina == "clasificaciones":
                mostrar_pagina_clasificaciones()
            else:
                mostrar_pagina_eliminatorias()
        ventana.after(max(0, demora_ms), redirigir)

    mostrar_batallas(contenedor, al_terminar_fase=al_terminar_fase)

# ============================================================
# GRUPOS
# ============================================================
def mostrar_pagina_grupos():
    contenedor = limpiar_contenido()
    mostrar_grupos(contenedor)
    seleccionar_boton(botones_menu[1])


# ============================================================
# CLASIFICACIONES
# ============================================================
def mostrar_pagina_clasificaciones():
    contenedor = limpiar_contenido()
    mostrar_clasificaciones(contenedor)
    seleccionar_boton(botones_menu[4])


# ============================================================
# ELIMINATORIAS
# ============================================================
def mostrar_pagina_eliminatorias():
    contenedor = limpiar_contenido()
    mostrar_eliminatorias(contenedor)
    seleccionar_boton(botones_menu[3])


# ============================================================
# HISTORIAL
# ============================================================
def mostrar_pagina_historial():
    contenedor = limpiar_contenido()
    mostrar_historial(contenedor)
    seleccionar_boton(botones_menu[6])


# ============================================================
# BOTONES DEL MENÚ
# ============================================================

botones_menu = []


def crear_boton_menu(texto, comando):

    contenedor_boton = tk.Frame(
        menu,
        bg=FONDO
    )

    contenedor_boton.pack(
        fill="x"
    )

    boton = tk.Button(
        contenedor_boton,
        text=texto,
        command=comando,
        font=("Arial", 15, "bold"),
        bg=FONDO,
        fg=TEXTO,
        activebackground="#FDECEC",
        activeforeground=ROJO_OSCURO,
        relief="flat",
        bd=0,
        cursor="hand2",
        anchor="w",
        padx=25
    )

    boton.pack(
        fill="x",
        ipady=15
    )

    # --------------------------------------------------------
    # ANIMACIÓN HOVER
    # --------------------------------------------------------

    def entrar(event):

        if boton != boton_actual:

            boton.config(
                bg="#FDECEC",
                fg=ROJO_OSCURO
            )

    def salir(event):

        if boton != boton_actual:

            boton.config(
                bg=FONDO,
                fg=TEXTO
            )

    boton.bind(
        "<Enter>",
        entrar
    )

    boton.bind(
        "<Leave>",
        salir
    )

    # --------------------------------------------------------
    # LÍNEA SEPARADORA
    # --------------------------------------------------------

    tk.Frame(
        contenedor_boton,
        bg=GRIS_CLARO,
        height=1
    ).pack(
        fill="x"
    )

    botones_menu.append(
        boton
    )

    return boton


crear_boton_menu(
    "REGISTRO",
    mostrar_pagina_registro
)

crear_boton_menu(
    "GRUPOS",
    mostrar_pagina_grupos
)

crear_boton_menu(
    "ENFRENTAMIENTOS",
    mostrar_pagina_enfrentamientos
)

crear_boton_menu(
    "ELIMINATORIAS",
    mostrar_pagina_eliminatorias
)

crear_boton_menu(
    "CLASIFICACIONES",
    mostrar_pagina_clasificaciones
)

crear_boton_menu(
    "BATALLAS",
    mostrar_pagina_batallas
)

crear_boton_menu(
    "HISTORIAL",
    mostrar_pagina_historial
)


# ============================================================
# INICIAR Y CERRAR DASHBOARD
# ============================================================

URL_DASHBOARD = "http://127.0.0.1:8000"
RUTA_APP_DASHBOARD = os.path.join(BASE_DIR, "Interfaz", "app.py")
proceso_dashboard = None


def dashboard_disponible():
    try:
        with urllib.request.urlopen(
            f"{URL_DASHBOARD}/api/state",
            timeout=0.5
        ):
            return True
    except Exception:
        return False


def detener_dashboard_anterior():
    """Cierra únicamente procesos que ejecuten el app.py de este repositorio."""
    if os.name != "nt":
        return

    ruta_objetivo = os.path.normcase(os.path.abspath(RUTA_APP_DASHBOARD))
    ruta_ps = ruta_objetivo.replace("'", "''")
    script = (
        "$needle = [regex]::Escape('" + ruta_ps + "'); "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -and $_.CommandLine -match $needle } | "
        "ForEach-Object { "
        "if ($_.ProcessId -ne $PID) { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
        "} }"
    )

    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", script
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False
        )
        # Da tiempo a Windows para liberar el puerto del servidor anterior.
        time.sleep(0.5)
    except (OSError, subprocess.TimeoutExpired):
        # Si no se puede consultar PowerShell, el inicio normal aún puede funcionar.
        pass


def iniciar_dashboard():
    global proceso_dashboard

    # Elimina una instancia huérfana de este mismo dashboard si quedó abierta
    # después de cerrar MiniSumos de forma inesperada.
    detener_dashboard_anterior()

    opciones = {}
    if os.name == "nt":
        opciones["creationflags"] = subprocess.CREATE_NO_WINDOW

    proceso_dashboard = subprocess.Popen(
        [sys.executable, RUTA_APP_DASHBOARD],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **opciones
    )

    def esperar_y_abrir_dashboard():
        limite = time.time() + 20

        while time.time() < limite:
            if dashboard_disponible():
                webbrowser.open(URL_DASHBOARD)
                return

            if proceso_dashboard is not None and proceso_dashboard.poll() is not None:
                return

            time.sleep(0.25)

    threading.Thread(
        target=esperar_y_abrir_dashboard,
        daemon=True
    ).start()


# ============================================================
# CERRAR PROGRAMA
# ============================================================

def cerrar_programa():
    try:
        cerrar_registro()
    finally:
        if proceso_dashboard is not None and proceso_dashboard.poll() is None:
            proceso_dashboard.terminate()

            try:
                proceso_dashboard.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proceso_dashboard.kill()
                proceso_dashboard.wait(timeout=2)

        ventana.destroy()


ventana.protocol(
    "WM_DELETE_WINDOW",
    cerrar_programa
)


# ============================================================
# INICIAR EN REGISTRO
# ============================================================

mostrar_pagina_registro()
iniciar_dashboard()


# ============================================================
# EJECUTAR
# ============================================================

ventana.mainloop()
