"""Clasificación estadística y gestión manual de llaves para MiniSumos RC."""
import os
import sqlite3
from functools import cmp_to_key

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
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
    """Convierte M:SS:CC (minutos:segundos:centésimas) a segundos."""
    if valor is None:
        return None
    try:
        partes = [int(p) for p in str(valor).strip().split(":")]
        if len(partes) == 2:
            # Compatibilidad con tiempos antiguos guardados como MM:SS.
            return partes[0] * 60 + partes[1]
        if len(partes) == 3:
            minutos, segundos, centesimas = partes
            if minutos < 0 or not 0 <= segundos < 60 or not 0 <= centesimas < 100:
                return None
            return minutos * 60 + segundos + centesimas / 100
    except (TypeError, ValueError):
        return None
    return None


def _segundos_a_tiempo(segundos):
    """Formatea minutos, segundos y centésimas como MM:SSCC para las tablas."""
    if segundos is None:
        return "00:0000"
    total_centesimas = max(0, int(round(float(segundos) * 100)))
    minutos = total_centesimas // 6000
    segundos_restantes = (total_centesimas % 6000) // 100
    centesimas = total_centesimas % 100
    return f"{minutos:02d}:{segundos_restantes:02d}{centesimas:02d}"


def _cantidad_participantes_validos(cursor):
    """Cuenta únicamente participantes que cumplen todos los requisitos del reglamento."""
    cursor.execute("""
        SELECT COUNT(*)
        FROM participantes p
        WHERE CAST(COALESCE(p.peso, 0) AS REAL) > 0
          AND CAST(COALESCE(p.peso, 0) AS REAL) <= 500
          AND COALESCE(CAST(p.cumple_dimensiones AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.tipo_rc AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.interruptor_visible AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.sin_elementos_fijacion AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.sensores_tapados AS INTEGER), 0) != 0
    """)
    return cursor.fetchone()[0]


def _estadisticas(cursor):
    """Calcula estadísticas parciales usando únicamente batallas ya completadas."""
    cursor.execute("""
        SELECT p.id, p.robot, COALESCE(gp.grupo_id, NULL), COALESCE(g.nombre, '')
        FROM participantes p
        LEFT JOIN grupo_participantes gp ON gp.participante_id = p.id
        LEFT JOIN grupos g ON g.id = gp.grupo_id
        WHERE CAST(COALESCE(p.peso, 0) AS REAL) > 0
          AND CAST(COALESCE(p.peso, 0) AS REAL) <= 500
          AND COALESCE(CAST(p.cumple_dimensiones AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.tipo_rc AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.interruptor_visible AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.sin_elementos_fijacion AS INTEGER), 0) != 0
          AND COALESCE(CAST(p.sensores_tapados AS INTEGER), 0) != 0
        ORDER BY p.id
    """)
    stats = {}
    for pid, robot, gid, grupo in cursor.fetchall():
        stats[pid] = {
            "id": pid,
            "grupo_id": gid,
            "grupo": grupo if gid is not None else "Todos contra todos",
            "robot": robot or "—",
            "puntos": 0,
            "victorias": 0,
            "combates": 0,
            "tiempo_total": 0,
            "tiempos_validos": 0,
            "ataques_propios": 0,
            "ataques_totales": 0,
        }

    cursor.execute("""
        SELECT e.id, e.etapa, e.grupo_id, e.participante1, e.participante2,
               e.ganador, e.estado, e.tiempo,
               COALESCE(e.ataques1, 0), COALESCE(e.ataques2, 0),
               p1.robot, p2.robot
        FROM enfrentamientos e
        JOIN participantes p1 ON p1.id = e.participante1
        JOIN participantes p2 ON p2.id = e.participante2
        WHERE e.etapa IN ('Grupo', 'Todos') AND e.estado = 'Completado'
        ORDER BY e.id
    """)
    combates = cursor.fetchall()
    directos = {}

    for (bid, etapa, grupo_id, p1, p2, ganador, estado, tiempo,
         ataques1, ataques2, robot1, robot2) in combates:
        # No reincorporar al ranking participantes que ya no cumplen el reglamento.
        # Si cualquiera de los robots de un combate no está en el conjunto válido,
        # ese combate no interviene en las estadísticas de clasificación.
        if p1 not in stats or p2 not in stats:
            continue

        s1, s2 = stats[p1], stats[p2]
        s1["combates"] += 1
        s2["combates"] += 1
        a1, a2 = max(0, int(ataques1 or 0)), max(0, int(ataques2 or 0))
        s1["ataques_propios"] += a1
        s2["ataques_propios"] += a2
        total_ataques = a1 + a2
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
        s["ha_competido"] = s["combates"] > 0
    return stats, directos

