"""Clasificación estadística y gestión manual de llaves para MiniSumos RC."""
import os
import sqlite3
from functools import cmp_to_key

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_BD = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")


def conectar():
    return sqlite3.connect(RUTA_BD)


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


def nombre_ronda(cantidad):
    return {
        2: "Final",
        4: "Semifinal",
        8: "Cuartos de final",
        16: "Octavos de final",
        32: "Dieciseisavos de final",
        64: "Treintaidosavos de final",
        128: "Sesentaicuatroavos de final",
    }.get(cantidad, "Ronda eliminatoria")


def _tiempo_a_segundos(valor):
    """Convierte MM:SS o HH:MM:SS a segundos; tiempos vacíos quedan sin dato."""
    if valor is None:
        return None
    try:
        partes = [int(p) for p in str(valor).strip().split(":")]
        if len(partes) == 2:
            return partes[0] * 60 + partes[1]
        if len(partes) == 3:
            return partes[0] * 3600 + partes[1] * 60 + partes[2]
    except (TypeError, ValueError):
        return None
    return None


def _segundos_a_tiempo(segundos):
    if segundos is None:
        return "—"
    segundos = int(round(segundos))
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


def _estadisticas(cursor):
    cursor.execute("""
        SELECT e.id, e.etapa, e.grupo_id, e.participante1, e.participante2,
               e.ganador, e.estado, e.tiempo,
               COALESCE(e.ataques1, 0), COALESCE(e.ataques2, 0),
               p1.robot, p2.robot, COALESCE(g.nombre, '')
        FROM enfrentamientos e
        JOIN participantes p1 ON p1.id = e.participante1
        JOIN participantes p2 ON p2.id = e.participante2
        LEFT JOIN grupos g ON g.id = e.grupo_id
        WHERE e.etapa IN ('Grupo', 'Todos')
        ORDER BY e.id
    """)
    combates = cursor.fetchall()
    if not combates or any(f[6] != "Completado" for f in combates):
        return None

    cursor.execute("""
        SELECT gp.participante_id, gp.grupo_id, p.robot, g.nombre
        FROM grupo_participantes gp
        JOIN participantes p ON p.id = gp.participante_id
        JOIN grupos g ON g.id = gp.grupo_id
    """)
    stats = {}
    for pid, gid, robot, grupo in cursor.fetchall():
        stats[pid] = {
            "id": pid, "grupo_id": gid, "grupo": grupo, "robot": robot,
            "puntos": 0, "victorias": 0, "combates": 0,
            "tiempo_total": 0, "tiempos_validos": 0,
            "ataques_propios": 0, "ataques_totales": 0,
        }

    directos = {}
    for (bid, etapa, grupo_id, p1, p2, ganador, estado, tiempo,
         ataques1, ataques2, robot1, robot2, grupo) in combates:
        if etapa == "Todos":
            for pid, robot in ((p1, robot1), (p2, robot2)):
                stats.setdefault(pid, {
                    "id": pid, "grupo_id": None, "grupo": "Todos contra todos",
                    "robot": robot, "puntos": 0, "victorias": 0, "combates": 0,
                    "tiempo_total": 0, "tiempos_validos": 0,
                    "ataques_propios": 0, "ataques_totales": 0,
                })
        s1, s2 = stats[p1], stats[p2]
        s1["combates"] += 1
        s2["combates"] += 1
        s1["ataques_propios"] += max(0, int(ataques1 or 0))
        s2["ataques_propios"] += max(0, int(ataques2 or 0))
        total_ataques = max(0, int(ataques1 or 0)) + max(0, int(ataques2 or 0))
        s1["ataques_totales"] += total_ataques
        s2["ataques_totales"] += total_ataques
        segundos = _tiempo_a_segundos(tiempo)
        if segundos is not None:
            for s in (s1, s2):
                s["tiempo_total"] += segundos
                s["tiempos_validos"] += 1
        if ganador in (p1, p2):
            stats[ganador]["victorias"] += 1
            stats[ganador]["puntos"] += 1
            directos[frozenset((p1, p2))] = ganador

    for s in stats.values():
        s["tiempo_promedio"] = (
            s["tiempo_total"] / s["tiempos_validos"]
            if s["tiempos_validos"] else None
        )
        s["porcentaje_ataques"] = (
            100 * s["ataques_propios"] / s["ataques_totales"]
            if s["ataques_totales"] else 0.0
        )
        s["porcentaje_victorias"] = (
            100 * s["victorias"] / s["combates"]
            if s["combates"] else 0.0
        )
    return stats, directos


