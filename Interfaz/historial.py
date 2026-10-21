import os
import sqlite3
import tkinter as tk
from tkinter import ttk


def _separar_tiempo_tabla(valor):
    """Separa el tiempo en MM:SS y centésimas para usar fuentes distintas."""
    partes = str(valor or "").strip().split(":")
    try:
        if len(partes) == 3:
            minutos, segundos, centesimas = (int(p) for p in partes)
        elif len(partes) == 2:
            minutos = int(partes[0])
            resto = partes[1].zfill(4)
            segundos, centesimas = int(resto[:2]), int(resto[2:])
        else:
            return "—", ""
        if minutos < 0 or not 0 <= segundos < 60 or not 0 <= centesimas < 100:
            return valor or "—", ""
        return f"{minutos:02d}:{segundos:02d}", f"{centesimas:02d}"
    except (TypeError, ValueError):
        return valor or "—", ""

FONDO = "#FFFFFF"
ROJO_OSCURO = "#8E1B1B"
TEXTO = "#1F2937"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
RUTA_BD = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")


def conectar():
    return sqlite3.connect(RUTA_BD)


def obtener_historial():
    """Consulta únicamente resultados archivados de batallas finalizadas."""
    with conectar() as conexion:
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT
                id,
                COALESCE(robot1, '—'),
                COALESCE(robot2, '—'),
                COALESCE(tiempo, ''),
                COALESCE(ataques1, '—'),
                COALESCE(ataques2, '—'),
                COALESCE(ganador, 'Sin ganador'),
                COALESCE(motivo, '—')
            FROM historial_batallas
            ORDER BY id DESC
        """)
        return cursor.fetchall()


def mostrar_historial(contenedor):
    for widget in contenedor.winfo_children():
        widget.destroy()

    principal = tk.Frame(contenedor, bg=FONDO)
    principal.pack(fill="both", expand=True, padx=36, pady=28)

    tk.Label(
        principal,
        text="HISTORIAL DE BATALLAS",
        font=("Arial", 16, "bold"),
        fg=ROJO_OSCURO,
        bg=FONDO
    ).pack(anchor="w", pady=(0, 6))

    marco = tk.Frame(principal, bg=FONDO)
    marco.pack(fill="both", expand=True)

    columnas = (
        "numero", "robot1", "robot2", "tiempo",
        "ataques1", "ataques2", "ganador", "motivo"
    )
    tabla = ttk.Treeview(marco, columns=columnas, show="headings", height=16)

    encabezados = [
        ("numero", "N°", 65),
        ("robot1", "ROBOT 1", 155),
        ("robot2", "ROBOT 2", 155),
        ("tiempo", "TIEMPO", 125),
        ("ataques1", "ATQ. 1", 85),
        ("ataques2", "ATQ. 2", 85),
        ("ganador", "GANADOR", 155),
        ("motivo", "MOTIVO", 190),
    ]
    for columna, titulo, ancho in encabezados:
        tabla.heading(columna, text=titulo)
        tabla.column(columna, width=ancho, minwidth=55, anchor="center", stretch=True)

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
    estilo.configure(
        "Historial.Treeview",
        rowheight=36,
        borderwidth=1,
        relief="solid",
        bordercolor="#CBD5E1",
        background="#FFFFFF",
        fieldbackground="#FFFFFF",
        foreground=TEXTO,
        font=("Arial", 12),
    )
    estilo.configure(
        "Historial.Treeview.Heading",
        borderwidth=1,
        relief="solid",
        bordercolor="#CBD5E1",
        font=("Arial", 12, "bold"),
    )
    tabla.configure(style="Historial.Treeview")

    tiempos_visuales = []
    etiquetas_tiempo = []

    def dibujar_tiempos_visuales():
        for widget in etiquetas_tiempo:
            widget.destroy()
        etiquetas_tiempo.clear()
        for item, tiempo_principal, centesimas in tiempos_visuales:
            caja = tabla.bbox(item, "tiempo")
            if not caja:
                continue
            x, y, ancho, alto = caja
            seleccionado = item in tabla.selection()
            fondo_seleccion = estilo.lookup("Treeview", "background", ("selected",)) or "#4A6984"
            fondo_celda = fondo_seleccion if seleccionado else "#FFFFFF"
            celda = tk.Frame(tabla, bg=fondo_celda, bd=0, highlightthickness=0)
            celda.place(x=x, y=y, width=ancho, height=alto)
            contenido_tiempo = tk.Frame(celda, bg=fondo_celda, bd=0, highlightthickness=0)
            contenido_tiempo.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(
                contenido_tiempo, text=tiempo_principal, font=("Arial", 12),
                bg=fondo_celda, fg="#1F2937", bd=0, padx=0
            ).pack(side="left", anchor="center", padx=0)
            tk.Label(
                contenido_tiempo, text=centesimas, font=("Arial", 8),
                bg=fondo_celda, fg="#1F2937", bd=0, padx=0
            ).pack(side="left", anchor="s", padx=0, pady=(6, 0))
            def seleccionar_tiempo(_evento, iid=item):
                tabla.selection_set(iid)
                tabla.focus(iid)
                tabla.after_idle(dibujar_tiempos_visuales)
                return "break"
            for elemento in (celda, contenido_tiempo, *contenido_tiempo.winfo_children()):
                elemento.bind("<Button-1>", seleccionar_tiempo)
            etiquetas_tiempo.append(celda)

    barra_vertical = ttk.Scrollbar(
        marco, orient="vertical",
        command=lambda *args: (tabla.yview(*args), dibujar_tiempos_visuales())
    )
    barra_horizontal = ttk.Scrollbar(
        principal, orient="horizontal",
        command=lambda *args: (tabla.xview(*args), dibujar_tiempos_visuales())
    )
    tabla.configure(
        yscrollcommand=lambda *args: (barra_vertical.set(*args), dibujar_tiempos_visuales()),
        xscrollcommand=lambda *args: (barra_horizontal.set(*args), dibujar_tiempos_visuales())
    )
    tabla.pack(side="left", fill="both", expand=True)
    barra_vertical.pack(side="right", fill="y")
    barra_horizontal.pack(fill="x")
    tabla.bind("<Configure>", lambda _e: dibujar_tiempos_visuales(), add="+")
    tabla.bind("<<TreeviewSelect>>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")
    tabla.bind("<MouseWheel>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")
    tabla.bind("<Button-4>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")
    tabla.bind("<Button-5>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")

    def cargar():
        if not principal.winfo_exists():
            return
        try:
            filas = obtener_historial()
            tabla.delete(*tabla.get_children())
            tiempos_visuales.clear()

            for fila in filas:
                valores = list(fila)
                valores[0] = str(valores[0])
                tiempo, centesimas = _separar_tiempo_tabla(valores[3])
                valores[3] = ""
                valores[4] = "—" if valores[4] in ("", None) else valores[4]
                valores[5] = "—" if valores[5] in ("", None) else valores[5]
                item = tabla.insert("", "end", values=valores)
                if tiempo != "—":
                    tiempos_visuales.append((item, tiempo, centesimas))
            tabla.after_idle(dibujar_tiempos_visuales)

        except sqlite3.Error as error:
            print(f"No se pudo cargar el historial: {error}")

    cargar()