def _comparar(a, b, directos=None):
    """Ordena por puntos, porcentaje de ataques, tiempo promedio y victorias."""
    if a["puntos"] != b["puntos"]:
        return -1 if a["puntos"] > b["puntos"] else 1

    if a["porcentaje_ataques"] != b["porcentaje_ataques"]:
        return -1 if a["porcentaje_ataques"] > b["porcentaje_ataques"] else 1

    ta, tb = a["tiempo_promedio"], b["tiempo_promedio"]
    ta = float("inf") if ta is None else ta
    tb = float("inf") if tb is None else tb
    if ta != tb:
        return -1 if ta < tb else 1

    if a["victorias"] != b["victorias"]:
        return -1 if a["victorias"] > b["victorias"] else 1

    return (a["id"] > b["id"]) - (a["id"] < b["id"])


def _clave_ranking(a, b):
    """Prioriza a quien ya compitió y luego aplica el criterio oficial."""
    if a["ha_competido"] != b["ha_competido"]:
        return -1 if a["ha_competido"] else 1
    return _comparar(a, b)


def _ranking_general(stats):
    return sorted(stats.values(), key=cmp_to_key(_clave_ranking))


def _seleccionar_ids_clasificados(stats, cantidad_cupos):
    """En grupos, asigna cupos por posición: primeros, segundos, terceros, etc."""
    grupos = {}
    for fila in stats.values():
        grupo_id = fila.get("grupo_id")
        if grupo_id is not None:
            grupos.setdefault(grupo_id, []).append(fila)

    # Sin fase de grupos: clasificación general (todos contra todos).
    if not grupos:
        return [
            fila["id"]
            for fila in _ranking_general(stats)[:cantidad_cupos]
        ]

    for filas in grupos.values():
        filas.sort(key=cmp_to_key(_clave_ranking))

    seleccionados = []
    posicion = 0
    while len(seleccionados) < cantidad_cupos:
        candidatos = [
            filas[posicion]
            for filas in grupos.values()
            if len(filas) > posicion
        ]
        if not candidatos:
            break
        candidatos.sort(key=cmp_to_key(_clave_ranking))
        for fila in candidatos:
            if len(seleccionados) >= cantidad_cupos:
                break
            seleccionados.append(fila["id"])
        posicion += 1

    return seleccionados


def obtener_tabla_clasificacion():
    """Devuelve el ranking y la marca de clasificación en tiempo real."""
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        stats, _ = _estadisticas(cursor)
        if not stats:
            return []

        ranking = _ranking_general(stats)
        cantidad_total = _cantidad_participantes_validos(cursor)
        cupos = (
            min(cantidad_clasificados(cantidad_total), len(ranking))
            if cantidad_total >= 6 else min(2, len(ranking))
        )
        ids_clasificados = set(_seleccionar_ids_clasificados(stats, cupos))

        for posicion, fila in enumerate(ranking, 1):
            fila["posicion"] = posicion
            fila["clasifica"] = fila["id"] in ids_clasificados
            fila["tiempo_mostrar"] = _segundos_a_tiempo(fila["tiempo_promedio"])
        return ranking
    finally:
        conexion.close()


def _obtener_clasificados(cursor):
    """Selecciona clasificados por posición entre grupos, completando los cupos."""
    stats, _ = _estadisticas(cursor)
    cantidad_total = _cantidad_participantes_validos(cursor)
    ranking = _ranking_general(stats)

    if cantidad_total <= 5:
        cantidad_cupos = min(2, len(ranking))
    else:
        cantidad_cupos = min(cantidad_clasificados(cantidad_total), len(ranking))

    ids_clasificados = _seleccionar_ids_clasificados(stats, cantidad_cupos)
    por_id = {fila["id"]: fila for fila in ranking}
    return [
        (por_id[pid]["id"], por_id[pid]["grupo_id"])
        for pid in ids_clasificados
        if pid in por_id
    ]

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
            # Solo sincroniza resultados. La siguiente ronda se habilita
            # manualmente desde la pestaña Eliminatorias.
            _sincronizar_resultados_llaves(cursor)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()



