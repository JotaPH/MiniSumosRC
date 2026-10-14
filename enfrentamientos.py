import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import random

from .llaves import obtener_tabla_clasificacion, generar_llaves_manualmente


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

    # ========================================================
    # CONFIGURAR TABLA SEGÚN LA CANTIDAD
    # ========================================================

    def configurar_columnas(cantidad):

        tabla.delete(*tabla.get_children())

        if cantidad >= 6:

            columnas = (
                "ID",
                "Grupo",
                "Robot 1",
                "Robot 2",
                "Estado"
            )

            tabla["columns"] = columnas

            encabezados = {
                "ID": "ID",
                "Grupo": "GRUPO",
                "Robot 1": "ROBOT 1",
                "Robot 2": "ROBOT 2",
                "Estado": "ESTADO"
            }

            for columna, texto in encabezados.items():

                tabla.heading(
                    columna,
                    text=texto
                )

            tabla.column(
            "ID",
            width=70,
            anchor="center"
            )
            

            tabla.column(
                "Grupo",
                width=150,
                anchor="center"
            )

            tabla.column(
                "Robot 1",
                width=280,
                anchor="center"
            )

            tabla.column(
                "Robot 2",
                width=280,
                anchor="center"
            )

            tabla.column(
                "Estado",
                width=170,
                anchor="center"
            )

        else:

            columnas = (
                "ID",
                "Etapa",
                "Robot 1",
                "Robot 2",
                "Estado"
            )

            tabla["columns"] = columnas

            encabezados = {
                "ID": "ID",
                "Etapa": "ETAPA",
                "Robot 1": "ROBOT 1",
                "Robot 2": "ROBOT 2",
                "Estado": "ESTADO"
            }

            for columna, texto in encabezados.items():

                tabla.heading(
                    columna,
                    text=texto
                )

            tabla.column(
                "ID",
                width=70,
                anchor="center"
            )

            tabla.column(
                "Etapa",
                width=170,
                anchor="center"
            )

            tabla.column(
                "Robot 1",
                width=320,
                anchor="center"
            )

            tabla.column(
                "Robot 2",
                width=320,
                anchor="center"
            )

            tabla.column(
                "Estado",
                width=180,
                anchor="center"
            )

    # Botón que solo se habilita cuando todos los grupos terminan.
    boton_llaves = ttk.Button(
        marco_botones,
        text="GENERAR LLAVES",
        command=lambda: generar_llaves(),
        style="Generar.TButton",
        state="disabled"
    )
    boton_llaves.pack(side="left", padx=(12, 0))

    # ========================================================
    # CARGAR ENFRENTAMIENTOS O CLASIFICACIÓN
    # ========================================================

    def estado_fase_grupos():
        conexion = conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
        total = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM enfrentamientos
            WHERE etapa = 'Grupo' AND estado != 'Completado'
        """)
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
            tabla.column(
                columna,
                width=anchos.get(columna, 130),
                anchor="center",
                stretch=True
            )

    def cargar_clasificacion():
        filas = obtener_tabla_clasificacion()
        if filas is None:
            return False

        columnas = (
            "Posición", "Robot", "Grupo", "Puntos",
            "Tiempo promedio", "% Ataques", "% Victorias", "Estado"
        )
        configurar_tabla(
            columnas,
            ("POS.", "ROBOT", "GRUPO", "PUNTOS", "TIEMPO PROM.", "% ATAQUES", "% VICTORIAS", "CLASIFICACIÓN"),
            {
                "Posición": 70, "Robot": 190, "Grupo": 110,
                "Puntos": 90, "Tiempo promedio": 135,
                "% Ataques": 115, "% Victorias": 120, "Estado": 145
            }
        )
        tabla.tag_configure("clasifica", background="#DCFCE7", foreground="#166534")
        tabla.tag_configure("eliminado", background="#FEE2E2", foreground="#991B1B")

        for fila in filas:
            tabla.insert(
                "", "end",
                values=(
                    f'{fila["posicion_grupo"]}°',
                    fila["robot"],
                    fila["grupo"],
                    fila["puntos"],
                    fila["tiempo_mostrar"],
                    f'{fila["porcentaje_ataques"]:.1f}%',
                    f'{fila["porcentaje_victorias"]:.1f}%',
                    "CLASIFICA" if fila["clasifica"] else "NO CLASIFICA"
                ),
                tags=("clasifica" if fila["clasifica"] else "eliminado",)
            )
        return True

    def cargar_enfrentamientos():
        participantes = obtener_participantes_validos()
        cantidad = len(participantes)
        grupos_terminados, hay_llaves = estado_fase_grupos()

        # Terminada la fase de grupos, primero se muestra la clasificación.
        if grupos_terminados and not hay_llaves:
            tk.Label(
                contenido,
                text="CLASIFICACIÓN Y ESTADÍSTICAS",
                font=("Arial", 14, "bold"),
                fg=TEXTO,
                bg=FONDO
            ).pack(anchor="w", pady=(0, 8))
            if cargar_clasificacion():
                boton_llaves.configure(state="normal")
                return

        # Si ya se generaron llaves, se muestran solo los combates eliminatorios.
        enfrentamientos = obtener_enfrentamientos()
        if hay_llaves:
            enfrentamientos = [
                e for e in enfrentamientos
                if e[1] not in ("Grupo", "Todos")
            ]

        if hay_llaves:
            columnas = ("ID", "Ronda", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "RONDA", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Ronda": 200, "Robot 1": 260, "Robot 2": 260, "Estado": 150}
            )
        elif cantidad >= 6:
            columnas = ("ID", "Grupo", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "GRUPO", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Grupo": 150, "Robot 1": 280, "Robot 2": 280, "Estado": 170}
            )
        else:
            columnas = ("ID", "Etapa", "Robot 1", "Robot 2", "Estado")
            configurar_tabla(
                columnas, ("ID", "ETAPA", "ROBOT 1", "ROBOT 2", "ESTADO"),
                {"ID": 70, "Etapa": 170, "Robot 1": 320, "Robot 2": 320, "Estado": 180}
            )

        for e in enfrentamientos:
            id_batalla, etapa, grupo, robot1, robot2, estado = e
            if hay_llaves:
                valores = (id_batalla, etapa, robot1, robot2, estado)
            elif cantidad >= 6:
                valores = (id_batalla, grupo, robot1, robot2, estado)
            else:
                valores = (id_batalla, etapa, robot1, robot2, estado)
            tabla.insert("", "end", values=valores)

        boton_llaves.configure(
            state="disabled",
            text="LLAVES GENERADAS" if hay_llaves else "GENERAR LLAVES"
        )

    def generar_llaves():
        confirmar = messagebox.askyesno(
            "Generar llaves",
            "Se calcularán los clasificados según las estadísticas y se crearán los enfrentamientos de la primera ronda. ¿Continuar?",
            parent=contenedor.winfo_toplevel()
        )
        if not confirmar:
            return
        exito, mensaje = generar_llaves_manualmente()
        if exito:
            messagebox.showinfo("Llaves generadas", mensaje, parent=contenedor.winfo_toplevel())
            # El contenido se redibuja para retirar el encabezado de clasificación.
            for widget in contenido.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget("text") == "CLASIFICACIÓN Y ESTADÍSTICAS":
                    widget.destroy()
            cargar_enfrentamientos()
        else:
            messagebox.showwarning("No se pudieron generar", mensaje, parent=contenedor.winfo_toplevel())


    def cargar_enfrentamientos():

        participantes = obtener_participantes_validos()

        cantidad = len(participantes)

        configurar_columnas(cantidad)

        enfrentamientos = obtener_enfrentamientos()

        for enfrentamiento in enfrentamientos:

            id_enfrentamiento, etapa, grupo, robot1, robot2, estado = enfrentamiento

            if cantidad >= 6:

                valores = (
                    id_enfrentamiento,
                    grupo,
                    robot1,
                    robot2,
                    estado
                )

            else:

                valores = (
                    id_enfrentamiento,
                    etapa,
                    robot1,
                    robot2,
                    estado
                )

            tabla.insert(
                "",
                "end",
                values=valores
            )

    # ========================================================
    # PREPARAR
    # ========================================================

    def preparar():

        participantes = obtener_participantes_validos()

        cantidad = len(participantes)

        if cantidad < 2:

            messagebox.showwarning(
                "Participantes insuficientes",
                (
                    "Se necesitan al menos 2 participantes "
                    "que cumplan todos los requisitos."
                )
            )

            return

        confirmar = messagebox.askyesno(
            "Preparar competencia",
            (
                f"Hay {cantidad} participantes válidos.\n\n"
                "Se generará nuevamente la estructura "
                "de enfrentamientos.\n\n"
                "¿Deseas continuar?"
            )
        )

        if not confirmar:
            return

        exito, mensaje = preparar_competencia()

        if exito:

            cargar_enfrentamientos()

            total = len(
                obtener_enfrentamientos()
            )

            messagebox.showinfo(
                "Competencia preparada",
                (
                    f"{mensaje}\n\n"
                    f"Enfrentamientos generados: {total}"
                )
            )

        else:

            messagebox.showwarning(
                "No se pudo preparar",
                mensaje
            )

    # ========================================================
    # CARGA INICIAL
    # ========================================================

    cargar_enfrentamientos()
