import os
import sqlite3
from contextlib import closing
import tkinter as tk
from tkinter import ttk
from llaves import obtener_tabla_clasificacion

FONDO = "#FFFFFF"
ROJO = "#C62828"
ROJO_OSCURO = "#8E1B1B"
VERDE = "#DCFCE7"
VERDE_TEXTO = "#166534"
ROJO_FONDO = "#FEE2E2"
ROJO_TEXTO = "#991B1B"
GRIS = "#666666"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
RUTA_BD = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")

def _separar_tiempo_tabla(valor):
    """Separa MM:SSCC en una parte grande y centésimas pequeñas."""
    texto = str(valor or "00:0000").strip()
    try:
        if texto.count(":") == 2:
            minutos, segundos, centesimas = (int(p) for p in texto.split(":"))
        elif texto.count(":") == 1:
            minutos, resto = texto.split(":")
            minutos = int(minutos)
            resto = resto.zfill(4)
            segundos, centesimas = int(resto[:2]), int(resto[2:])
        else:
            return "00:00", "00"
        return f"{minutos:02d}:{segundos:02d}", f"{centesimas:02d}"
    except (TypeError, ValueError):
        return "00:00", "00"



def estado_fase():
    with closing(sqlite3.connect(RUTA_BD)) as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
        hay_grupos = cursor.fetchone()[0] > 0

        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
        total_grupos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo' AND estado != 'Completado'")
        pendientes_grupos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
        total_todos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos' AND estado != 'Completado'")
        pendientes_todos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM llaves")
        total_llaves = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
        total_finales = cursor.fetchone()[0]

    return {
        "hay_grupos": hay_grupos,
        "total_grupos": total_grupos,
        "pendientes_grupos": pendientes_grupos,
        "total_todos": total_todos,
        "pendientes_todos": pendientes_todos,
        "total_llaves": total_llaves,
        "total_finales": total_finales,
    }