def avanzar_ronda_manualmente():
    """Habilita la siguiente ronda solo después de completar la ronda actual."""
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT ronda, COUNT(*) FROM llaves GROUP BY ronda")
        rondas = sorted(cursor.fetchall(), key=lambda fila: fila[1], reverse=True)
        if len(rondas) < 2:
            return False, "Esta es la ronda final; no hay otra fase por habilitar."

        _sincronizar_resultados_llaves(cursor)
        for indice, (ronda_actual, _) in enumerate(rondas[:-1]):
            cursor.execute(
                "SELECT ganador, estado FROM enfrentamientos WHERE etapa = ? ORDER BY id",
                (ronda_actual,)
            )
            combates = cursor.fetchall()
            if not combates:
                return False, f"Los enfrentamientos de {ronda_actual} todavía no se han generado."
            if any(estado != "Completado" or ganador is None for ganador, estado in combates):
                return False, f"Aún hay combates pendientes en {ronda_actual}."

            siguiente = rondas[indice + 1][0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = ?", (siguiente,))
            if cursor.fetchone()[0]:
                # Esa ronda ya se habilitó; continuar revisando si ya terminó también.
                continue

            ganadores = [ganador for ganador, _ in combates]
            if len(ganadores) < 2 or len(ganadores) % 2:
                return False, "No se pudo formar la siguiente ronda con los ganadores actuales."

            parejas = [(ganadores[i], ganadores[i + 1]) for i in range(0, len(ganadores), 2)]
            for posicion, (p1, p2) in enumerate(parejas, 1):
                cursor.execute("""
                    UPDATE llaves SET participante1 = ?, participante2 = ?, estado = 'Pendiente'
                    WHERE ronda = ? AND posicion = ?
                """, (p1, p2, siguiente, posicion))
                cursor.execute("""
                    INSERT INTO enfrentamientos
                        (etapa, grupo_id, participante1, participante2, estado, ronda)
                    VALUES (?, NULL, ?, ?, 'Pendiente', ?)
                """, (siguiente, p1, p2, indice + 2))
            conexion.commit()
            return True, f"Se habilitó la fase: {siguiente}."

        return False, "No hay otra ronda pendiente por habilitar. La eliminatoria ya llegó a su final."
    except Exception as error:
        conexion.rollback()
        return False, f"No se pudo habilitar la siguiente ronda: {error}"
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


def avanzar_fase_automatica():
    """Crea la siguiente fase cuando todos los combates iniciales están completados."""
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM grupo_participantes")
        hay_grupos = cursor.fetchone()[0] > 0

        if hay_grupos:
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo' AND estado != 'Completado'")
            pendientes = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM llaves")
            llaves_existentes = cursor.fetchone()[0]
            conexion.close()
            if total > 0 and pendientes == 0 and not llaves_existentes:
                return _generar_llaves()
            return False, "La fase de grupos aún no ha terminado."
        
        cantidad = _cantidad_participantes_validos(cursor)
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos' AND estado != 'Completado'")
        pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
        final_existente = cursor.fetchone()[0]
        if cantidad < 3 or cantidad > 5 or total == 0 or pendientes > 0 or final_existente:
            conexion.close()
            return False, "La fase inicial aún no ha terminado o no requiere una final automática."

        clasificados = _obtener_clasificados(cursor)
        if not clasificados or len(clasificados) < 2:
            conexion.close()
            return False, "No se pudieron determinar los dos mejores participantes."
        cursor.execute("""
            INSERT INTO enfrentamientos
                (etapa, grupo_id, participante1, participante2, estado, ronda)
            VALUES ('Final', NULL, ?, ?, 'Pendiente', 1)
        """, (clasificados[0][0], clasificados[1][0]))
        conexion.commit()
        return True, "Final generada automáticamente entre los dos primeros del ranking."
    except Exception as error:
        try:
            conexion.rollback()
        except Exception:
            pass
        return False, f"No se pudo generar automáticamente la siguiente fase: {error}"
    finally:
        try:
            conexion.close()
        except Exception:
            pass
