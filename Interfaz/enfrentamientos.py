import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import random



# ============================================================
# BASE DE DATOS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
ruta_bd = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")


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

    # El historial pertenece a una competencia; no debe mezclarse con la nueva.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_batallas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batalla_id INTEGER,
            etapa TEXT,
            grupo TEXT,
            robot1 TEXT,
            robot2 TEXT,
            tiempo TEXT,
            ataques1 INTEGER,
            ataques2 INTEGER,
            ganador TEXT,
            motivo TEXT,
            fecha_registro TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        DELETE FROM historial_batallas
    """)
    # Reinicia también el consecutivo del historial para la nueva competencia.
    cursor.execute("""
        DELETE FROM sqlite_sequence
        WHERE name = 'historial_batallas'
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
    """
    Prioriza grupos de 4 y evita grupos de 5.
    Se usa el menor número de grupos que permite que cada grupo tenga
    como máximo 4 participantes y, para cantidades desde 6, al menos 3.
    La asignación intercalada reparte los sobrantes de forma equilibrada:
    por ejemplo, 10 -> 4, 3, 3; 18 -> 4, 4, 4, 3, 3.
    """
    return (cantidad + 3) // 4


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
    """Pantalla exclusiva para los enfrentamientos de la fase inicial."""
    for widget in contenedor.winfo_children():
        widget.destroy()

    contenido = tk.Frame(contenedor, bg=FONDO)
    contenido.pack(fill="both", expand=True, padx=40, pady=30)

    tk.Label(
        contenido, text="ENFRENTAMIENTOS",
        font=("Arial", 20, "bold"), fg="#8E1B1B", bg=FONDO
    ).pack(anchor="w", pady=(0, 20))

    estilo = ttk.Style()
    estilo.configure(
        "Enfrentamientos.Treeview", font=("Arial", 13), rowheight=42,
        background=BLANCO, foreground=TEXTO, fieldbackground=BLANCO
    )
    estilo.configure(
        "Enfrentamientos.Treeview.Heading",
        font=("Arial", 12, "bold"), foreground=BLANCO, background=ROJO
    )

    marco_botones = tk.Frame(contenido, bg=FONDO)
    marco_botones.pack(fill="x", pady=(0, 15))

    marco_tabla = tk.Frame(
        contenido, bg=BLANCO,
        highlightbackground="#D0D5DA", highlightthickness=1
    )
    marco_tabla.pack(fill="both", expand=True)

    columnas = ("numero", "etapa", "grupo", "robot1", "robot2", "estado")
    tabla = ttk.Treeview(
        marco_tabla, columns=columnas, show="headings",
        style="Enfrentamientos.Treeview"
    )
    for col, titulo, ancho in [
        ("numero", "N.º", 65), ("etapa", "FASE", 160),
        ("grupo", "GRUPO", 145), ("robot1", "ROBOT 1", 230),
        ("robot2", "ROBOT 2", 230), ("estado", "ESTADO", 140)
    ]:
        tabla.heading(col, text=titulo)
        tabla.column(col, width=ancho, anchor="center", stretch=True)

    barra = ttk.Scrollbar(marco_tabla, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=barra.set)
    tabla.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    tabla.tag_configure("completado", background="#DCFCE7", foreground="#166534")
    tabla.tag_configure("pendiente", background="#F1F5F9", foreground="#475569")

    def cargar():
        participantes = obtener_participantes_validos()
        cantidad = len(participantes)
        todas = obtener_enfrentamientos()

        if cantidad == 2:
            etapa_inicial = "Final"
        elif cantidad <= 5:
            etapa_inicial = "Todos"
        else:
            etapa_inicial = "Grupo"

        filas = [fila for fila in todas if fila[1] == etapa_inicial]
        firma = tuple(p[0] for p in participantes)
        tabla.delete(*tabla.get_children())
        # En todos contra todos no hay grupos; se oculta la columna para evitar confusión.
        tabla["displaycolumns"] = (
            ("numero", "etapa", "robot1", "robot2", "estado")
            if etapa_inicial in ("Todos", "Final")
            else columnas
        )

        for numero, etapa, grupo, robot1, robot2, estado_fila in filas:
            if etapa == "Todos":
                fase = "Todos contra todos"
            elif etapa == "Final" and cantidad == 2:
                fase = f"Serie final • Batalla {numero}"
            else:
                fase = etapa
            tabla.insert(
                "", "end",
                values=(numero, fase, grupo or "—", robot1 or "—", robot2 or "—", estado_fila),
                tags=("completado" if estado_fila == "Completado" else "pendiente",)
            )
        return firma, filas

    def reiniciar():
        participantes = obtener_participantes_validos()
        cantidad = len(participantes)
        if cantidad < 2:
            messagebox.showwarning(
                "Participantes insuficientes",
                "Se necesitan al menos 2 participantes válidos.",
                parent=contenedor.winfo_toplevel()
            )
            return
        if not messagebox.askyesno(
            "Reiniciar fase inicial",
            "Se generará de nuevo la fase inicial con los participantes válidos actuales. "
            "Se borrarán los resultados y las eliminatorias existentes. ¿Continuar?",
            parent=contenedor.winfo_toplevel()
        ):
            return
        exito, mensaje = preparar_competencia()
        if exito:
            cargar()
        else:
            messagebox.showwarning(
                "No se pudo reiniciar", mensaje,
                parent=contenedor.winfo_toplevel()
            )

    boton_reiniciar = tk.Button(
        marco_botones, text="REINICIAR FASE INICIAL",
        command=reiniciar, font=("Arial", 11, "bold"),
        bg="#C62828", fg="#FFFFFF",
        activebackground="#8E1B1B", activeforeground="#FFFFFF",
        relief="flat", bd=0, cursor="hand2", padx=18, pady=10
    )
    boton_reiniciar.pack(side="left")
    boton_reiniciar.bind("<Enter>", lambda evento: boton_reiniciar.config(bg="#A91F1F"))
    boton_reiniciar.bind("<Leave>", lambda evento: boton_reiniciar.config(bg="#C62828"))
    boton_reiniciar.bind("<ButtonPress-1>", lambda evento: boton_reiniciar.config(bg="#761616"))
    boton_reiniciar.bind("<ButtonRelease-1>", lambda evento: boton_reiniciar.config(bg="#A91F1F"))

    cargar()

