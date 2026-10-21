import os
import sqlite3
from contextlib import closing
import tkinter as tk
from tkinter import ttk
from llaves import obtener_datos_llaves

FONDO = "#FFFFFF"
ROJO_OSCURO = "#8E1B1B"
GRIS = "#64748B"
VERDE = "#DCFCE7"
VERDE_TEXTO = "#166534"
BORDE = "#CBD5E1"
TEXTO = "#1F2937"

def mostrar_eliminatorias(contenedor):
    for widget in contenedor.winfo_children():
        widget.destroy()

    principal = tk.Frame(contenedor, bg=FONDO)
    principal.pack(fill="both", expand=True, padx=40, pady=25)

    tk.Label(
        principal, text="ELIMINATORIAS",
        font=("Arial", 20, "bold"), fg="#8E1B1B", bg=FONDO
    ).pack(anchor="w", pady=(0, 14))

    mensaje_vacio = tk.Label(
        principal, text="", font=("Arial", 15, "bold"),
        fg=GRIS, bg=FONDO, justify="center", wraplength=850
    )

    marco_llaves = tk.Frame(principal, bg=FONDO)
    marco_llaves.pack(fill="both", expand=True)
    canvas_llaves = tk.Canvas(marco_llaves, bg=FONDO, highlightthickness=0)
    scroll_y_llaves = ttk.Scrollbar(marco_llaves, orient="vertical", command=canvas_llaves.yview)
    scroll_x_llaves = ttk.Scrollbar(marco_llaves, orient="horizontal", command=canvas_llaves.xview)
    canvas_llaves.configure(yscrollcommand=scroll_y_llaves.set, xscrollcommand=scroll_x_llaves.set)
    canvas_llaves.grid(row=0, column=0, sticky="nsew")
    scroll_y_llaves.grid(row=0, column=1, sticky="ns")
    scroll_x_llaves.grid(row=1, column=0, sticky="ew")
    marco_llaves.grid_rowconfigure(0, weight=1)
    marco_llaves.grid_columnconfigure(0, weight=1)

    def cargar_cuadro_llaves():
        rondas = obtener_datos_llaves()
        if rondas:
            mensaje_vacio.pack_forget()
            if not marco_llaves.winfo_manager():
                marco_llaves.pack(fill="both", expand=True)
        if not rondas:
            canvas_llaves.delete("all")
            canvas_llaves.configure(scrollregion=(0, 0, 1, 1))
            marco_llaves.pack_forget()
            mensaje_vacio.pack(fill="both", expand=True, pady=30)
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                if os.path.basename(base_dir).lower() == "interfaz":
                    base_dir = os.path.dirname(base_dir)
                with closing(sqlite3.connect(os.path.join(
                    base_dir, "BasesDeDatos", "competencia.db"
                ))) as conexion:
                    cursor = conexion.cursor()
                    cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
                    hay_grupos = cursor.fetchone()[0] > 0
                    cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
                    total_grupos = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo' AND estado != 'Completado'")
                    pendientes_grupos = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
                    total_todos = cursor.fetchone()[0]
            except sqlite3.Error as error:
                print(f"No se pudo consultar el estado de eliminatorias: {error}")
                hay_grupos, total_grupos, pendientes_grupos, total_todos = False, 0, 0, 0

            if hay_grupos and total_grupos and pendientes_grupos == 0:
                texto = "La fase de grupos terminó. Ve a Batallas y pulsa CONTINUAR para generar las llaves."
            elif hay_grupos:
                texto = "Las llaves estarán disponibles cuando termine la fase de grupos. El avance se controla desde Batallas."
            elif total_todos:
                texto = "En esta competencia no habrá cuadro eliminatorio. Al terminar todos contra todos, la final se habilita desde Batallas."
            else:
                texto = "En esta competencia no hay eliminatorias generadas."
            mensaje_vacio.config(text=texto)
            return False

        mensaje_vacio.pack_forget()
        if not marco_llaves.winfo_manager():
            marco_llaves.pack(fill="both", expand=True)
        canvas_llaves.update_idletasks()
        canvas_llaves.delete("all")

        # Una tarjeta por participante y una columna final exclusiva para el campeón.
        ancho_tarjeta, alto_tarjeta = 176, 40
        separacion_x, margen_x, margen_y = 56, 22, 24
        separacion_y = 12
        cantidad_primera = max(1, len(rondas[0]["combates"]) * 2)
        alto_total = margen_y * 2 + cantidad_primera * (alto_tarjeta + separacion_y)

        # Se reserva espacio para el recuadro del campeón, incluso mientras
        # la final está pendiente.
        columnas = len(rondas) + 1
        ancho_total = margen_x * 2 + columnas * ancho_tarjeta + (columnas - 1) * separacion_x

        # Centrar el cuadro horizontal y verticalmente cuando quepa en el área visible.
        ancho_visible = max(1, canvas_llaves.winfo_width())
        alto_visible = max(1, canvas_llaves.winfo_height())
        desplazamiento_x = max(0, (ancho_visible - ancho_total) / 2)
        desplazamiento_y = max(0, (alto_visible - alto_total) / 2)

        posiciones_y = []
        for ronda in rondas:
            cantidad_tarjetas = max(1, len(ronda["combates"]) * 2)
            espacio = max(alto_total - margen_y * 2, cantidad_tarjetas * alto_tarjeta)
            posiciones_y.append([
                desplazamiento_y + margen_y + (i + 0.5) * espacio / cantidad_tarjetas
                for i in range(cantidad_tarjetas)
            ])

        def participante_de(combate, lado):
            return (
                combate[f"participante{lado}"],
                combate[f"robot{lado}"],
                combate[f"nombre{lado}"]
            )

        # Conectores entre rondas. Se conservan ambas ramas: verde para quien
        # gana y gris para quien queda eliminado.
        for indice in range(len(rondas) - 1):
            x1 = desplazamiento_x + margen_x + indice * (ancho_tarjeta + separacion_x) + ancho_tarjeta
            x2 = desplazamiento_x + margen_x + (indice + 1) * (ancho_tarjeta + separacion_x)
            xm = (x1 + x2) / 2
            for j, combate in enumerate(rondas[indice]["combates"]):
                y_p1 = posiciones_y[indice][j * 2]
                y_p2 = posiciones_y[indice][j * 2 + 1]
                y_union = (y_p1 + y_p2) / 2
                # Cada combate alimenta una tarjeta distinta de la ronda siguiente.
                # Así, dos semifinales llegan por separado a los dos finalistas,
                # sin fusionar prematuramente las cuatro ramas en una sola línea.
                y_destino = posiciones_y[indice + 1][j]
                ganador = combate["ganador"]

                color_p1 = "#16A34A" if ganador is not None and ganador == combate["participante1"] else "#94A3B8"
                color_p2 = "#16A34A" if ganador is not None and ganador == combate["participante2"] else "#94A3B8"
                canvas_llaves.create_line(
                    x1, y_p1, xm, y_p1, xm, y_union,
                    fill=color_p1, width=2
                )
                canvas_llaves.create_line(
                    x1, y_p2, xm, y_p2, xm, y_union,
                    fill=color_p2, width=2
                )

                color_salida = "#16A34A" if ganador is not None else "#94A3B8"
                canvas_llaves.create_line(
                    xm, y_union, xm, y_destino, x2, y_destino,
                    fill=color_salida, width=2
                )

        # Dibujar las tarjetas de cada ronda.
        for indice, ronda in enumerate(rondas):
            x = desplazamiento_x + margen_x + indice * (ancho_tarjeta + separacion_x)
            for j, combate in enumerate(ronda["combates"]):
                for lado in (1, 2):
                    pid, robot, persona = participante_de(combate, lado)
                    y = posiciones_y[indice][j * 2 + (lado - 1)]
                    y1, y2 = y - alto_tarjeta / 2, y + alto_tarjeta / 2

                    es_ganador = pid is not None and combate["ganador"] == pid
                    es_perdedor = (
                        pid is not None
                        and combate["ganador"] is not None
                        and combate["ganador"] != pid
                    )

                    if es_ganador:
                        fondo, borde, color_texto = "#DCFCE7", "#16A34A", "#166534"
                    elif es_perdedor:
                        fondo, borde, color_texto = "#E5E7EB", "#D1D5DB", "#6B7280"
                    elif pid is None:
                        fondo, borde, color_texto = "#F8FAFC", "#CBD5E1", "#94A3B8"
                    else:
                        fondo, borde, color_texto = "#FFFFFF", "#CBD5E1", "#334155"

                    canvas_llaves.create_rectangle(
                        x, y1, x + ancho_tarjeta, y2,
                        fill=fondo, outline=borde, width=1
                    )
                    canvas_llaves.create_text(
                        x + 8, y - 6, text=robot or "Por definir", anchor="w",
                        fill=color_texto, font=("Arial", 9, "bold"),
                        width=ancho_tarjeta - 16
                    )
                    if persona:
                        canvas_llaves.create_text(
                            x + 8, y + 10, text=persona, anchor="w",
                            fill="#64748B" if not es_perdedor else "#9CA3AF",
                            font=("Arial", 7), width=ancho_tarjeta - 16
                        )
                    if es_ganador:
                        canvas_llaves.create_text(
                            x + ancho_tarjeta - 10, y, text="●",
                            fill="#16A34A", font=("Arial", 9, "bold")
                        )
                    elif combate["estado"] == "En curso":
                        canvas_llaves.create_text(
                            x + ancho_tarjeta - 10, y, text="●",
                            fill="#D97706", font=("Arial", 9, "bold")
                        )

        # Recuadro final del campeón, conectado a los dos participantes de la
        # final. El recorrido del campeón queda verde y el del otro finalista gris.
        combate_final = rondas[-1]["combates"][-1] if rondas[-1]["combates"] else None
        x_final = desplazamiento_x + margen_x + (len(rondas) - 1) * (ancho_tarjeta + separacion_x)
        x_campeon = desplazamiento_x + margen_x + len(rondas) * (ancho_tarjeta + separacion_x)
        y_campeon = (
            posiciones_y[-1][0] + posiciones_y[-1][1]
        ) / 2 if len(posiciones_y[-1]) >= 2 else alto_total / 2

        if combate_final:
            y_p1, y_p2 = posiciones_y[-1][0], posiciones_y[-1][1]
            y_union = (y_p1 + y_p2) / 2
            x_union = x_final + ancho_tarjeta + separacion_x / 2
            ganador_id = combate_final["ganador"]

            color_p1 = "#16A34A" if ganador_id is not None and ganador_id == combate_final["participante1"] else "#94A3B8"
            color_p2 = "#16A34A" if ganador_id is not None and ganador_id == combate_final["participante2"] else "#94A3B8"
            canvas_llaves.create_line(
                x_final + ancho_tarjeta, y_p1, x_union, y_p1, x_union, y_union,
                fill=color_p1, width=2
            )
            canvas_llaves.create_line(
                x_final + ancho_tarjeta, y_p2, x_union, y_p2, x_union, y_union,
                fill=color_p2, width=2
            )
            color_salida = "#16A34A" if ganador_id is not None else "#94A3B8"
            canvas_llaves.create_line(
                x_union, y_union, x_campeon, y_campeon,
                fill=color_salida, width=2
            )

            if ganador_id is not None:
                lado_ganador = 1 if ganador_id == combate_final["participante1"] else 2
                _, robot_campeon, persona_campeon = participante_de(combate_final, lado_ganador)
                texto_robot = robot_campeon or "Campeón"
                texto_persona = persona_campeon or ""
                fondo_campeon, borde_campeon, color_campeon = "#DCFCE7", "#16A34A", "#166534"
            else:
                texto_robot = "CAMPEÓN"
                texto_persona = "Por definir"
                fondo_campeon, borde_campeon, color_campeon = "#F8FAFC", "#CBD5E1", "#64748B"

            y1, y2 = y_campeon - alto_tarjeta / 2, y_campeon + alto_tarjeta / 2
            canvas_llaves.create_rectangle(
                x_campeon, y1, x_campeon + ancho_tarjeta, y2,
                fill=fondo_campeon, outline=borde_campeon, width=2
            )
            canvas_llaves.create_text(
                x_campeon + 8, y_campeon - 6, text=texto_robot, anchor="w",
                fill=color_campeon, font=("Arial", 9, "bold"),
                width=ancho_tarjeta - 16
            )
            canvas_llaves.create_text(
                x_campeon + 8, y_campeon + 10, text=texto_persona or "GANADOR DEL TORNEO",
                anchor="w", fill=color_campeon, font=("Arial", 7),
                width=ancho_tarjeta - 16
            )

        canvas_llaves.configure(
            scrollregion=(
                0,
                0,
                max(ancho_total, ancho_visible),
                max(alto_total + desplazamiento_y, alto_visible)
            )
        )
        return True
    cargar_cuadro_llaves()
