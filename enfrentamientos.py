import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import random

from .llaves import obtener_tabla_clasificacion, generar_llaves_manualmente, obtener_datos_llaves, generar_final_todos_manualmente


# ============================================================
# BASE DE DATOS
# ============================================================

ruta_bd = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    ),
    "BasesDeDatos",
    "competencia.db"
)


# ============================================================
# COLORES
# ============================================================

FONDO = "#FFFFFF"
BLANCO = "#FFFFFF"
ROJO = "#C62828"
ROJO_OSCURO = "#8E1B1B"
ROJO_CLARO = "#FA7B55"
VERDE = "#02971B"
VERDE_OSCURO = "#025E11"
TEXTO = "#222222"
GRIS = "#666666"


# ============================================================
# CONEXIÓN
# ============================================================

def conectar():
    return sqlite3.connect(ruta_bd)


# ============================================================
# CREAR TABLAS
# ============================================================

def crear_tablas():

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grupos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grupo_participantes (
            grupo_id INTEGER NOT NULL,
            participante_id INTEGER NOT NULL,
            PRIMARY KEY (grupo_id, participante_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enfrentamientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            etapa TEXT NOT NULL,
            grupo_id INTEGER,
            participante1 INTEGER NOT NULL,
            participante2 INTEGER NOT NULL,
            ganador INTEGER,
            estado TEXT DEFAULT 'Pendiente',
            ronda INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clasificacion (
            participante_id INTEGER PRIMARY KEY,
            grupo_id INTEGER,
            combates INTEGER DEFAULT 0,
            victorias INTEGER DEFAULT 0,
            derrotas INTEGER DEFAULT 0,
            puntos INTEGER DEFAULT 0,
            porcentaje REAL DEFAULT 0,
            posicion INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ronda TEXT NOT NULL,
            posicion INTEGER NOT NULL,
            participante1 INTEGER,
            participante2 INTEGER,
            ganador INTEGER,
            estado TEXT DEFAULT 'Pendiente'
        )
    """)

    conexion.commit()
    conexion.close()


crear_tablas()


# ============================================================
# PARTICIPANTES VÁLIDOS
# ============================================================

def obtener_participantes_validos():

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT
            id,
            nombre,
            robot,
            peso,
            cumple_dimensiones,
            tipo_rc,
            interruptor_visible,
            sin_elementos_fijacion,
            sensores_tapados
        FROM participantes
        ORDER BY id
    """)

    participantes = cursor.fetchall()
    conexion.close()

    participantes_validos = []

    for participante in participantes:

        (
            identificacion,
            nombre,
            robot,
            peso,
            dimensiones,
            rc,
            interruptor,
            fijacion,
            sensores
        ) = participante

        try:
            peso_valido = (
                float(peso) > 0
                and float(peso) <= 500
            )
        except:
            peso_valido = False

        cumple = (
            peso_valido
            and dimensiones
            and rc
            and interruptor
            and fijacion
            and sensores
        )

        if cumple:
            participantes_validos.append(participante)

    return participantes_validos


# ============================================================
# LIMPIAR COMPETENCIA ANTERIOR
# ============================================================

def limpiar_competencia_anterior():

    conexion = conectar()
    cursor = conexion.cursor()

    # Elimina todos los enfrentamientos anteriores
    cursor.execute("""
        DELETE FROM enfrentamientos
    """)

    # Reinicia el contador de IDs de enfrentamientos
    cursor.execute("""
    DELETE FROM sqlite_sequence
    WHERE name = 'enfrentamientos'
    """)

    # Elimina clasificación anterior
    cursor.execute("""
        DELETE FROM clasificacion
    """)

    # Elimina llaves anteriores
    cursor.execute("""
        DELETE FROM llaves
    """)

    # Elimina relación de participantes con grupos
    cursor.execute("""
        DELETE FROM grupo_participantes
    """)

    # Elimina los grupos anteriores
    cursor.execute("""
        DELETE FROM grupos
    """)

    conexion.commit()
    conexion.close()


# ============================================================
# CANTIDAD DE CLASIFICADOS
# ============================================================

def cantidad_clasificados(cantidad):

    if cantidad <= 11:
        return 4

    if cantidad <= 23:
        return 8

    if cantidad <= 47:
        return 16

    if cantidad <= 95:
        return 32

    if cantidad <= 191:
        return 64

    return 128


# ============================================================
# CANTIDAD DE GRUPOS
# ============================================================

def cantidad_grupos(cantidad):

    grupos = round(cantidad / 4)

    if grupos < 2:
        grupos = 2

    while cantidad / grupos < 3 and grupos > 1:
        grupos -= 1

    while cantidad / grupos > 5:
        grupos += 1

    return grupos


# ============================================================
# GENERAR GRUPOS
# ============================================================

def generar_grupos():

    participantes = obtener_participantes_validos()
    cantidad = len(participantes)

    if cantidad < 6:
        return False, (
            "No se necesitan grupos para esta cantidad "
            "de participantes."
        )

    grupos_cantidad = cantidad_grupos(cantidad)

    random.shuffle(participantes)

    conexion = conectar()
    cursor = conexion.cursor()

    grupos = []

    for numero in range(1, grupos_cantidad + 1):

        cursor.execute("""
            INSERT INTO grupos (nombre)
            VALUES (?)
        """, (
            f"Grupo {chr(64 + numero)}",
        ))

        grupos.append(cursor.lastrowid)

    for indice, participante in enumerate(participantes):

        grupo = grupos[indice % grupos_cantidad]

        cursor.execute("""
            INSERT INTO grupo_participantes
            (
                grupo_id,
                participante_id
            )
            VALUES (?, ?)
        """, (
            grupo,
            participante[0]
        ))

    conexion.commit()
    conexion.close()

    return True, (
        f"Se generaron {grupos_cantidad} grupos "
        f"con {cantidad} participantes."
    )


# ============================================================
# OBTENER PARTICIPANTES DE UN GRUPO
# ============================================================

def obtener_participantes_grupo(grupo_id):

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT
            p.id,
            p.nombre,
            p.robot
        FROM participantes p
        INNER JOIN grupo_participantes gp
            ON p.id = gp.participante_id
        WHERE gp.grupo_id = ?
        ORDER BY p.id
    """, (
        grupo_id,
    ))

    participantes = cursor.fetchall()

    conexion.close()

    return participantes


# ============================================================
# GENERAR CALENDARIO TODOS CONTRA TODOS
# ============================================================

def generar_calendario(participantes):

    participantes = participantes.copy()

    # Si hay cantidad impar, agregamos un descanso
    if len(participantes) % 2 != 0:
        participantes.append(None)

    cantidad = len(participantes)

    rondas = []

    # Método de rotación
    for numero_ronda in range(cantidad - 1):

        enfrentamientos = []

        for i in range(cantidad // 2):

            participante1 = participantes[i]
            participante2 = participantes[cantidad - 1 - i]

            # Si alguno tiene descanso, no se genera pelea
            if participante1 is not None and participante2 is not None:

                enfrentamientos.append(
                    (
                        participante1[0],
                        participante2[0]
                    )
                )

        rondas.append(enfrentamientos)

        # Mantener el primero fijo y rotar los demás
        participantes = (
            [participantes[0]]
            + [participantes[-1]]
            + participantes[1:-1]
        )

    return rondas


# ============================================================
# GENERAR ENFRENTAMIENTOS DE UN GRUPO
# ============================================================

def generar_enfrentamientos_grupo(grupo_id):

    participantes = obtener_participantes_grupo(grupo_id)

    return generar_calendario(participantes)


# ============================================================
# GENERAR ENFRENTAMIENTOS DE TODOS LOS GRUPOS INTERCALADOS
# ============================================================

def generar_enfrentamientos_grupos():

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id
        FROM grupos
        ORDER BY id
    """)

    grupos = cursor.fetchall()

    conexion.close()

    calendarios = []

    # Generar el calendario de cada grupo
    for grupo in grupos:

        grupo_id = grupo[0]

        rondas = generar_enfrentamientos_grupo(
            grupo_id
        )

        calendarios.append(
            (
                grupo_id,
                rondas
            )
        )

    # ========================================================
    # INTERCALAR RONDAS DE TODOS LOS GRUPOS
    # ========================================================

    conexion = conectar()
    cursor = conexion.cursor()

    cantidad_rondas = 0

    for grupo_id, rondas in calendarios:

        if len(rondas) > cantidad_rondas:
            cantidad_rondas = len(rondas)

    for numero_ronda in range(cantidad_rondas):

        for grupo_id, rondas in calendarios:

            # Algunos grupos pueden tener menos rondas
            if numero_ronda >= len(rondas):
                continue

            enfrentamientos = rondas[numero_ronda]

            for participante1, participante2 in enfrentamientos:

                cursor.execute("""
                    INSERT INTO enfrentamientos
                    (
                        etapa,
                        grupo_id,
                        participante1,
                        participante2,
                        estado,
                        ronda
                    )
                    VALUES (
                        'Grupo',
                        ?,
                        ?,
                        ?,
                        'Pendiente',
                        ?
                    )
                """, (
                    grupo_id,
                    participante1,
                    participante2,
                    numero_ronda + 1
                ))

    conexion.commit()
    conexion.close()

    return True


