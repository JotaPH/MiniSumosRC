import os
import sqlite3
from contextlib import closing
import tkinter as tk
from tkinter import ttk

FONDO = "#FFFFFF"
ROJO = "#C62828"
ROJO_OSCURO = "#8E1B1B"
TEXTO = "#222222"
GRIS = "#666666"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
RUTA_BD = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")

def conectar():
    return sqlite3.connect(RUTA_BD)

def mostrar_grupos(contenedor):
    for widget in contenedor.winfo_children():
        widget.destroy()

    principal = tk.Frame(contenedor, bg=FONDO)
    principal.pack(fill="both", expand=True, padx=36, pady=28)

    tk.Label(
        principal, text="GRUPOS DE LA COMPETENCIA",
        font=("Arial", 20, "bold"), fg=ROJO_OSCURO, bg=FONDO
    ).pack(anchor="w", pady=(0, 20))

    marco = tk.Frame(principal, bg=FONDO)
    marco.pack(fill="both", expand=True)

    columnas = ("numero", "grupo", "robot", "participante")
    tabla = ttk.Treeview(marco, columns=columnas, show="headings", height=16)
    encabezados = {
        "numero": ("N.º", 70),
        "grupo": ("GRUPO", 170),
        "robot": ("ROBOT", 280),
        "participante": ("PARTICIPANTE", 260),
    }
    for col, (titulo, ancho) in encabezados.items():
        tabla.heading(col, text=titulo)
        tabla.column(col, width=ancho, anchor="center", stretch=True)

    colores = [
        "#F1F5F9", "#FEF3C7", "#DCFCE7", "#DBEAFE",
        "#FCE7F3", "#EDE9FE", "#FFEDD5", "#CCFBF1",
        "#F3F4F6", "#ECFCCB"
    ]
    for i, color in enumerate(colores):
        tabla.tag_configure(f"grupo_{i}", background=color, foreground=TEXTO)

    barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=barra.set)

    estado = tk.Label(
        principal, text="", font=("Arial", 12), bg=FONDO, fg=GRIS,
        justify="center", wraplength=800
    )
    estado.pack(anchor="center", pady=(24, 0))

    def cargar():
        tabla.delete(*tabla.get_children())
        try:
            with closing(conectar()) as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    SELECT g.id, g.nombre, p.robot, p.nombre
                    FROM grupos g
                    LEFT JOIN grupo_participantes gp ON gp.grupo_id = g.id
                    LEFT JOIN participantes p ON p.id = gp.participante_id
                    ORDER BY g.id, gp.rowid
                """)
                filas = cursor.fetchall()
        except sqlite3.Error as error:
            tabla.pack_forget()
            barra.pack_forget()
            estado.config(text=f"No se pudieron leer los grupos: {error}", fg=ROJO)
            return

        if not filas:
            tabla.pack_forget()
            barra.pack_forget()
            estado.config(
                text="En esta competencia no se definieron grupos. "
                     "La fase inicial se juega todos contra todos.",
                fg=GRIS
            )
            return

        estado.pack_forget()
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        estado.pack(anchor="w", pady=(10, 0))
        contadores = {}
        indice_grupo = {}
        for _, grupo, robot, participante in filas:
            contadores[grupo] = contadores.get(grupo, 0) + 1
            if grupo not in indice_grupo:
                indice_grupo[grupo] = len(indice_grupo) % len(colores)
            tabla.insert(
                "", "end",
                values=(contadores[grupo], grupo, robot or "—", participante or "—"),
                tags=(f"grupo_{indice_grupo[grupo]}",)
            )
        estado.config(
            text=f"{len(contadores)} grupos • {sum(1 for fila in filas if fila[2] or fila[3])} participantes asignados",
            fg=GRIS
        )

    cargar()
