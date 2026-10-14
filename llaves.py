"""Generación progresiva de llaves eliminatorias para MiniSumos RC.

No modifica la generación de grupos ni el calendario inicial. Las rondas
eliminatorias se guardan en las tablas existentes de enfrentamientos y llaves.
"""
import os
import sqlite3
from functools import cmp_to_key

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_BD = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")
ETAPAS_INICIALES = ("Grupo", "Todos")


def conectar():
    return sqlite3.connect(RUTA_BD)


def _cantidad_clasificados(cantidad):
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


def _nombre_ronda(cantidad_participantes):
    nombres = {
        2: "Final",
        4: "Semifinal",
        8: "Cuartos de final",
        16: "Octavos de final",
        32: "Dieciseisavos de final",
        64: "Treintaidosavos de final",
        128: "Sesentaicuatroavos de final",
    }
    return nombres.get(cantidad_participantes, "Ronda eliminatoria")


def _orden_siembra(cantidad):
    """Orden clásico: 1 vs N, N/2 vs N/2+1, etc."""
    orden = [1, 2]
    while len(orden) < cantidad:
        limite = len(orden) * 2 + 1
        orden = [semilla for anterior in orden
                 for semilla in (anterior, limite - anterior)]
    return orden


def _comparar(a, b, enfrentamientos_directos):
    # Cada registro contiene id, grupo, victorias, combates, porcentaje.
    if a["victorias"] != b["victorias"]:
        return -1 if a["victorias"] > b["victorias"] else 1
    if a["porcentaje"] != b["porcentaje"]:
        return -1 if a["porcentaje"] > b["porcentaje"] else 1

    ganador_directo = enfrentamientos_directos.get(
        frozenset((a["id"], b["id"]))
    )
    if ganador_directo == a["id"]:
        return -1
    if ganador_directo == b["id"]:
        return 1
    return -1 if a["id"] < b["id"] else (1 if a["id"] > b["id"] else 0)


def _obtener_clasificados(cursor):
    cursor.execute("""
        SELECT etapa, grupo_id, participante1, participante2, ganador, estado
        FROM enfrentamientos
        WHERE etapa IN ('Grupo', 'Todos')
        ORDER BY id
    """)
    iniciales = cursor.fetchall()
    if not iniciales or any(fila[5] != "Completado" for fila in iniciales):
        return None

    # En un todos-contra-todos pequeño, avanzan los dos mejores.
    etapas = {fila[0] for fila in iniciales}
    stats = {}
    directos = {}
    grupos_participantes = {}

    cursor.execute("""
        SELECT grupo_id, participante_id
        FROM grupo_participantes
    """)
    for grupo_id, participante_id in cursor.fetchall():
        grupos_participantes[participante_id] = grupo_id

    for etapa, grupo_id, p1, p2, ganador, estado in iniciales:
        for participante in (p1, p2):
            registro = stats.setdefault(participante, {
                "id": participante,
                "grupo": grupo_id if etapa == "Grupo" else None,
                "victorias": 0,
                "combates": 0,
                "porcentaje": 0.0,
            })
            registro["combates"] += 1
            if etapa == "Grupo":
                registro["grupo"] = grupo_id
        if ganador in (p1, p2):
            stats[ganador]["victorias"] += 1
            directos[frozenset((p1, p2))] = ganador

    for registro in stats.values():
        registro["porcentaje"] = (
            registro["victorias"] / registro["combates"]
            if registro["combates"] else 0.0
        )

    if etapas == {"Todos"}:
        clasificados = sorted(
            stats.values(),
            key=cmp_to_key(lambda a, b: _comparar(a, b, directos))
        )
        return [(r["id"], None) for r in clasificados[:2]]

    # Fase por grupos: ordenar primero dentro de cada grupo. Después,
    # comparar a los participantes por posición de grupo y rendimiento.
    por_grupo = {}
    for participante, registro in stats.items():
        grupo_id = registro["grupo"]
        if grupo_id is not None:
            por_grupo.setdefault(grupo_id, []).append(registro)

    ranking = []
    for grupo_id, miembros in por_grupo.items():
        miembros.sort(key=cmp_to_key(
            lambda a, b: _comparar(a, b, directos)
        ))
        for posicion, registro in enumerate(miembros, start=1):
            ranking.append({
                "id": registro["id"],
                "grupo": grupo_id,
                "posicion_grupo": posicion,
                "victorias": registro["victorias"],
                "porcentaje": registro["porcentaje"],
            })

    ranking.sort(key=lambda r: (
        r["posicion_grupo"],
        -r["porcentaje"],
        -r["victorias"],
        r["id"],
    ))

    cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
    cantidad = cursor.fetchone()[0]
    cantidad = min(_cantidad_clasificados(cantidad), len(ranking))
    return [(r["id"], r["grupo"]) for r in ranking[:cantidad]]


def _emparejar_primera_ronda(clasificados):
    cantidad = len(clasificados)
    orden = _orden_siembra(cantidad)
    participantes = [clasificados[semilla - 1] for semilla in orden]

    def conflictos():
        return sum(
            1 for i in range(0, len(participantes), 2)
            if participantes[i][1] is not None
            and participantes[i][1] == participantes[i + 1][1]
        )

    # Mantener el cuadro de siembra clásico e intentar evitar que dos
    # robots del mismo grupo se enfrenten en la primera ronda.
    for i in range(0, len(participantes), 2):
        if (participantes[i][1] is None
                or participantes[i][1] != participantes[i + 1][1]):
            continue
        mejor_conflicto = conflictos()
        mejor_intercambio = None
        for j in range(i + 2, len(participantes), 2):
            participantes[i + 1], participantes[j + 1] = (
                participantes[j + 1], participantes[i + 1]
            )
            nuevos = conflictos()
            if nuevos < mejor_conflicto:
                mejor_conflicto = nuevos
                mejor_intercambio = j
            participantes[i + 1], participantes[j + 1] = (
                participantes[j + 1], participantes[i + 1]
            )
        if mejor_intercambio is not None:
            j = mejor_intercambio
            participantes[i + 1], participantes[j + 1] = (
                participantes[j + 1], participantes[i + 1]
            )

    return [
        (participantes[i][0], participantes[i + 1][0])
        for i in range(0, len(participantes), 2)
    ]