# ============================================================
# TODOS CONTRA TODOS 3 A 5 PARTICIPANTES
# ============================================================

def generar_todos_contra_todos_pequeno():

    participantes = obtener_participantes_validos()

    cantidad = len(participantes)

    if cantidad < 3 or cantidad > 5:
        return False

    rondas = generar_calendario(participantes)

    conexion = conectar()
    cursor = conexion.cursor()

    for numero_ronda, enfrentamientos in enumerate(
        rondas,
        start=1
    ):

        for participante1, participante2 in enfrentamientos:

            cursor.execute("""
                INSERT INTO enfrentamientos
                (
                    etapa,
                    grupo_id,
                    participante1,
                    participante2,
                    estado,
                    ronda
                )
                VALUES (
                    'Todos',
                    NULL,
                    ?,
                    ?,
                    'Pendiente',
                    ?
                )
            """, (
                participante1,
                participante2,
                numero_ronda
            ))

    conexion.commit()
    conexion.close()

    return True


# ============================================================
# FINAL DIRECTA PARA 2 PARTICIPANTES
# ============================================================

def generar_final_directa():

    participantes = obtener_participantes_validos()

    if len(participantes) != 2:
        return False

    conexion = conectar()
    cursor = conexion.cursor()

    # Se programan las tres batallas de la serie al mejor de tres.
    for numero_batalla in range(1, 4):
        cursor.execute("""
            INSERT INTO enfrentamientos
            (etapa, grupo_id, participante1, participante2, estado, ronda)
            VALUES ('Final', NULL, ?, ?, 'Pendiente', ?)
        """, (
            participantes[0][0],
            participantes[1][0],
            numero_batalla
        ))

    conexion.commit()
    conexion.close()
    return True