def mostrar_clasificaciones(contenedor):
    for widget in contenedor.winfo_children():
        widget.destroy()

    principal = tk.Frame(contenedor, bg=FONDO)
    principal.pack(fill="both", expand=True, padx=36, pady=28)

    tk.Label(
        principal, text="CLASIFICACIONES",
        font=("Arial", 16, "bold"), fg=ROJO_OSCURO, bg=FONDO
    ).pack(anchor="w", pady=(0, 14))

    marco = tk.Frame(principal, bg=FONDO)
    marco.pack(fill="both", expand=True)

    columnas = ("posicion", "robot", "puntos", "ataques", "tiempo", "victorias")
    tabla = ttk.Treeview(marco, columns=columnas, show="headings", height=16)
    for col, titulo, ancho in [
        ("posicion", "POSICIÓN", 150),
        ("robot", "ROBOT", 205),
        ("puntos", "PUNTOS", 100),
        ("ataques", "ATAQUES", 125),
        ("tiempo", "TIEMPO PROM.", 130),
        ("victorias", "VICTORIAS", 135),
    ]:
        tabla.heading(col, text=titulo)
        tabla.column(col, width=ancho, anchor="center", stretch=True)

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
    estilo.configure(
        "Clasificaciones.Treeview",
        rowheight=36,
        borderwidth=1,
        relief="solid",
        bordercolor="#CBD5E1",
        lightcolor="#CBD5E1",
        darkcolor="#CBD5E1",
        background="#FFFFFF",
        fieldbackground="#FFFFFF",
        foreground="#1F2937",
        font=("Arial", 14),
    )
    estilo.configure(
        "Clasificaciones.Treeview.Heading",
        borderwidth=1,
        relief="solid",
        bordercolor="#CBD5E1",
        lightcolor="#CBD5E1",
        darkcolor="#CBD5E1",
        font=("Arial", 14, "bold"),
    )
    tabla.configure(style="Clasificaciones.Treeview")

    tiempos_visuales = []
    etiquetas_tiempo = []

    def dibujar_tiempos_visuales():
        for widget in etiquetas_tiempo:
            widget.destroy()
        etiquetas_tiempo.clear()
        for item, tiempo_principal, centesimas, color_fondo in tiempos_visuales:
            caja = tabla.bbox(item, "tiempo")
            if not caja:
                continue
            x, y, ancho, alto = caja
            seleccionado = item in tabla.selection()
            fondo_seleccion = estilo.lookup("Treeview", "background", ("selected",)) or "#4A6984"
            fondo_celda = fondo_seleccion if seleccionado else color_fondo
            celda = tk.Frame(tabla, bg=fondo_celda, bd=0, highlightthickness=0)
            celda.place(x=x, y=y, width=ancho, height=alto)
            contenido_tiempo = tk.Frame(celda, bg=fondo_celda, bd=0, highlightthickness=0)
            contenido_tiempo.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(
                contenido_tiempo, text=tiempo_principal, font=("Arial", 14),
                bg=fondo_celda, fg="#1F2937", bd=0, padx=0
            ).pack(side="left", anchor="center", padx=0)
            tk.Label(
                contenido_tiempo, text=centesimas, font=("Arial", 9),
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

    def desplazar_tiempos(*_args):
        dibujar_tiempos_visuales()

    barra = ttk.Scrollbar(
        marco, orient="vertical",
        command=lambda *args: (tabla.yview(*args), dibujar_tiempos_visuales())
    )
    tabla.configure(
        yscrollcommand=lambda *args: (barra.set(*args), dibujar_tiempos_visuales())
    )
    tabla.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    tabla.bind("<Configure>", lambda _e: dibujar_tiempos_visuales(), add="+")
    tabla.bind("<<TreeviewSelect>>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")
    tabla.bind("<MouseWheel>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")
    tabla.bind("<Button-4>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")
    tabla.bind("<Button-5>", lambda _e: tabla.after_idle(dibujar_tiempos_visuales), add="+")

    tabla.tag_configure("clasifica", background="#DCFCE7", foreground="#166534")
    tabla.tag_configure("eliminado", background="#FEE2E2", foreground="#991B1B")
    tabla.tag_configure("pendiente", background="#FFFFFF", foreground="#1F2937")
    tabla.tag_configure("sin_jugar", background="#FFFFFF", foreground="#64748B")
    colores_grupo = ["#DBEAFE"]
    for indice, color in enumerate(colores_grupo):
        tabla.tag_configure(
            f"encabezado_grupo_{indice}",
            background=color,
            foreground="#1F2937",
            font=("Arial", 14, "bold"),
        )

    leyenda = tk.Frame(principal, bg=FONDO)
    leyenda.pack(anchor="w", pady=(12, 0))
    tk.Label(leyenda, text="  ", bg="#DCFCE7", relief="solid", bd=1, width=2).pack(side="left", padx=(0, 6))
    tk.Label(leyenda, text="Clasificado", bg=FONDO, fg="#166534", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 18))
    tk.Label(leyenda, text="  ", bg="#FEE2E2", relief="solid", bd=1, width=2).pack(side="left", padx=(0, 6))
    tk.Label(leyenda, text="No clasificado", bg=FONDO, fg="#991B1B", font=("Arial", 9, "bold")).pack(side="left")

    def clave_grupo(fila):
        # Durante la fase en curso, quienes aún no han competido quedan al final.
        if not fila.get("ha_competido"):
            return (1, 0, 0, float("inf"), 0, fila.get("id", 0))
        tiempo = fila.get("tiempo_promedio")
        return (
            0,
            -float(fila.get("puntos") or 0),
            -float(fila.get("porcentaje_ataques") or 0),
            float("inf") if tiempo is None else float(tiempo),
            -float(fila.get("victorias") or 0),
            fila.get("id", 0),
        )

    def cargar():
        try:
            filas = obtener_tabla_clasificacion() or []
            estado = estado_fase()
        except (sqlite3.Error, KeyError, TypeError) as error:
            print(f"No se pudo actualizar la clasificación: {error}")
            return

        tabla.delete(*tabla.get_children())
        tiempos_visuales.clear()
        hay_grupos = estado["hay_grupos"]
        if hay_grupos:
            fase_terminada = (
                estado["total_grupos"] > 0
                and estado["pendientes_grupos"] == 0
            )
        else:
            fase_terminada = (
                estado["total_todos"] > 0
                and estado["pendientes_todos"] == 0
            )

        if hay_grupos:
            grupos = {}
            for fila in filas:
                nombre_grupo = (fila.get("grupo") or "Sin grupo").strip()
                if nombre_grupo == "Todos contra todos":
                    nombre_grupo = "Sin grupo"
                grupos.setdefault(nombre_grupo, []).append(fila)

            for indice, nombre_grupo in enumerate(sorted(grupos, key=str.casefold)):
                etiqueta = nombre_grupo.upper()
                tabla.insert(
                    "", "end",
                    values=(etiqueta, "", "", "", "", ""),
                    tags=("encabezado_grupo_0",)
                )

                filas_grupo = sorted(grupos[nombre_grupo], key=clave_grupo)
                for posicion_grupo, fila in enumerate(filas_grupo, 1):
                    tiempo, centesimas = (
                        _separar_tiempo_tabla(fila.get("tiempo_mostrar", "00:0000"))
                        if fila.get("ha_competido") else ("—", "")
                    )
                    valores = (
                        f"{posicion_grupo}°",
                        fila.get("robot") or "—",
                        fila.get("puntos", 0) if fila.get("ha_competido") else "—",
                        f'{(fila.get("porcentaje_ataques") or 0):.1f}%' if fila.get("ha_competido") else "—",
                        "",
                        f'{(fila.get("porcentaje_victorias") or 0):.0f}%' if fila.get("ha_competido") else "—",
                    )
                    if not fase_terminada:
                        tag = "pendiente"
                    elif not fila.get("ha_competido"):
                        tag = "eliminado"
                    else:
                        tag = "clasifica" if fila.get("clasifica") else "eliminado"
                    item = tabla.insert("", "end", values=valores, tags=(tag,))
                    if fila.get("ha_competido"):
                        color_tiempo = "#DCFCE7" if tag == "clasifica" else "#FEE2E2" if tag == "eliminado" else "#FFFFFF"
                        tiempos_visuales.append((item, tiempo, centesimas, color_tiempo))
        else:
            for fila in filas:
                tiempo, centesimas = (
                    _separar_tiempo_tabla(fila.get("tiempo_mostrar", "00:0000"))
                    if fila.get("ha_competido") else ("—", "")
                )
                valores = (
                    f'{fila.get("posicion", "—")}°',
                    fila.get("robot") or "—",
                    fila.get("puntos", 0) if fila.get("ha_competido") else "—",
                    f'{(fila.get("porcentaje_ataques") or 0):.1f}%' if fila.get("ha_competido") else "—",
                    "",
                    f'{(fila.get("porcentaje_victorias") or 0):.0f}%' if fila.get("ha_competido") else "—",
                )
                if not fase_terminada:
                    tag = "pendiente"
                elif not fila.get("ha_competido"):
                    tag = "eliminado"
                else:
                    tag = "clasifica" if fila.get("clasifica") else "eliminado"
                item = tabla.insert("", "end", values=valores, tags=(tag,))
                if fila.get("ha_competido"):
                    color_tiempo = "#DCFCE7" if tag == "clasifica" else "#FEE2E2" if tag == "eliminado" else "#FFFFFF"
                    tiempos_visuales.append((item, tiempo, centesimas, color_tiempo))

        tabla.after_idle(dibujar_tiempos_visuales)

    # Se consulta al entrar a la pestaña; no se vuelve a leer la BD cada segundo.
    # Al finalizar una batalla, la clasificación se verá actualizada al abrir esta página.
    cargar()
    principal.after_idle(dibujar_tiempos_visuales)