def _crear_cuadro_inicial(cursor, clasificados):
    parejas = _emparejar_primera_ronda(clasificados)
    cantidad = len(clasificados)
    if not parejas:
        return

    # Crear las casillas de todas las rondas para que el cuadro pueda
    # representarse visualmente más adelante.
    tamano_ronda = cantidad
    while tamano_ronda >= 2:
        nombre = _nombre_ronda(tamano_ronda)
        for posicion in range(1, tamano_ronda // 2 + 1):
            p1 = p2 = None
            if tamano_ronda == cantidad:
                p1, p2 = parejas[posicion - 1]
            cursor.execute("""
                INSERT INTO llaves
                    (ronda, posicion, participante1, participante2, estado)
                VALUES (?, ?, ?, ?, 'Pendiente')
            """, (nombre, posicion, p1, p2))
        tamano_ronda //= 2

    etapa = _nombre_ronda(cantidad)
    for p1, p2 in parejas:
        cursor.execute("""
            INSERT INTO enfrentamientos
                (etapa, grupo_id, participante1, participante2, estado, ronda)
            VALUES (?, NULL, ?, ?, 'Pendiente', 1)
        """, (etapa, p1, p2))


def _sincronizar_resultados_llaves(cursor):
    cursor.execute("""
        SELECT DISTINCT ronda
        FROM llaves
    """)
    etapas = [fila[0] for fila in cursor.fetchall()]
    for etapa in etapas:
        cursor.execute("""
            SELECT ganador, estado
            FROM enfrentamientos
            WHERE etapa = ?
            ORDER BY id
        """, (etapa,))
        combates = cursor.fetchall()
        for posicion, (ganador, estado) in enumerate(combates, start=1):
            cursor.execute("""
                UPDATE llaves
                SET ganador = ?, estado = ?
                WHERE ronda = ? AND posicion = ?
            """, (
                ganador,
                "Completado" if estado == "Completado" else estado,
                etapa,
                posicion,
            ))


def _avanzar_ronda(cursor):
    cursor.execute("""
        SELECT ronda, COUNT(*)
        FROM llaves
        GROUP BY ronda
    """)
    rondas = sorted(cursor.fetchall(), key=lambda fila: fila[1], reverse=True)
    if len(rondas) < 2:
        return

    etapas_ordenadas = [fila[0] for fila in rondas]
    for indice, etapa in enumerate(etapas_ordenadas[:-1]):
        cursor.execute("""
            SELECT id, ganador, estado
            FROM enfrentamientos
            WHERE etapa = ?
            ORDER BY id
        """, (etapa,))
        combates = cursor.fetchall()
        if not combates or any(estado != "Completado" or ganador is None
                               for _, ganador, estado in combates):
            continue

        siguiente_etapa = etapas_ordenadas[indice + 1]
        cursor.execute("""
            SELECT COUNT(*)
            FROM enfrentamientos
            WHERE etapa = ?
        """, (siguiente_etapa,))
        if cursor.fetchone()[0] > 0:
            continue

        ganadores = [ganador for _, ganador, _ in combates]
        parejas = [
            (ganadores[i], ganadores[i + 1])
            for i in range(0, len(ganadores), 2)
        ]
        for posicion, (p1, p2) in enumerate(parejas, start=1):
            cursor.execute("""
                UPDATE llaves
                SET participante1 = ?, participante2 = ?, estado = 'Pendiente'
                WHERE ronda = ? AND posicion = ?
            """, (p1, p2, siguiente_etapa, posicion))
            cursor.execute("""
                INSERT INTO enfrentamientos
                    (etapa, grupo_id, participante1, participante2, estado, ronda)
                VALUES (?, NULL, ?, ?, 'Pendiente', ?)
            """, (siguiente_etapa, p1, p2, indice + 2))
        break


def actualizar_llaves_tras_resultado():
    conexion = conectar()
    cursor = conexion.cursor()
    try:
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
        cursor.execute("""
            SELECT COUNT(*)
            FROM enfrentamientos
            WHERE etapa IN ('Grupo', 'Todos')
        """)
        total_iniciales = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM llaves")
        total_llaves = cursor.fetchone()[0]

        if total_iniciales:
            cursor.execute("""
                SELECT COUNT(*)
                FROM enfrentamientos
                WHERE etapa IN ('Grupo', 'Todos')
                  AND estado != 'Completado'
            """)
            pendientes = cursor.fetchone()[0]
            if pendientes:
                conexion.close()
                return

            if total_llaves == 0:
                clasificados = _obtener_clasificados(cursor)
                if clasificados and len(clasificados) >= 2:
                    _crear_cuadro_inicial(cursor, clasificados)
                    conexion.commit()
                conexion.close()
                return

        # Una final directa para dos participantes no necesita generar
        # una segunda fase: no tiene encuentros iniciales ni casillas.
        if total_llaves:
            _sincronizar_resultados_llaves(cursor)
            _avanzar_ronda(cursor)
            conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        try:
            conexion.close()
        except Exception:
            pass