# ============================================================
# PREPARAR COMPETENCIA
# ============================================================

def preparar_competencia():

    participantes = obtener_participantes_validos()

    cantidad = len(participantes)

    if cantidad < 2:

        return False, (
            "Se necesitan al menos 2 participantes "
            "que cumplan el reglamento."
        )

    # IMPORTANTE:
    # Primero se borra TODO lo generado anteriormente.
    limpiar_competencia_anterior()

    # --------------------------------------------
    # 2 PARTICIPANTES
    # --------------------------------------------

    if cantidad == 2:

        generar_final_directa()

        return True, (
            "Se generó la final directa."
        )

    # --------------------------------------------
    # 3 A 5 PARTICIPANTES
    # --------------------------------------------

    if cantidad <= 5:

        generar_todos_contra_todos_pequeno()

        return True, (
            "Se generó la fase todos contra todos."
        )

    # --------------------------------------------
    # 6 O MÁS PARTICIPANTES
    # --------------------------------------------

    generar_grupos()
    generar_enfrentamientos_grupos()

    return True, (
        "Se generaron los grupos y sus enfrentamientos."
    )


# ============================================================
# OBTENER ENFRENTAMIENTOS
# ============================================================

def obtener_enfrentamientos():

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT
            e.id,
            e.etapa,
            COALESCE(g.nombre, ''),
            p1.robot,
            p2.robot,
            e.estado
        FROM enfrentamientos e
        INNER JOIN participantes p1
            ON e.participante1 = p1.id
        INNER JOIN participantes p2
            ON e.participante2 = p2.id
        LEFT JOIN grupos g
            ON e.grupo_id = g.id
        ORDER BY e.id
    """)

    resultados = cursor.fetchall()

    conexion.close()

    return resultados


# ============================================================
# INTERFAZ
# ============================================================

def mostrar_enfrentamientos(contenedor):

    estilo = ttk.Style()

    # --------------------------------------------------------
    # BOTÓN
    # --------------------------------------------------------

    estilo.configure(
        "Generar.TButton",
        font=("Arial", 12, "bold"),
        foreground=BLANCO,
        background=VERDE,
        padding=(20, 10)
    )

    estilo.map(
        "Generar.TButton",
        background=[
            ("active", VERDE_OSCURO),
            ("pressed", VERDE_OSCURO)
        ]
    )

    # --------------------------------------------------------
    # TABLA
    # --------------------------------------------------------

    estilo.configure(
        "Treeview",
        font=("Arial", 15),
        rowheight=44,
        background=BLANCO,
        foreground=TEXTO,
        fieldbackground=BLANCO
    )

    estilo.configure(
        "Treeview.Heading",
        font=("Arial", 14, "bold"),
        foreground=BLANCO,
        background=ROJO
    )

    estilo.map(
        "Treeview",
        background=[
            ("selected", ROJO_CLARO)
        ],
        foreground=[
            ("selected", "black")
        ]
    )

    # --------------------------------------------------------
    # CONTENEDOR PRINCIPAL
    # --------------------------------------------------------

    contenido = tk.Frame(
        contenedor,
        bg=FONDO
    )

    contenido.pack(
        fill="both",
        expand=True,
        padx=40,
        pady=30
    )

    # --------------------------------------------------------
    # TÍTULO
    # --------------------------------------------------------

    tk.Label(
        contenido,
        text="ENFRENTAMIENTOS",
        font=("Arial", 18, "bold"),
        fg="#000000",
        bg=FONDO
    ).pack(
        anchor="w",
        pady=(0, 20)
    )

    # --------------------------------------------------------
    # BOTÓN
    # --------------------------------------------------------

    marco_botones = tk.Frame(
        contenido,
        bg=FONDO
    )

    marco_botones.pack(
        fill="x",
        pady=(0, 15)
    )

    boton_preparar = ttk.Button(
        marco_botones,
        text="PREPARAR COMPETENCIA",
        command=lambda: preparar(),
        style="Generar.TButton"
    )

    boton_preparar.pack(
        side="left"
    )

    # --------------------------------------------------------
    # TABLA
    # --------------------------------------------------------

    marco_tabla = tk.Frame(
        contenido,
        bg=BLANCO,
        highlightbackground="#D0D5DA",
        highlightthickness=1
    )

    marco_tabla.pack(
        fill="both",
        expand=True
    )

    tabla = ttk.Treeview(
        marco_tabla,
        show="headings"
    )

    scrollbar = ttk.Scrollbar(
        marco_tabla,
        orient="vertical",
        command=tabla.yview
    )

    tabla.configure(
        yscrollcommand=scrollbar.set
    )

    tabla.pack(
        side="left",
        fill="both",
        expand=True
    )

    scrollbar.pack(
        side="right",
        fill="y"
    )

    # Cuadro eliminatorio visual, separado de la tabla de enfrentamientos.
    marco_llaves = tk.Frame(marco_tabla, bg=BLANCO)
    canvas_llaves = tk.Canvas(marco_llaves, bg=BLANCO, highlightthickness=0)
    scroll_y_llaves = ttk.Scrollbar(marco_llaves, orient="vertical", command=canvas_llaves.yview)
    scroll_x_llaves = ttk.Scrollbar(marco_llaves, orient="horizontal", command=canvas_llaves.xview)
    canvas_llaves.configure(yscrollcommand=scroll_y_llaves.set, xscrollcommand=scroll_x_llaves.set)
    canvas_llaves.grid(row=0, column=0, sticky="nsew")
    scroll_y_llaves.grid(row=0, column=1, sticky="ns")
    scroll_x_llaves.grid(row=1, column=0, sticky="ew")
    marco_llaves.grid_rowconfigure(0, weight=1)
    marco_llaves.grid_columnconfigure(0, weight=1)

    def mostrar_tabla():
        marco_llaves.pack_forget()
        if not tabla.winfo_manager():
            tabla.pack(side="left", fill="both", expand=True)
        if not scrollbar.winfo_manager():
            scrollbar.pack(side="right", fill="y")

    def cargar_cuadro_llaves():
        rondas = obtener_datos_llaves()
        if not rondas:
            return False

        tabla.pack_forget()
        scrollbar.pack_forget()
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
        canvas_llaves.xview_moveto(0)
        canvas_llaves.yview_moveto(0)
        return True

    # Botón para generar llaves manualmente después de revisar la clasificación.
    boton_llaves = ttk.Button(
        marco_botones, text="GENERAR LLAVES",
        command=lambda: generar_llaves(), style="Generar.TButton",
        state="disabled"
    )
    boton_llaves.pack(side="left", padx=(12, 0))

    def estado_fase_grupos():
        conexion = conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo' AND estado != 'Completado'")
        pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM llaves")
        hay_llaves = cursor.fetchone()[0] > 0
        conexion.close()
        return total > 0 and pendientes == 0, hay_llaves

    def configurar_tabla(columnas, encabezados, anchos):
        tabla.delete(*tabla.get_children())
        tabla["columns"] = columnas
        for columna, titulo in zip(columnas, encabezados):
            tabla.heading(columna, text=titulo)
            tabla.column(columna, width=anchos.get(columna, 130), anchor="center", stretch=True)

    def cargar_clasificacion():
        filas = obtener_tabla_clasificacion()
        if filas is None:
            return False

        cantidad_participantes = len(obtener_participantes_validos())
        if 3 <= cantidad_participantes <= 5:
            # En todos contra todos no hay grupos: se omite esa columna.
            columnas = ("Posición", "Robot", "Puntos", "Tiempo promedio", "% Ataques", "% Victorias")
            configurar_tabla(
                columnas,
                ("POS.", "ROBOT", "PUNTOS", "TIEMPO PROM.", "% ATAQUES", "% VICTORIAS"),
                {"Posición": 70, "Robot": 240, "Puntos": 110, "Tiempo promedio": 170, "% Ataques": 145, "% Victorias": 145}
            )
        else:
            columnas = ("Posición", "Robot", "Grupo", "Puntos", "Tiempo promedio", "% Ataques", "% Victorias")
            configurar_tabla(
                columnas,
                ("POS.", "ROBOT", "GRUPO", "PUNTOS", "TIEMPO PROM.", "% ATAQUES", "% VICTORIAS"),
                {"Posición": 70, "Robot": 220, "Grupo": 140, "Puntos": 110, "Tiempo promedio": 170, "% Ataques": 145, "% Victorias": 145}
            )

        tabla.tag_configure("clasifica", background="#DCFCE7", foreground="#166534")
        tabla.tag_configure("eliminado", background="#FEE2E2", foreground="#991B1B")
        for fila in filas:
            if 3 <= cantidad_participantes <= 5:
                valores = (
                    f'{fila["posicion_grupo"]}°', fila["robot"],
                    fila["puntos"], fila["tiempo_mostrar"],
                    f'{fila["porcentaje_ataques"]:.1f}%',
                    f'{fila["porcentaje_victorias"]:.1f}%'
                )
            else:
                valores = (
                    f'{fila["posicion_grupo"]}°', fila["robot"], fila["grupo"],
                    fila["puntos"], fila["tiempo_mostrar"],
                    f'{fila["porcentaje_ataques"]:.1f}%',
                    f'{fila["porcentaje_victorias"]:.1f}%'
                )
            tabla.insert(
                "", "end",
                values=valores,
                tags=("clasifica" if fila["clasifica"] else "eliminado",)
            )
        return True

    def estado_fase_todos():
        conexion = conectar()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos' AND estado != 'Completado'")
            pendientes = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
            finales = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final' AND estado != 'Completado'")
            finales_pendientes = cursor.fetchone()[0]
            return total > 0 and pendientes == 0, finales > 0, finales_pendientes
        finally:
            conexion.close()

    def cargar_enfrentamientos():
        participantes = obtener_participantes_validos()
        cantidad = len(participantes)
        grupos_terminados, hay_llaves = estado_fase_grupos()
        todos_terminados, hay_final, finales_pendientes = estado_fase_todos()

        # Mostrar clasificación al terminar grupos (6+) o todos contra todos (3–5).
        if cantidad >= 6 and grupos_terminados and not hay_llaves:
            mostrar_tabla()
            if cargar_clasificacion():
                boton_llaves.configure(state="normal", text="GENERAR LLAVES")
                return
        if 3 <= cantidad <= 5 and todos_terminados and not hay_final:
            mostrar_tabla()
            if cargar_clasificacion():
                boton_llaves.configure(state="normal", text="GENERAR FINAL")
                return

        enfrentamientos = obtener_enfrentamientos()

        if hay_llaves:
            # Mostrar el cuadro tradicional conectado en lugar de una tabla plana.
            if cargar_cuadro_llaves():
                boton_llaves.configure(state="disabled", text="LLAVES EN CURSO")
                return
            mostrar_tabla()
            boton_llaves.configure(state="disabled", text="LLAVES EN CURSO")

        elif cantidad <= 5 and todos_terminados and hay_final:
            # Para 3–5 participantes, ocultar el todos-contra-todos una vez finalizado
            # y dejar visible la final entre los dos mejores.
            enfrentamientos = [fila for fila in enfrentamientos if fila[1] == "Final"]
            columnas = ("ID", "Etapa", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "ETAPA", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Etapa": 170, "Robot 1": 320, "Robot 2": 320, "Estado": 180}
            )
            boton_llaves.configure(state="disabled", text="NO SE REQUIEREN LLAVES")

        elif cantidad == 2:
            # La final directa tiene tres combates programados para la serie al mejor de tres.
            enfrentamientos = [fila for fila in enfrentamientos if fila[1] == "Final"]
            columnas = ("ID", "Etapa", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "ETAPA / BATALLA", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Etapa": 170, "Robot 1": 320, "Robot 2": 320, "Estado": 180}
            )
            boton_llaves.configure(state="disabled", text="MEJOR DE 3")

        elif cantidad >= 6:
            columnas = ("ID", "Grupo", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "GRUPO", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Grupo": 150, "Robot 1": 280, "Robot 2": 280, "Estado": 170}
            )
            boton_llaves.configure(state="disabled", text="GENERAR LLAVES")

        else:
            columnas = ("ID", "Etapa", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "ETAPA", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Etapa": 170, "Robot 1": 320, "Robot 2": 320, "Estado": 180}
            )
            boton_llaves.configure(state="disabled", text="NO SE REQUIEREN LLAVES")

        mostrar_tabla()
        for fila in enfrentamientos:
            id_batalla, etapa, grupo, robot1, robot2, estado = fila
            if hay_llaves:
                valores = (id_batalla, etapa, robot1, robot2, estado)
            elif cantidad >= 6:
                valores = (id_batalla, grupo, robot1, robot2, estado)
            else:
                etapa_mostrar = "Todos v Todos" if etapa == "Todos" else etapa
                valores = (id_batalla, etapa_mostrar, robot1, robot2, estado)
            tabla.insert("", "end", values=valores)

    def generar_llaves():
        participantes_actuales = obtener_participantes_validos()
        if 3 <= len(participantes_actuales) <= 5:
            exito, mensaje = generar_final_todos_manualmente()
            if exito:
                messagebox.showinfo("Final generada", mensaje, parent=contenedor.winfo_toplevel())
                cargar_enfrentamientos()
            else:
                messagebox.showwarning("No se pudo generar la final", mensaje, parent=contenedor.winfo_toplevel())
            return

        if obtener_datos_llaves():
            # La regeneración manual de llaves queda deshabilitada para evitar
            # borrar accidentalmente resultados de una fase eliminatoria.
            messagebox.showinfo(
                "Llaves ya generadas",
                "Las llaves eliminatorias ya están generadas.",
                parent=contenedor.winfo_toplevel()
            )
            return

        confirmar = messagebox.askyesno(
            "Generar llaves",
            "Se calcularán los clasificados y se crearán los enfrentamientos de la primera ronda. ¿Continuar?",
            parent=contenedor.winfo_toplevel()
        )
        if not confirmar:
            return
        exito, mensaje = generar_llaves_manualmente()
        if exito:
            messagebox.showinfo("Llaves generadas", mensaje, parent=contenedor.winfo_toplevel())
            cargar_enfrentamientos()
        else:
            messagebox.showwarning("No se pudieron generar", mensaje, parent=contenedor.winfo_toplevel())

    def preparar():
        participantes = obtener_participantes_validos()
        cantidad = len(participantes)
        if cantidad < 2:
            messagebox.showwarning(
                "Participantes insuficientes",
                "Se necesitan al menos 2 participantes que cumplan todos los requisitos.",
                parent=contenedor.winfo_toplevel()
            )
            return
        confirmar = messagebox.askyesno(
            "Preparar competencia",
            f"Hay {cantidad} participantes válidos.\n\nSe generará nuevamente la estructura de enfrentamientos y se borrarán los resultados anteriores.\n\n¿Deseas continuar?",
            parent=contenedor.winfo_toplevel()
        )
        if not confirmar:
            return
        exito, mensaje = preparar_competencia()
        if exito:
            cargar_enfrentamientos()
            total = len(obtener_enfrentamientos())
            messagebox.showinfo(
                "Competencia preparada",
                f"{mensaje}\n\nEnfrentamientos generados: {total}",
                parent=contenedor.winfo_toplevel()
            )
        else:
            messagebox.showwarning("No se pudo preparar", mensaje, parent=contenedor.winfo_toplevel())

    cargar_enfrentamientos()