def _comparar(a, b, directos):
    if a["puntos"] != b["puntos"]:
        return -1 if a["puntos"] > b["puntos"] else 1
    ta, tb = a["tiempo_promedio"], b["tiempo_promedio"]
    if ta is not None or tb is not None:
        ta = float("inf") if ta is None else ta
        tb = float("inf") if tb is None else tb
        if ta != tb:
            return -1 if ta < tb else 1
    if a["porcentaje_ataques"] != b["porcentaje_ataques"]:
        return -1 if a["porcentaje_ataques"] > b["porcentaje_ataques"] else 1
    if a["porcentaje_victorias"] != b["porcentaje_victorias"]:
        return -1 if a["porcentaje_victorias"] > b["porcentaje_victorias"] else 1
    directo = directos.get(frozenset((a["id"], b["id"])))
    if directo == a["id"]:
        return -1
    if directo == b["id"]:
        return 1
    return (a["id"] > b["id"]) - (a["id"] < b["id"])


def obtener_tabla_clasificacion():
    """Filas visuales por puesto y grupo; cupos decididos por rendimiento."""
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        resultado = _estadisticas(cursor)
        if resultado is None:
            return None
        stats, directos = resultado
        cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
        hay_grupos = cursor.fetchone()[0] > 0

        if hay_grupos:
            por_grupo = {}
            for s in stats.values():
                if s["grupo_id"] is not None:
                    por_grupo.setdefault(s["grupo_id"], []).append(s)
            ranking = []
            for miembros in por_grupo.values():
                miembros.sort(key=cmp_to_key(lambda a, b: _comparar(a, b, directos)))
                for posicion, s in enumerate(miembros, 1):
                    fila = dict(s)
                    fila["posicion_grupo"] = posicion
                    ranking.append(fila)
            # Orden visible: todos los primeros puestos por grupo A, B, C;
            # después todos los segundos, y así sucesivamente.
            ranking.sort(key=lambda r: (
                r["posicion_grupo"], r["grupo"].casefold(), r["robot"].casefold()
            ))
            cantidad_total = len(stats)
            cupos = min(cantidad_clasificados(cantidad_total), len(ranking))

            # Para decidir quién entra si los cupos se terminan dentro de una
            # posición, comparar estadísticas entre los integrantes de esa posición.
            seleccionados = set()
            posiciones = sorted({r["posicion_grupo"] for r in ranking})
            for posicion in posiciones:
                nivel = [r for r in ranking if r["posicion_grupo"] == posicion]
                nivel.sort(key=cmp_to_key(lambda a, b: _comparar(a, b, directos)))
                for fila in nivel:
                    if len(seleccionados) >= cupos:
                        break
                    seleccionados.add(fila["id"])
                if len(seleccionados) >= cupos:
                    break
        else:
            ranking = sorted(stats.values(), key=cmp_to_key(lambda a, b: _comparar(a, b, directos)))
            for posicion, fila in enumerate(ranking, 1):
                fila["posicion_grupo"] = posicion
            cupos = 2
            seleccionados = {r["id"] for r in ranking[:cupos]}

        for fila in ranking:
            fila["clasifica"] = fila["id"] in seleccionados
            fila["tiempo_mostrar"] = _segundos_a_tiempo(fila["tiempo_promedio"])
        return ranking
    finally:
        conexion.close()


def _obtener_clasificados(cursor):
    resultado = _estadisticas(cursor)
    if resultado is None:
        return None
    stats, directos = resultado
    cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
    hay_grupos = cursor.fetchone()[0] > 0
    if not hay_grupos:
        ranking = sorted(stats.values(), key=cmp_to_key(lambda a, b: _comparar(a, b, directos)))
        return [(s["id"], None) for s in ranking[:2]]

    por_grupo = {}
    for s in stats.values():
        if s["grupo_id"] is not None:
            por_grupo.setdefault(s["grupo_id"], []).append(s)
    ranking = []
    for gid, miembros in por_grupo.items():
        miembros.sort(key=cmp_to_key(lambda a, b: _comparar(a, b, directos)))
        for posicion, s in enumerate(miembros, 1):
            fila = dict(s)
            fila["posicion"] = posicion
            ranking.append(fila)

    # La siembra prioriza el puesto de grupo. Entre robots que ocuparon
    # el mismo puesto, desempata el rendimiento global acordado.
    ranking.sort(key=lambda r: r["posicion"])
    orden_siembra = []
    for posicion in sorted({r["posicion"] for r in ranking}):
        nivel = [r for r in ranking if r["posicion"] == posicion]
        nivel.sort(key=cmp_to_key(lambda a, b: _comparar(a, b, directos)))
        orden_siembra.extend(nivel)

    cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
    cantidad_total = cursor.fetchone()[0]
    cupos = min(cantidad_clasificados(cantidad_total), len(orden_siembra))
    return [(r["id"], r["grupo_id"]) for r in orden_siembra[:cupos]]


def _orden_siembra(cantidad):
    orden = [1, 2]
    while len(orden) < cantidad:
        limite = len(orden) * 2 + 1
        orden = [s for anterior in orden for s in (anterior, limite - anterior)]
    return orden


def _emparejar_primera_ronda(clasificados):
    participantes = [clasificados[s - 1] for s in _orden_siembra(len(clasificados))]
    def conflictos():
        return sum(
            1 for i in range(0, len(participantes), 2)
            if participantes[i][1] is not None and participantes[i][1] == participantes[i + 1][1]
        )
    for i in range(0, len(participantes), 2):
        if participantes[i][1] is None or participantes[i][1] != participantes[i + 1][1]:
            continue
        mejor, intercambio = conflictos(), None
        for j in range(i + 2, len(participantes), 2):
            participantes[i + 1], participantes[j + 1] = participantes[j + 1], participantes[i + 1]
            nuevos = conflictos()
            if nuevos < mejor:
                mejor, intercambio = nuevos, j
            participantes[i + 1], participantes[j + 1] = participantes[j + 1], participantes[i + 1]
        if intercambio is not None:
            j = intercambio
            participantes[i + 1], participantes[j + 1] = participantes[j + 1], participantes[i + 1]
    return [(participantes[i][0], participantes[i + 1][0]) for i in range(0, len(participantes), 2)]


def _crear_cuadro_inicial(cursor, clasificados):
    parejas = _emparejar_primera_ronda(clasificados)
    cantidad = len(clasificados)
    if not parejas:
        return
    tamano = cantidad
    while tamano >= 2:
        ronda = nombre_ronda(tamano)
        for posicion in range(1, tamano // 2 + 1):
            p1, p2 = parejas[posicion - 1] if tamano == cantidad else (None, None)
            cursor.execute("""
                INSERT INTO llaves (ronda, posicion, participante1, participante2, estado)
                VALUES (?, ?, ?, ?, 'Pendiente')
            """, (ronda, posicion, p1, p2))
        tamano //= 2
    etapa = nombre_ronda(cantidad)
    for p1, p2 in parejas:
        cursor.execute("""
            INSERT INTO enfrentamientos (etapa, grupo_id, participante1, participante2, estado, ronda)
            VALUES (?, NULL, ?, ?, 'Pendiente', 1)
        """, (etapa, p1, p2))


def generar_llaves_manualmente():
    return _generar_llaves()


def _generar_llaves():
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
        total_grupos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo' AND estado != 'Completado'")
        pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM llaves")
        existentes = cursor.fetchone()[0]
        if not total_grupos:
            return False, "No hay una fase de grupos preparada."
        if pendientes:
            return False, "Aún hay batallas de grupos pendientes."
        if existentes:
            return False, "Las llaves ya fueron generadas."

        clasificados = _obtener_clasificados(cursor)
        if not clasificados or len(clasificados) < 2:
            return False, "No se pudieron determinar al menos dos clasificados."
        _crear_cuadro_inicial(cursor, clasificados)
        conexion.commit()
        return True, f"Se generaron {len(clasificados)} clasificados y sus primeros enfrentamientos."
    except Exception as error:
        conexion.rollback()
        return False, f"No se pudieron generar las llaves: {error}"
    finally:
        conexion.close()


def _crear_final_todos(cursor):
    cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
    if cursor.fetchone()[0]:
        return
    clasificados = _obtener_clasificados(cursor)
    if not clasificados or len(clasificados) < 2:
        return
    cursor.execute("""
        INSERT INTO enfrentamientos (etapa, grupo_id, participante1, participante2, estado, ronda)
        VALUES ('Final', NULL, ?, ?, 'Pendiente', 1)
    """, (clasificados[0][0], clasificados[1][0]))


def _sincronizar_resultados_llaves(cursor):
    cursor.execute("SELECT DISTINCT ronda FROM llaves")
    etapas = [r[0] for r in cursor.fetchall()]
    for etapa in etapas:
        cursor.execute("""
            SELECT ganador, estado FROM enfrentamientos WHERE etapa = ? ORDER BY id
        """, (etapa,))
        for posicion, (ganador, estado) in enumerate(cursor.fetchall(), 1):
            cursor.execute("""
                UPDATE llaves SET ganador = ?, estado = ?
                WHERE ronda = ? AND posicion = ?
            """, (ganador, "Completado" if estado == "Completado" else estado, etapa, posicion))


def _avanzar_ronda(cursor):
    cursor.execute("SELECT ronda, COUNT(*) FROM llaves GROUP BY ronda")
    rondas = sorted(cursor.fetchall(), key=lambda fila: fila[1], reverse=True)
    if len(rondas) < 2:
        return
    etapas = [r[0] for r in rondas]
    for indice, etapa in enumerate(etapas[:-1]):
        cursor.execute("SELECT ganador, estado FROM enfrentamientos WHERE etapa = ? ORDER BY id", (etapa,))
        combates = cursor.fetchall()
        if not combates or any(estado != "Completado" or ganador is None for ganador, estado in combates):
            continue
        siguiente = etapas[indice + 1]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = ?", (siguiente,))
        if cursor.fetchone()[0]:
            continue
        ganadores = [ganador for ganador, _ in combates]
        parejas = [(ganadores[i], ganadores[i + 1]) for i in range(0, len(ganadores), 2)]
        for posicion, (p1, p2) in enumerate(parejas, 1):
            cursor.execute("""
                UPDATE llaves SET participante1 = ?, participante2 = ?, estado = 'Pendiente'
                WHERE ronda = ? AND posicion = ?
            """, (p1, p2, siguiente, posicion))
            cursor.execute("""
                INSERT INTO enfrentamientos (etapa, grupo_id, participante1, participante2, estado, ronda)
                VALUES (?, NULL, ?, ?, 'Pendiente', ?)
            """, (siguiente, p1, p2, indice + 2))
        break


def actualizar_llaves_tras_resultado():
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ronda TEXT NOT NULL,
                posicion INTEGER NOT NULL, participante1 INTEGER, participante2 INTEGER,
                ganador INTEGER, estado TEXT DEFAULT 'Pendiente'
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
        total_todos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos' AND estado != 'Completado'")
        pendientes_todos = cursor.fetchone()[0]
        # La final de 3–5 participantes se crea desde Enfrentamientos,
        # después de que el organizador revise la tabla de clasificación.
        cursor.execute("SELECT COUNT(*) FROM llaves")
        if cursor.fetchone()[0]:
            _sincronizar_resultados_llaves(cursor)
            _avanzar_ronda(cursor)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()



def obtener_datos_llaves():
    """Devuelve las rondas y sus combates con nombres para dibujar el cuadro visual."""
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT l.id, l.ronda, l.posicion,
                   l.participante1, l.participante2, l.ganador, l.estado,
                   p1.robot, p1.nombre, p2.robot, p2.nombre
            FROM llaves l
            LEFT JOIN participantes p1 ON p1.id = l.participante1
            LEFT JOIN participantes p2 ON p2.id = l.participante2
            ORDER BY l.id
        """)
        filas = cursor.fetchall()
        rondas = []
        por_nombre = {}
        for fila in filas:
            (llave_id, ronda, posicion, p1, p2, ganador, estado,
             robot1, nombre1, robot2, nombre2) = fila
            if ronda not in por_nombre:
                por_nombre[ronda] = []
                rondas.append({"nombre": ronda, "combates": por_nombre[ronda]})
            por_nombre[ronda].append({
                "id": llave_id,
                "posicion": posicion,
                "participante1": p1,
                "participante2": p2,
                "ganador": ganador,
                "estado": estado or "Pendiente",
                "robot1": robot1 or "Por definir",
                "nombre1": nombre1 or "",
                "robot2": robot2 or "Por definir",
                "nombre2": nombre2 or "",
            })
        return rondas
    finally:
        conexion.close()



def generar_final_todos_manualmente():
    """Crea la final entre los dos mejores tras revisar la clasificación."""
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos' AND estado != 'Completado'")
        pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
        existe_final = cursor.fetchone()[0]
        if not total or pendientes:
            return False, "Aún hay batallas de todos contra todos pendientes."
        if existe_final:
            return False, "La final ya está generada."
        clasificados = _obtener_clasificados(cursor)
        if not clasificados or len(clasificados) < 2:
            return False, "No se pudieron determinar los dos mejores participantes."
        cursor.execute("""
            INSERT INTO enfrentamientos
                (etapa, grupo_id, participante1, participante2, estado, ronda)
            VALUES ('Final', NULL, ?, ?, 'Pendiente', 1)
        """, (clasificados[0][0], clasificados[1][0]))
        conexion.commit()
        return True, "Final generada entre los dos primeros de la clasificación."
    except Exception as error:
        conexion.rollback()
        return False, f"No se pudo generar la final: {error}"
    finally:
        conexion.close()
