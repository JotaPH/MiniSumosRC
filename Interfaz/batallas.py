import tkinter as tk
from tkinter import messagebox
import sqlite3
import os
import time
from tkinter import ttk
from logica import RelojBatalla
from dashboard_bridge import dashboard_bridge
from llaves import (actualizar_llaves_tras_resultado, generar_llaves_manualmente, generar_final_todos_manualmente, avanzar_ronda_manualmente)

# Bloqueo temporal de controles de la siguiente batalla mientras el dashboard
# muestra el anuncio del ganador.
BLOQUEO_CONTROLES_HASTA = 0.0

def _separar_tiempo_visual(valor):
    """Devuelve minutos:segundos y centésimas para mostrar con tamaños distintos."""
    try:
        partes = [int(p) for p in str(valor or "0:00:00").split(":")]
        if len(partes) == 3:
            minutos, segundos, centesimas = partes
        elif len(partes) == 2:
            minutos, segundos = partes
            centesimas = 0
        else:
            minutos, segundos, centesimas = 0, 0, 0
        return f"{minutos:02d}:{segundos:02d}", f"{centesimas:02d}"
    except (TypeError, ValueError):
        return "00:00", "00"


def _tiempo_a_segundos(valor):
    """Convierte minutos:segundos:centésimas al valor numérico oficial."""
    try:
        partes = [int(p) for p in str(valor or "0:00:00").split(":")]
        if len(partes) == 3:
            return max(0.0, partes[0] * 60 + partes[1] + partes[2] / 100)
        if len(partes) == 2:
            return max(0.0, partes[0] * 60 + partes[1])
    except (TypeError, ValueError):
        pass
    return 0.0


def _imagen_dashboard(robot, participante_id, imagen_evitar=None):
    """Asigna un color estable por participante y evita repetir color en la batalla."""
    colores = [
        ("amarillo", "/Imagenes/R_Amarillo.png"),
        ("morado", "/Imagenes/R_Morado.png"),
        ("rojo", "/Imagenes/R_Rojo.png"),
        ("verde", "/Imagenes/R_Verde.png"),
    ]
    nombre = str(robot or "").strip().lower()
    claves = {
        "amarillo": "/Imagenes/R_Amarillo.png",
        "morado": "/Imagenes/R_Morado.png",
        "purple": "/Imagenes/R_Morado.png",
        "rojo": "/Imagenes/R_Rojo.png",
        "verde": "/Imagenes/R_Verde.png",
    }
    imagen = next((ruta for clave, ruta in claves.items() if clave in nombre), None)
    if imagen is None:
        try:
            indice = (int(participante_id) - 1) % len(colores)
        except (TypeError, ValueError):
            indice = 0
        imagen = colores[indice][1]
    if imagen == imagen_evitar:
        indice = next((i for i, (_, ruta) in enumerate(colores) if ruta == imagen), 0)
        imagen = colores[(indice + 1) % len(colores)][1]
    return imagen


def _actualizar_tiempo_visual(etiqueta_principal, etiqueta_centesimas, valor):
    principal, centesimas = _separar_tiempo_visual(valor)
    etiqueta_principal.config(text=principal)
    etiqueta_centesimas.config(text=centesimas)




# ============================================================
# COMPONENTES VISUALES REDONDEADOS
# ============================================================

def _puntos_redondeados(x1, y1, x2, y2, radio):
    radio = max(2, min(radio, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + radio, y1, x2 - radio, y1,
        x2, y1, x2, y1 + radio,
        x2, y2 - radio, x2, y2,
        x2 - radio, y2, x1 + radio, y2,
        x1, y2, x1, y2 - radio,
        x1, y1 + radio, x1, y1
    ]


class RoundedCard(tk.Frame):
    """Tarjeta con fondo redondeado y un frame interior para sus widgets."""
    def __init__(self, master, fill="#ffffff", outline="#d7dde2",
                 radius=18, padding=8, height=120, **kwargs):
        super().__init__(master, bg=master.cget("bg"), bd=0,
                         highlightthickness=0, **kwargs)
        self.fill = fill
        self.outline = outline
        self.radius = radius
        self.padding = padding
        self.canvas = tk.Canvas(
            self, bg=master.cget("bg"), bd=0, highlightthickness=0,
            relief="flat", height=height
        )
        self.canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(self.canvas, bg=fill, bd=0,
                                highlightthickness=0)
        self.window_id = self.canvas.create_window(
            padding, padding, anchor="nw", window=self.content
        )
        self.canvas.bind("<Configure>", self._redibujar)
        self.after_idle(self._redibujar)

    def _redibujar(self, event=None):
        ancho = max(2, self.canvas.winfo_width())
        alto = max(2, self.canvas.winfo_height())
        p = min(self.padding, max(2, ancho // 5), max(2, alto // 5))
        self.canvas.delete("fondo_redondeado")
        self.canvas.create_polygon(
            _puntos_redondeados(1, 1, ancho - 1, alto - 1, self.radius),
            smooth=True, splinesteps=24, fill=self.fill,
            outline=self.outline, width=1, tags="fondo_redondeado"
        )
        self.canvas.tag_lower("fondo_redondeado")
        self.canvas.coords(self.window_id, p, p)
        self.canvas.itemconfigure(
            self.window_id, width=max(1, ancho - 2 * p),
            height=max(1, alto - 2 * p)
        )


class RoundedButton(tk.Canvas):
    """Botón dibujado en Canvas para mantener esquinas redondeadas."""
    def __init__(self, master, text="", command=None, width=150, height=44,
                 bg="#2563eb", fg="white", activebackground=None,
                 activeforeground=None, disabledbackground="#cbd5e1",
                 font=("Segoe UI", 11, "bold"), radius=14, state="normal",
                 secondary_text=None, secondary_font=("Segoe UI", 14),
                 **kwargs):
        super().__init__(
            master, width=width, height=height, bg=master.cget("bg"),
            bd=0, highlightthickness=0, relief="flat", cursor="hand2"
        )
        self.text = text
        self.command = command
        self.button_bg = bg
        self.button_fg = fg
        self.activebackground = activebackground or bg
        self.activeforeground = activeforeground or fg
        self.disabledbackground = disabledbackground
        self.font = font
        self.secondary_text = secondary_text
        self.secondary_font = secondary_font
        self.radius = radius
        self.state = state
        self.hover = False
        self.bind("<Configure>", self._dibujar)
        self.bind("<Enter>", self._entrar)
        self.bind("<Leave>", self._salir)
        self.bind("<Button-1>", self._clic)
        self.after_idle(self._dibujar)

    def _color_actual(self):
        if self.state == "disabled":
            return self.disabledbackground
        return self.activebackground if self.hover else self.button_bg

    def _dibujar(self, event=None):
        self.delete("all")
        ancho = max(2, self.winfo_width())
        alto = max(2, self.winfo_height())
        self.create_polygon(
            _puntos_redondeados(1, 1, ancho - 1, alto - 1, self.radius),
            smooth=True, splinesteps=24, fill=self._color_actual(),
            outline=self._color_actual()
        )
        color_texto = "#f8fafc" if self.state == "disabled" else self.button_fg
        if self.secondary_text is None:
            self.create_text(
                ancho / 2, alto / 2, text=self.text,
                fill=color_texto, font=self.font, justify="center"
            )
        else:
            self.create_text(
                ancho / 2, alto * 0.39, text=self.text,
                fill=color_texto, font=self.font, justify="center"
            )
            self.create_text(
                ancho / 2, alto * 0.70, text=self.secondary_text,
                fill=color_texto, font=self.secondary_font, justify="center"
            )
        super().configure(cursor="arrow" if self.state == "disabled" else "hand2")

    def _entrar(self, event=None):
        self.hover = True
        self._dibujar()

    def _salir(self, event=None):
        self.hover = False
        self._dibujar()

    def _clic(self, event=None):
        if self.state != "disabled" and callable(self.command):
            self.command()

    def config(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
        atributos = {
            "command": "command", "text": "text", "bg": "button_bg",
            "fg": "button_fg", "activebackground": "activebackground",
            "activeforeground": "activeforeground",
            "disabledbackground": "disabledbackground",
            "font": "font", "state": "state"
        }
        for key, attr in atributos.items():
            if key in kwargs:
                setattr(self, attr, kwargs.pop(key))
        if kwargs:
            super().configure(**kwargs)
        self._dibujar()

    configure = config


# ============================================================
# BASE DE DATOS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
ruta_bd = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")


def conectar_bd():
    return sqlite3.connect(ruta_bd)


# ============================================================
# PREPARAR BASE DE DATOS
# ============================================================

def preparar_base_batallas():

    conexion = conectar_bd()
    cursor = conexion.cursor()

    cursor.execute(
        "PRAGMA table_info(enfrentamientos)"
    )

    columnas = [
        fila[1]
        for fila in cursor.fetchall()
    ]

    if "criterio_ganador" not in columnas:

        cursor.execute("""
            ALTER TABLE enfrentamientos
            ADD COLUMN criterio_ganador TEXT
        """)

    if "tiempo" not in columnas:

        cursor.execute("""
            ALTER TABLE enfrentamientos
            ADD COLUMN tiempo TEXT
        """)

    if "inicio_epoch" not in columnas:
        cursor.execute("""
            ALTER TABLE enfrentamientos
            ADD COLUMN inicio_epoch REAL
        """)

    if "ataques1" not in columnas:

        cursor.execute("""
            ALTER TABLE enfrentamientos
            ADD COLUMN ataques1 INTEGER DEFAULT 0
        """)

    if "ataques2" not in columnas:

        cursor.execute("""
            ALTER TABLE enfrentamientos
            ADD COLUMN ataques2 INTEGER DEFAULT 0
        """)

    # Archivo histórico independiente: sobrevive al reinicio de las fases.
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
        CREATE TABLE IF NOT EXISTS historial_control (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    # En la primera ejecución, importar también los resultados que ya estaban
    # completados antes de instalar el historial permanente.
    cursor.execute(
        "SELECT valor FROM historial_control WHERE clave = ?",
        ("copia_inicial_completados_v1",)
    )
    migracion_realizada = cursor.fetchone()

    if not migracion_realizada:
        cursor.execute("""
            INSERT INTO historial_batallas (
                batalla_id, etapa, grupo, robot1, robot2, tiempo,
                ataques1, ataques2, ganador, motivo
            )
            SELECT
                e.id,
                e.etapa,
                COALESCE(g.nombre, ''),
                COALESCE(p1.robot, p1.nombre, '—'),
                COALESCE(p2.robot, p2.nombre, '—'),
                COALESCE(e.tiempo, ''),
                COALESCE(e.ataques1, 0),
                COALESCE(e.ataques2, 0),
                COALESCE(pg.robot, pg.nombre, 'Sin ganador'),
                COALESCE(e.criterio_ganador, '')
            FROM enfrentamientos e
            LEFT JOIN grupos g ON g.id = e.grupo_id
            LEFT JOIN participantes p1 ON p1.id = e.participante1
            LEFT JOIN participantes p2 ON p2.id = e.participante2
            LEFT JOIN participantes pg ON pg.id = e.ganador
            WHERE e.estado = 'Completado'
            ORDER BY e.id
        """)
        cursor.execute("""
            INSERT INTO historial_control (clave, valor)
            VALUES (?, ?)
        """, ("copia_inicial_completados_v1", "completada"))

    conexion.commit()
    conexion.close()


preparar_base_batallas()


# ============================================================
# OBTENER BATALLA
# ============================================================

def obtener_batalla_actual():

    conexion = conectar_bd()
    cursor = conexion.cursor()

    # Primero una batalla activa
    cursor.execute("""
        SELECT
            e.id,
            e.etapa,
            COALESCE(g.nombre, ''),
            e.participante1,
            e.participante2,
            p1.nombre,
            p1.robot,
            p2.nombre,
            p2.robot,
            e.estado,
            e.ronda,
            COALESCE(e.criterio_ganador, ''),
            COALESCE(e.tiempo, ''),
            COALESCE(e.ataques1, 0),
            COALESCE(e.ataques2, 0)

        FROM enfrentamientos e

        INNER JOIN participantes p1
            ON e.participante1 = p1.id

        INNER JOIN participantes p2
            ON e.participante2 = p2.id

        LEFT JOIN grupos g
            ON e.grupo_id = g.id

        WHERE e.estado IN ('En curso', 'Pausada', 'Preparando')

        ORDER BY e.id

        LIMIT 1
    """)

    batalla = cursor.fetchone()

    # Si no hay activa, siguiente pendiente
    if batalla is None:

        cursor.execute("""
            SELECT
                e.id,
                e.etapa,
                COALESCE(g.nombre, ''),
                e.participante1,
                e.participante2,
                p1.nombre,
                p1.robot,
                p2.nombre,
                p2.robot,
                e.estado,
                e.ronda,
                COALESCE(e.criterio_ganador, ''),
                COALESCE(e.tiempo, ''),
                COALESCE(e.ataques1, 0),
                COALESCE(e.ataques2, 0)

            FROM enfrentamientos e

            INNER JOIN participantes p1
                ON e.participante1 = p1.id

            INNER JOIN participantes p2
                ON e.participante2 = p2.id

            LEFT JOIN grupos g
                ON e.grupo_id = g.id

            WHERE e.estado = 'Pendiente'

            ORDER BY e.id

            LIMIT 1
        """)

        batalla = cursor.fetchone()

    conexion.close()

    return batalla


# ============================================================
# ACTUALIZAR ESTADO
# ============================================================

def actualizar_estado(id_batalla, estado):

    conexion = conectar_bd()
    cursor = conexion.cursor()

    cursor.execute("""
        UPDATE enfrentamientos

        SET estado = ?

        WHERE id = ?
    """, (
        estado,
        id_batalla
    ))

    conexion.commit()
    conexion.close()

def guardar_reloj(id_batalla, estado, tiempo, inicio_epoch):
    """Guarda estado y referencia temporal para recuperar el cronómetro al volver."""
    conexion = conectar_bd()
    cursor = conexion.cursor()
    cursor.execute("""
        UPDATE enfrentamientos
        SET estado = ?, tiempo = ?, inicio_epoch = ?
        WHERE id = ?
    """, (estado, tiempo, inicio_epoch, id_batalla))
    conexion.commit()
    conexion.close()


def obtener_inicio_epoch(id_batalla):
    conexion = conectar_bd()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT inicio_epoch FROM enfrentamientos WHERE id = ?",
        (id_batalla,)
    )
    fila = cursor.fetchone()
    conexion.close()
    return fila[0] if fila else None


def obtener_estado_batalla(id_batalla):
    conexion = conectar_bd()
    try:
        fila = conexion.execute(
            "SELECT estado FROM enfrentamientos WHERE id = ?", (id_batalla,)
        ).fetchone()
        return fila[0] if fila else None
    finally:
        conexion.close()


def obtener_batallas_para_reinicio():
    """Lista solo batallas completadas que aún se pueden corregir."""
    conexion = conectar_bd()
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT e.id, e.etapa, COALESCE(g.nombre, ''), e.ronda,
               COALESCE(p1.robot, p1.nombre, 'Robot 1'),
               COALESCE(p2.robot, p2.nombre, 'Robot 2'), e.estado
        FROM enfrentamientos e
        LEFT JOIN grupos g ON g.id = e.grupo_id
        JOIN participantes p1 ON p1.id = e.participante1
        JOIN participantes p2 ON p2.id = e.participante2
        WHERE e.estado = 'Completado'
        ORDER BY e.id
    """)
    filas = cursor.fetchall()

    opciones = []
    for bid, etapa, grupo, ronda, robot1, robot2, estado in filas:
        if etapa in ("Grupo", "Todos"):
            cursor.execute("""
                SELECT COUNT(*) FROM enfrentamientos
                WHERE etapa NOT IN ('Grupo', 'Todos')
                  AND estado != 'Pendiente'
            """)
            if cursor.fetchone()[0]:
                continue
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM enfrentamientos
                WHERE etapa NOT IN ('Grupo', 'Todos')
                  AND COALESCE(ronda, 1) > ?
                  AND estado != 'Pendiente'
            """, (ronda or 1,))
            if cursor.fetchone()[0]:
                continue

        if etapa == "Grupo":
            fase = f"Grupo {grupo}".strip()
        elif etapa == "Todos":
            fase = "Todos contra todos"
        else:
            fase = etapa
        opciones.append((
            bid,
            f"#{bid} | {robot1} vs {robot2} | {fase}"
        ))

    conexion.close()
    return opciones


def reiniciar_batalla_en_bd(id_batalla):
    """Limpia solo el resultado seleccionado, sin reconstruir fases ni emparejamientos."""
    conexion = conectar_bd()
    try:
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT etapa, COALESCE(ronda, 1), estado,
                   participante1, participante2
            FROM enfrentamientos WHERE id = ?
        """, (id_batalla,))
        objetivo = cursor.fetchone()
        if not objetivo:
            return False, "La batalla seleccionada ya no existe."

        etapa, ronda, estado, participante1, participante2 = objetivo

        cursor.execute("""
            SELECT id, estado FROM enfrentamientos
            WHERE estado IN ('En curso', 'Pausada', 'Preparando')
        """)
        activas = cursor.fetchall()
        # Se permite reiniciar la batalla activa seleccionada; las demás
        # siguen bloqueadas para evitar interferir con otro combate.
        if any(bid != id_batalla for bid, _ in activas):
            return False, (
                "No se puede reiniciar otra batalla mientras hay una batalla "
                "en curso, pausada o en preparación. Selecciona la batalla activa."
            )
        if estado in ("En curso", "Pausada", "Preparando") and not any(
            bid == id_batalla for bid, _ in activas
        ):
            return False, "La batalla ya no está activa. Actualiza la pestaña e inténtalo de nuevo."

        # Se permite corregir una fase anterior mientras ninguna batalla
        # de una fase posterior haya comenzado.
        if etapa in ("Grupo", "Todos"):
            cursor.execute("""
                SELECT COUNT(*) FROM enfrentamientos
                WHERE etapa NOT IN ('Grupo', 'Todos')
                  AND estado != 'Pendiente'
            """)
            if cursor.fetchone()[0]:
                return False, (
                    "No se puede reiniciar esta batalla porque ya se jugó una "
                    "batalla de una fase posterior. Solo se pueden corregir "
                    "batallas de la fase actual."
                )
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM enfrentamientos
                WHERE etapa NOT IN ('Grupo', 'Todos')
                  AND COALESCE(ronda, 1) > ?
                  AND estado != 'Pendiente'
            """, (ronda,))
            if cursor.fetchone()[0]:
                return False, (
                    f"No se puede reiniciar {etapa} porque ya se jugó una "
                    "batalla de una fase posterior."
                )

        cursor.execute("""
            UPDATE enfrentamientos
            SET ganador = NULL,
                criterio_ganador = NULL,
                estado = 'Pendiente',
                tiempo = '0:00:00',
                inicio_epoch = NULL,
                ataques1 = 0,
                ataques2 = 0
            WHERE id = ?
        """, (id_batalla,))

        # En el torneo de exactamente dos robots se juega al mejor de tres.
        # Si el tercer combate había sido eliminado por un 2-0, recuperarlo
        # cuando se reabre una batalla para que la serie siga siendo válida.
        if etapa == "Final":
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
            total_grupos = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
            total_todos = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
            total_finales = cursor.fetchone()[0]
            if total_grupos == 0 and total_todos == 0 and total_finales == 2:
                cursor.execute("""
                    INSERT INTO enfrentamientos
                        (etapa, grupo_id, participante1, participante2,
                         estado, ronda, tiempo, ataques1, ataques2)
                    VALUES ('Final', NULL, ?, ?, 'Pendiente', 1, '0:00:00', 0, 0)
                """, (participante1, participante2))

        # Reemplazar el registro histórico de esta batalla; no dejar duplicados
        # del resultado anterior cuando se vuelva a registrar.
        cursor.execute(
            "DELETE FROM historial_batallas WHERE batalla_id = ?",
            (id_batalla,)
        )

        # Si se reinicia una batalla de la fase inicial, cualquier cuadro
        # eliminatorio todavía no iniciado deja de ser válido. Eliminarlo permite
        # que, al completar nuevamente la última batalla de grupos, se repita
        # el flujo original: Clasificaciones -> Continuar -> Eliminatorias.
        if etapa in ("Grupo", "Todos"):
            cursor.execute("""
                DELETE FROM enfrentamientos
                WHERE etapa NOT IN ('Grupo', 'Todos')
                  AND estado = 'Pendiente'
            """)
            cursor.execute("DELETE FROM llaves")
        else:
            # Mantener sincronizada únicamente la casilla de esta batalla en el
            # cuadro existente. No se recalculan clasificados ni emparejamientos.
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master
                WHERE type = 'table' AND name = 'llaves'
            """)
            if cursor.fetchone()[0] and etapa != "Final":
                cursor.execute("""
                    SELECT COUNT(*) FROM enfrentamientos
                    WHERE etapa = ? AND id <= ?
                """, (etapa, id_batalla))
                posicion = cursor.fetchone()[0]
                cursor.execute("""
                    UPDATE llaves
                    SET ganador = NULL, estado = 'Pendiente'
                    WHERE ronda = ? AND posicion = ?
                """, (etapa, posicion))

        conexion.commit()
    except Exception as error:
        conexion.rollback()
        return False, f"No se pudo reiniciar la batalla: {error}"
    finally:
        conexion.close()

    # Sincroniza los estados visibles de las llaves, pero no cambia los
    # participantes clasificados ni genera o modifica rondas posteriores.
    try:
        actualizar_llaves_tras_resultado()
    except Exception as error:
        print(f"No se pudieron sincronizar las llaves tras el reinicio: {error}")

    return True, "La batalla quedó pendiente y su resultado anterior fue eliminado."


def agregar_controles_reinicio(principal, contenedor, id_actual=None,
                                al_terminar_fase=None):
    """Muestra un reinicio rápido de la batalla actual y una lista desplegable."""
    opciones = obtener_batallas_para_reinicio()
    batalla_activa = obtener_batalla_actual()
    # La batalla actual debe aparecer incluso si es la primera y sigue pendiente.
    # Así los controles no desaparecen cuando todavía no hay resultados completados.
    if batalla_activa:
        id_activa = batalla_activa[0]
        if not any(bid == id_activa for bid, _ in opciones):
            etapa_activa = batalla_activa[1]
            grupo_activo = batalla_activa[2]
            if etapa_activa == "Grupo":
                fase_activa = f"Grupo {grupo_activo}".strip()
            elif etapa_activa == "Todos":
                fase_activa = "Todos contra todos"
            else:
                fase_activa = etapa_activa
            robot1_activo = batalla_activa[6] or batalla_activa[5] or "Robot 1"
            robot2_activo = batalla_activa[8] or batalla_activa[7] or "Robot 2"
            prefijo = "ACTUAL" if batalla_activa[9] == "Pendiente" else "ACTIVA"
            opciones.append((
                id_activa,
                f"{prefijo} #{id_activa} | {robot1_activo} vs {robot2_activo} | {fase_activa}"
            ))
    if not opciones:
        return

    marco = tk.Frame(principal, bg="#f3f5f7")
    marco.pack(fill="x", padx=22, pady=(8, 4))

    tk.Label(
        marco, text="REINICIAR BATALLA",
        font=("Segoe UI", 12, "bold"), fg="#7a858e", bg="#f3f5f7"
    ).pack(side="left", padx=(0, 10))

    valores = [etiqueta for _, etiqueta in opciones]
    seleccion = tk.StringVar()
    combo = ttk.Combobox(
        marco, textvariable=seleccion, values=valores,
        state="readonly", width=62, font=("Segoe UI", 12)
    )
    combo.pack(side="left", fill="x", expand=True, padx=(0, 10))

    # Dejar el selector vacío permite reiniciar directamente la batalla activa.
    # Si se elige una opción, se reinicia exactamente esa batalla.
    combo.set("")

    def ejecutar_reinicio():
        indice_actual = combo.current()
        if 0 <= indice_actual < len(opciones):
            bid, etiqueta = opciones[indice_actual]
        else:
            activa = obtener_batalla_actual()
            if not activa:
                messagebox.showwarning(
                    "Sin batalla disponible",
                    "No hay una batalla actual que se pueda reiniciar.",
                    parent=contenedor.winfo_toplevel()
                )
                return
            bid = activa[0]
            etapa_activa = activa[1]
            grupo_activo = activa[2]
            if etapa_activa == "Grupo":
                fase_activa = f"Grupo {grupo_activo}".strip()
            elif etapa_activa == "Todos":
                fase_activa = "Todos contra todos"
            else:
                fase_activa = etapa_activa
            r1 = activa[6] or activa[5] or "Robot 1"
            r2 = activa[8] or activa[7] or "Robot 2"
            etiqueta = f"ACTIVA #{bid} | {r1} vs {r2} | {fase_activa}"
        if not messagebox.askyesno(
            "Confirmar reinicio",
            f'¿Seguro que deseas reiniciar "{etiqueta}"?',
            parent=contenedor.winfo_toplevel()
        ):
            return

        exito, mensaje = reiniciar_batalla_en_bd(bid)
        if not exito:
            messagebox.showwarning(
                "No se puede reiniciar", mensaje,
                parent=contenedor.winfo_toplevel()
            )
            return

        # La confirmación inicial es la única ventana si el reinicio sale bien.
        mostrar_batallas(
            contenedor,
            al_terminar_fase=al_terminar_fase
        )

    boton = tk.Button(
        marco, text="REINICIAR", command=ejecutar_reinicio,
        font=("Segoe UI", 10, "bold"), bg="#C62828", fg="white",
        activebackground="#8E1B1B", activeforeground="white",
        relief="flat", bd=0, cursor="hand2", padx=14, pady=7
    )
    boton.pack(side="left")


# ============================================================
# REGISTRAR RESULTADO
# ============================================================

def registrar_resultado(
    id_batalla,
    ganador,
    criterio,
    tiempo,
    ataques1,
    ataques2
):

    conexion = conectar_bd()
    cursor = conexion.cursor()

    # Guardar el estado previo para archivar cada batalla solo una vez.
    cursor.execute(
        "SELECT estado FROM enfrentamientos WHERE id = ?",
        (id_batalla,)
    )
    estado_previo = cursor.fetchone()
    estado_previo = estado_previo[0] if estado_previo else None

    cursor.execute("""
        UPDATE enfrentamientos

        SET
            ganador = ?,
            criterio_ganador = ?,
            estado = 'Completado',
            tiempo = ?,
            ataques1 = ?,
            ataques2 = ?

        WHERE id = ?
    """, (
        ganador,
        criterio,
        tiempo,
        ataques1,
        ataques2,
        id_batalla
    ))

    # Archivar una copia de los datos del resultado. No depende de la tabla
    # de enfrentamientos activos, que puede borrarse al reiniciar una fase.
    if estado_previo != "Completado":
        cursor.execute("""
            SELECT
                e.etapa,
                COALESCE(g.nombre, ''),
                COALESCE(p1.robot, p1.nombre, '—'),
                COALESCE(p2.robot, p2.nombre, '—'),
                COALESCE(pg.robot, pg.nombre, 'Sin ganador'),
                COALESCE(e.tiempo, ''),
                COALESCE(e.ataques1, 0),
                COALESCE(e.ataques2, 0),
                COALESCE(e.criterio_ganador, '')
            FROM enfrentamientos e
            LEFT JOIN grupos g ON g.id = e.grupo_id
            LEFT JOIN participantes p1 ON p1.id = e.participante1
            LEFT JOIN participantes p2 ON p2.id = e.participante2
            LEFT JOIN participantes pg ON pg.id = e.ganador
            WHERE e.id = ?
        """, (id_batalla,))
        datos_historial = cursor.fetchone()

        if datos_historial:
            cursor.execute("""
                INSERT INTO historial_batallas (
                    batalla_id, etapa, grupo, robot1, robot2,
                    ganador, tiempo, ataques1, ataques2, motivo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_batalla,
                datos_historial[0],
                datos_historial[1],
                datos_historial[2],
                datos_historial[3],
                datos_historial[4],
                datos_historial[5],
                datos_historial[6],
                datos_historial[7],
                datos_historial[8]
            ))

    # En la serie al mejor de tres, cerrar automáticamente cuando un
    # participante consiga dos victorias y eliminar la tercera pelea pendiente.
    cursor.execute("""
        SELECT participante1, participante2
        FROM enfrentamientos
        WHERE id = ? AND etapa = 'Final'
    """, (id_batalla,))
    serie = cursor.fetchone()
    if serie:
        p1, p2 = serie
        cursor.execute("""
            SELECT ganador, COUNT(*)
            FROM enfrentamientos
            WHERE etapa = 'Final'
              AND participante1 = ? AND participante2 = ?
              AND estado = 'Completado'
            GROUP BY ganador
        """, (p1, p2))
        victorias = {fila[0]: fila[1] for fila in cursor.fetchall()}
        if max(victorias.values(), default=0) >= 2:
            cursor.execute("""
                DELETE FROM enfrentamientos
                WHERE etapa = 'Final'
                  AND participante1 = ? AND participante2 = ?
                  AND estado = 'Pendiente'
            """, (p1, p2))

    conexion.commit()
    conexion.close()

    # Sincronizar resultados con el cuadro, pero no crear la siguiente fase
    # automáticamente: el organizador la habilita desde la pestaña correspondiente.
    try:
        actualizar_llaves_tras_resultado()
    except Exception as error:
        print(f"Error al sincronizar los resultados con las llaves: {error}")


# ============================================================
# CENTRAR VENTANA
# ============================================================

def centrar_ventana(ventana, ancho, alto):

    ventana.update_idletasks()

    pantalla_ancho = ventana.winfo_screenwidth()

    x = (pantalla_ancho - ancho) // 2
    y = 0  # Pegada al borde superior de la pantalla

    ventana.geometry(
        f"{ancho}x{alto}+{x}+{y}"
    )


# ============================================================
# VENTANA RESULTADO
# ============================================================

def abrir_resultado(
    parent,
    batalla,
    actualizar,
    tiempo_agotado=False
):

    (
        id_batalla,
        etapa,
        grupo,
        participante1,
        participante2,
        nombre1,
        robot1,
        nombre2,
        robot2,
        estado,
        ronda,
        criterio_actual,
        tiempo_bd,
        ataques1_bd,
        ataques2_bd
    ) = batalla

    # El reloj y los ataques provienen de los valores sincronizados de la batalla.
    tiempo = tiempo_bd or "0:00:00"
    ataques1, ataques2 = dashboard_bridge.attacks()

    # --------------------------------------------------------
    # VENTANA
    # --------------------------------------------------------

    ventana = tk.Toplevel(parent)

    ventana.title(
        "Resultado de batalla"
    )

    centrar_ventana(
        ventana,
        760,
        720
    )

    ventana.transient(parent)

    # Asegura que el diálogo aparezca incluso si la aplicación estaba
    # minimizada o detrás de otra ventana cuando venció el tiempo.
    try:
        raiz = parent.winfo_toplevel()
        if raiz.state() == "iconic":
            raiz.deiconify()
        raiz.lift()
        ventana.lift()
        ventana.attributes("-topmost", True)
        ventana.after(700, lambda: ventana.attributes("-topmost", False))
        ventana.focus_force()
    except tk.TclError:
        pass

    # Mantiene el diálogo modal, pero ya visible y enfocado.
    ventana.grab_set()

    # No se puede cerrar con X
    ventana.protocol(
        "WM_DELETE_WINDOW",
        lambda: None
    )

    # --------------------------------------------------------
    # FONDO
    # --------------------------------------------------------

    ventana.configure(
        bg="#f3f5f7"
    )

    # --------------------------------------------------------
    # CONTENEDOR
    # --------------------------------------------------------

    principal = tk.Frame(
        ventana,
        bg="#f3f5f7"
    )

    principal.pack(
        fill="both",
        expand=True,
        padx=30,
        pady=25
    )

    # --------------------------------------------------------
    # ENCABEZADO ROJO DEL RESULTADO
    # --------------------------------------------------------

    cabecera_resultado = RoundedCard(
        principal, fill="#922b2b", outline="#922b2b",
        radius=22, padding=8, height=90
    )
    cabecera_resultado.pack(fill="x", pady=(0, 18))

    tk.Label(
        cabecera_resultado.content,
        text=f"RESULTADO • BATALLA {id_batalla}",
        font=("Segoe UI", 22, "bold"),
        fg="white", bg="#922b2b"
    ).pack(side="left", padx=20)

    tk.Label(
        cabecera_resultado.content,
        text=(f"Grupos - {grupo}" if etapa == "Grupo" and grupo
              else "Todos vs Todos" if etapa == "Todos" else etapa),
        font=("Segoe UI", 12, "bold"),
        fg="white", bg="#7f1d1d", padx=12, pady=7
    ).pack(side="right", padx=18)

    # --------------------------------------------------------
    # DATOS
    # --------------------------------------------------------

    datos = RoundedCard(
        principal, fill="white", outline="#d9dee3",
        radius=20, padding=8, height=94
    )
    datos.pack(fill="x", pady=(0, 20))

    for columna in range(3):
        datos.content.grid_columnconfigure(columna, weight=1)

    estadisticas = [
        ("ATAQUES R1", str(ataques1)),
        ("TIEMPO", tiempo),
        ("ATAQUES R2", str(ataques2)),
    ]

    for columna, (titulo, valor) in enumerate(estadisticas):
        tk.Label(
            datos.content, text=titulo,
            font=("Segoe UI", 9, "bold"),
            fg="#7a858e", bg="white"
        ).grid(row=0, column=columna, padx=18, pady=(12, 0), sticky="ew")

        if titulo == "TIEMPO":
            tiempo_resultado_frame = tk.Frame(datos.content, bg="white")
            tiempo_resultado_frame.grid(
                row=1, column=columna, padx=18, pady=(0, 12)
            )
            tiempo_resultado_principal = tk.Label(
                tiempo_resultado_frame, text="00:00",
                font=("Segoe UI", 18, "bold"), fg="#17202a", bg="white",
                padx=0, pady=0, bd=0, highlightthickness=0, anchor="e"
            )
            tiempo_resultado_principal.pack(side="left", anchor="s", padx=0, pady=0)
            tiempo_resultado_centesimas = tk.Label(
                tiempo_resultado_frame, text="00",
                font=("Segoe UI", 10, "bold"), fg="#17202a", bg="white",
                padx=0, pady=0, bd=0, highlightthickness=0, anchor="w"
            )
            tiempo_resultado_centesimas.pack(
                side="left", anchor="s", padx=0, pady=(0, 2), ipadx=0
            )
            _actualizar_tiempo_visual(
                tiempo_resultado_principal, tiempo_resultado_centesimas, valor
            )
        else:
            tk.Label(
                datos.content, text=valor,
                font=("Segoe UI", 18, "bold"),
                fg="#17202a", bg="white"
            ).grid(row=1, column=columna, padx=18, pady=(0, 12), sticky="ew")

    # --------------------------------------------------------
    # GANADOR
    # --------------------------------------------------------

    tk.Label(
        principal,
        text="SELECCIONA EL GANADOR",
        font=("Segoe UI", 13, "bold"),
        fg="#17202a",
        bg="#f3f5f7"
    ).pack(
        anchor="w",
        pady=(0, 8)
    )

    ganador = tk.IntVar(value=0)

    marco_ganadores = tk.Frame(
        principal,
        bg="#f3f5f7"
    )

    marco_ganadores.pack(
        fill="x"
    )

    boton1 = None
    boton2 = None

    def seleccionar_ganador(valor):
        ganador.set(valor)
        seleccionado1 = valor == participante1
        seleccionado2 = valor == participante2
        boton1.config(
            bg="#2563eb" if seleccionado1 else "#ffffff",
            fg="white" if seleccionado1 else "#17202a",
            activebackground="#2563eb" if seleccionado1 else "#dbeafe",
            activeforeground="white" if seleccionado1 else "#17202a"
        )
        boton2.config(
            bg="#2563eb" if seleccionado2 else "#ffffff",
            fg="white" if seleccionado2 else "#17202a",
            activebackground="#2563eb" if seleccionado2 else "#dbeafe",
            activeforeground="white" if seleccionado2 else "#17202a"
        )

    boton1 = RoundedButton(
        marco_ganadores,
        text=robot1, secondary_text=nombre1,
        command=lambda: seleccionar_ganador(participante1),
        width=300, height=78, bg="#ffffff", fg="#17202a",
        activebackground="#dbeafe", activeforeground="#17202a",
        font=("Segoe UI", 16, "bold"), secondary_font=("Segoe UI", 14),
        radius=16
    )
    boton1.pack(side="left", expand=True, fill="both", padx=(0, 7))

    boton2 = RoundedButton(
        marco_ganadores,
        text=robot2, secondary_text=nombre2,
        command=lambda: seleccionar_ganador(participante2),
        width=300, height=78, bg="#ffffff", fg="#17202a",
        activebackground="#dbeafe", activeforeground="#17202a",
        font=("Segoe UI", 16, "bold"), secondary_font=("Segoe UI", 14),
        radius=16
    )
    boton2.pack(side="left", expand=True, fill="both", padx=(7, 0))

    # --------------------------------------------------------
    # CRITERIO
    # --------------------------------------------------------

    tk.Label(
        principal,
        text="CRITERIO DE VICTORIA",
        font=("Segoe UI", 13, "bold"),
        fg="#17202a",
        bg="#f3f5f7"
    ).pack(
        anchor="w",
        pady=(20, 8)
    )

    criterio = tk.StringVar(value="")

    marco_criterios = tk.Frame(
        principal,
        bg="#f3f5f7"
    )

    marco_criterios.pack(
        fill="x"
    )

    criterios = [
        "Expulsión del Dojo",
        "Oponente no encendió",
        "Inactividad del oponente",
        "Oponente no se presentó",
        "Mayor cantidad de ataques",
        "Decisión del juez"
    ]

    botones_criterio = {}

    def seleccionar_criterio(texto):
        criterio.set(texto)
        for nombre, boton in botones_criterio.items():
            seleccionado = nombre == texto
            boton.config(
                bg="#2563eb" if seleccionado else "#ffffff",
                fg="white" if seleccionado else "#263238",
                activebackground="#2563eb" if seleccionado else "#dbeafe",
                activeforeground="white" if seleccionado else "#263238"
            )

    for texto in criterios:
        boton = RoundedButton(
            marco_criterios,
            text=texto,
            command=lambda opcion=texto: seleccionar_criterio(opcion),
            width=620, height=38,
            bg="#ffffff", fg="#263238",
            activebackground="#dbeafe", activeforeground="#263238",
            font=("Segoe UI", 11, "bold"), radius=13
        )
        boton.pack(fill="x", pady=3)
        botones_criterio[texto] = boton

    # Si se agotaron los dos minutos, sugerir automáticamente al robot con
    # más ataques y el criterio correspondiente. Si empatan, no se adivina.
    if tiempo_agotado and ataques1 != ataques2:
        if ataques1 > ataques2:
            seleccionar_ganador(participante1)
        else:
            seleccionar_ganador(participante2)
        seleccionar_criterio("Mayor cantidad de ataques")

    # --------------------------------------------------------
    # REGISTRAR
    # --------------------------------------------------------

    def registrar():
        global BLOQUEO_CONTROLES_HASTA
        nonlocal ataques1, ataques2
        ataques1, ataques2 = dashboard_bridge.attacks()

        if ganador.get() == 0:

            messagebox.showwarning(
                "Resultado incompleto",
                "Selecciona el ganador.",
                parent=ventana
            )

            return

        if criterio.get() == "":

            messagebox.showwarning(
                "Resultado incompleto",
                "Selecciona el criterio de victoria.",
                parent=ventana
            )

            return

        # Guardamos primero el resultado en Python.
        ganador_id = ganador.get()
        criterio_texto = criterio.get()
        registrar_resultado(
            id_batalla,
            ganador_id,
            criterio_texto,
            tiempo,
            ataques1,
            ataques2
        )

        ganador_robot = robot1 if ganador_id == participante1 else robot2
        ganador_persona = nombre1 if ganador_id == participante1 else nombre2
        imagen_ganador1 = _imagen_dashboard(robot1, participante1)
        imagen_ganador2 = _imagen_dashboard(robot2, participante2, imagen_ganador1)
        BLOQUEO_CONTROLES_HASTA = time.monotonic() + 10.0
        dashboard_bridge.set_time(_tiempo_a_segundos(tiempo), running=False)
        dashboard_bridge.trigger(
            "winner", winner=ganador_robot, winner_person=ganador_persona,
            reason=criterio_texto, elapsed_seconds=_tiempo_a_segundos(tiempo),
            attacks1=ataques1, attacks2=ataques2, phase="finished",
            status="BATALLA FINALIZADA", battle_id=id_batalla,
            battle_number=id_batalla, robot1=robot1, robot2=robot2,
            person1=nombre1, person2=nombre2,
            robot1_image=imagen_ganador1, robot2_image=imagen_ganador2
        )

        ventana.grab_release()
        ventana.destroy()

        # ACTUALIZAR INMEDIATAMENTE
        actualizar()

    ventana.bind(
        "<Return>",
        lambda evento: registrar()
    )

    # --------------------------------------------------------
    # TEXTO INFERIOR
    # --------------------------------------------------------

    tk.Label(
        principal,
        text="Presiona ENTER para registrar",
        font=("Segoe UI", 11, "italic"),
        fg="#68737d",
        bg="#f3f5f7"
    ).pack(
        pady=(12, 0)
    )


# ============================================================
# INTERFAZ BATALLAS
# ============================================================

def mostrar_batallas(contenedor, al_terminar_fase=None, resultado_recien_guardado=False):

    # --------------------------------------------------------
    # LIMPIAR LA PÁGINA ANTES DE DIBUJAR
    # --------------------------------------------------------

    for widget in contenedor.winfo_children():
        widget.destroy()

    batalla = obtener_batalla_actual()

    # --------------------------------------------------------
    # PRINCIPAL
    # --------------------------------------------------------

    principal = tk.Frame(
        contenedor,
        bg="#f3f5f7"
    )

    principal.pack(
        fill="both",
        expand=True
    )

    # --------------------------------------------------------
    # SI NO HAY BATALLAS
    # --------------------------------------------------------

    if batalla is None:

        agregar_controles_reinicio(
            principal, contenedor, id_actual=None,
            al_terminar_fase=al_terminar_fase
        )

        dashboard_bridge.set_time(0, running=False)
        dashboard_bridge.set_state({
            "battle_id": None, "battle_number": 0,
            "robot1": "POR DEFINIR", "robot2": "POR DEFINIR",
            "robot1_image": "/Imagenes/R_Amarillo.png", "robot2_image": "/Imagenes/R_Morado.png",
            "person1": "", "person2": "", "phase": "ready",
            "status": "NO HAY BATALLAS PENDIENTES", "elapsed_seconds": 0,
            "countdown_active": False, "countdown_value": "3",
            "winner": "", "winner_person": "", "reason": ""
        })
        dashboard_bridge.trigger("no_battles")

        conexion = conectar_bd()
        cursor = conexion.cursor()
        campeon = None
        marcador = None
        subtitulo = "TORNEO FINALIZADO"

        # Garantiza que la pantalla de cierre también funcione si Batallas se abre primero.
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

        # Si hay cuadro eliminatorio, el último registro de llaves corresponde a la final.
        cursor.execute("SELECT COUNT(*) FROM llaves")
        hay_llaves = cursor.fetchone()[0] > 0
        if hay_llaves:
            cursor.execute("""
                SELECT l.ganador, l.estado, p.robot, p.nombre
                FROM llaves l
                LEFT JOIN participantes p ON p.id = l.ganador
                ORDER BY l.id DESC
                LIMIT 1
            """)
            final_llave = cursor.fetchone()
            if final_llave and final_llave[0] is not None and final_llave[1] == "Completado":
                campeon = (final_llave[2] or "Robot campeón", final_llave[3] or "")
                subtitulo = "CAMPEÓN DE LAS LLAVES ELIMINATORIAS"

        # Competencia de 2 participantes: serie programada de tres batallas.
        if campeon is None:
            cursor.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN estado = 'Completado' THEN 1 ELSE 0 END)
                FROM enfrentamientos
                WHERE etapa = 'Final'
            """)
            total_finales, finales_completadas = cursor.fetchone()
            finales_completadas = finales_completadas or 0

            if total_finales >= 2 and finales_completadas == total_finales:
                cursor.execute("""
                    SELECT e.ganador, COUNT(*) AS victorias, p.robot, p.nombre
                    FROM enfrentamientos e
                    JOIN participantes p ON p.id = e.ganador
                    WHERE e.etapa = 'Final' AND e.estado = 'Completado'
                    GROUP BY e.ganador, p.robot, p.nombre
                    ORDER BY victorias DESC
                    LIMIT 1
                """)
                fila = cursor.fetchone()
                if fila:
                    campeon = (fila[2], fila[3])
                    cursor.execute("""
                        SELECT COUNT(*) FROM enfrentamientos
                        WHERE etapa = 'Final' AND estado = 'Completado'
                          AND ganador != ?
                    """, (fila[0],))
                    derrotas = cursor.fetchone()[0]
                    marcador = f"Serie final: {fila[1]} - {derrotas}"
                    subtitulo = "CAMPEÓN • SERIE AL MEJOR DE 3"

            # Final directa entre los dos mejores de todos contra todos.
            elif total_finales == 1 and finales_completadas == 1:
                cursor.execute("""
                    SELECT p.robot, p.nombre
                    FROM enfrentamientos e
                    JOIN participantes p ON p.id = e.ganador
                    WHERE e.etapa = 'Final' AND e.estado = 'Completado'
                    LIMIT 1
                """)
                fila = cursor.fetchone()
                if fila:
                    campeon = (fila[0], fila[1])

        # Al terminar grupos, la clasificación y el botón de llaves se gestionan
        # desde la página Enfrentamientos.
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Grupo'")
        total_grupos = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM enfrentamientos
            WHERE etapa = 'Grupo' AND estado != 'Completado'
        """)
        grupos_pendientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Todos'")
        total_todos = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM enfrentamientos
            WHERE etapa = 'Todos' AND estado != 'Completado'
        """)
        todos_pendientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enfrentamientos WHERE etapa = 'Final'")
        total_finales_actual = cursor.fetchone()[0]
        conexion.close()

        accion_tipo = None
        destino_fase = None
        titulo_fase = "NO HAY BATALLAS PENDIENTES"
        detalle_fase = "La competencia está al día."

        if total_grupos > 0 and grupos_pendientes == 0 and not hay_llaves:
            accion_tipo = "llaves"
            destino_fase = "clasificaciones"
            titulo_fase = "FASE DE GRUPOS FINALIZADA"
            detalle_fase = ""
        elif total_todos > 0 and todos_pendientes == 0 and total_finales_actual == 0:
            accion_tipo = "final"
            destino_fase = "clasificaciones"
            titulo_fase = "TODOS CONTRA TODOS FINALIZADO"
            detalle_fase = "La clasificación está lista. Puedes continuar con la final."
        elif hay_llaves:
            conexion_rondas = conectar_bd()
            cursor_rondas = conexion_rondas.cursor()
            cursor_rondas.execute("""
                SELECT etapa, COUNT(*),
                       SUM(CASE WHEN estado = 'Completado' THEN 1 ELSE 0 END)
                FROM enfrentamientos
                WHERE etapa NOT IN ('Grupo', 'Todos', 'Final')
                GROUP BY etapa
                ORDER BY MAX(id) DESC
                LIMIT 1
            """)
            ultima = cursor_rondas.fetchone()
            conexion_rondas.close()
            if ultima and ultima[0] and ultima[1] > 0 and ultima[2] == ultima[1]:
                accion_tipo = "ronda"
                destino_fase = "eliminatorias"
                titulo_fase = f"FASE {str(ultima[0]).upper()} FINALIZADA"
                detalle_fase = ""

        # Al terminar la fase inicial, muestra el aviso con CONTINUAR deshabilitado
        # y redirige a Clasificaciones automáticamente. Al regresar manualmente a Batallas,
        # el botón estará habilitado para pasar a Eliminatorias.
        redireccion_clasificaciones_pendiente = (
            resultado_recien_guardado
            and accion_tipo in ("llaves", "final")
            and al_terminar_fase
        )
        if redireccion_clasificaciones_pendiente:
            al_terminar_fase("clasificaciones", detalle_fase, 3000)

        if campeon:
            tk.Label(
                principal, text="🏆", font=("Segoe UI Emoji", 42),
                fg="#D97706", bg="#f3f5f7"
            ).pack(pady=(48, 0))
            tk.Label(
                principal, text="TORNEO FINALIZADO",
                font=("Segoe UI", 16, "bold"), fg="#68737d", bg="#f3f5f7"
            ).pack(pady=(4, 8))
            tk.Label(
                principal, text=subtitulo,
                font=("Segoe UI", 22, "bold"), fg="#166534", bg="#f3f5f7"
            ).pack(pady=(0, 18))
            tk.Label(
                principal, text=campeon[0],
                font=("Segoe UI", 36, "bold"), fg="#17202a", bg="#f3f5f7"
            ).pack(pady=(0, 6))
            tk.Label(
                principal, text=campeon[1],
                font=("Segoe UI", 20), fg="#475569", bg="#f3f5f7"
            ).pack(pady=(0, 12))
            if marcador:
                tk.Label(
                    principal, text=marcador,
                    font=("Segoe UI", 15, "bold"), fg="#17202a", bg="#f3f5f7"
                ).pack()
        elif accion_tipo:
            tk.Label(
                principal, text="✓", font=("Segoe UI", 46, "bold"),
                fg="#16A34A", bg="#f3f5f7"
            ).pack(pady=(75, 12))
            tk.Label(
                principal, text=titulo_fase,
                font=("Segoe UI", 25, "bold"), fg="#17202a", bg="#f3f5f7",
                wraplength=900, justify="center"
            ).pack(pady=(0, 12))
            if detalle_fase:
                tk.Label(
                    principal, text=detalle_fase,
                    font=("Segoe UI", 15), fg="#475569", bg="#f3f5f7",
                    wraplength=820, justify="center"
                ).pack(pady=(0, 24))

            boton_continuar = None

            def continuar_desde_batallas():
                if accion_tipo == "llaves":
                    exito, mensaje = generar_llaves_manualmente()
                elif accion_tipo == "final":
                    exito, mensaje = generar_final_todos_manualmente()
                else:
                    exito, mensaje = avanzar_ronda_manualmente()

                if exito:
                    if accion_tipo in ("llaves", "ronda") and al_terminar_fase:
                        boton_continuar.config(
                            state="disabled",
                            text="ABRIENDO ELIMINATORIAS..."
                        )
                        al_terminar_fase("eliminatorias", mensaje, 0)
                    else:
                        mostrar_batallas(
                            contenedor,
                            al_terminar_fase=al_terminar_fase
                        )
                else:
                    messagebox.showwarning(
                        "No se puede continuar", mensaje,
                        parent=contenedor.winfo_toplevel()
                    )

            texto_continuar = (
                "SERÁS DIRIGIDO A CLASIFICACIONES"
                if redireccion_clasificaciones_pendiente
                else "REVISA LAS ELIMINATORIAS"
                if accion_tipo == "llaves"
                else "CONTINUAR A LA FINAL"
                if accion_tipo == "final"
                else "CONTINUAR A LA SIGUIENTE RONDA"
            )
            boton_continuar = RoundedButton(
                principal, text=texto_continuar,
                command=continuar_desde_batallas,
                width=330, height=54,
                bg="#C62828", fg="#FFFFFF",
                activebackground="#8E1B1B", activeforeground="#FFFFFF",
                disabledbackground="#CBD5E1",
                font=("Segoe UI", 13, "bold"), radius=14,
                state="disabled" if redireccion_clasificaciones_pendiente else "normal"
            )
            boton_continuar.pack()
        else:
            tk.Label(
                principal, text="COMPETENCIA",
                font=("Segoe UI", 30, "bold"), fg="#17202a", bg="#f3f5f7"
            ).pack(pady=(90, 15))
            tk.Label(
                principal, text="No hay batallas pendientes",
                font=("Segoe UI", 16), fg="#68737d", bg="#f3f5f7"
            ).pack()
        return

    (
        id_batalla,
        etapa,
        grupo,
        participante1,
        participante2,
        nombre1,
        robot1,
        nombre2,
        robot2,
        estado,
        ronda,
        criterio_actual,
        tiempo_bd,
        ataques1_bd,
        ataques2_bd
    ) = batalla

    agregar_controles_reinicio(
        principal, contenedor, id_actual=id_batalla,
        al_terminar_fase=al_terminar_fase
    )

    imagen1 = _imagen_dashboard(robot1, participante1)
    imagen2 = _imagen_dashboard(robot2, participante2, imagen1)
    fase_dashboard = {
        "Pendiente": "ready",
        "Preparando": "ready",
        "En curso": "running",
        "Pausada": "paused",
        "Completado": "finished",
    }.get(estado, "ready")
    estado_puente_previo = dashboard_bridge.get_state()
    cuenta_ya_activa = (
        estado == "Preparando"
        and estado_puente_previo.get("battle_id") == id_batalla
        and estado_puente_previo.get("countdown_active", False)
    )
    dashboard_bridge.set_time(
        _tiempo_a_segundos(tiempo_bd), running=(estado == "En curso")
    )
    dashboard_bridge.set_state({
        "battle_id": id_batalla, "battle_number": id_batalla,
        "robot1": str(robot1 or nombre1 or "ROBOT 1"),
        "robot2": str(robot2 or nombre2 or "ROBOT 2"),
        "robot1_image": imagen1, "robot2_image": imagen2,
        "person1": str(nombre1 or ""), "person2": str(nombre2 or ""),
        "phase": fase_dashboard, "status": str(estado or "Pendiente").upper(),
        "elapsed_seconds": _tiempo_a_segundos(tiempo_bd),
        "countdown_active": cuenta_ya_activa,
        "countdown_value": estado_puente_previo.get("countdown_value", "3") if cuenta_ya_activa else "3",
        "winner": "", "winner_person": "", "reason": ""
    })
    if estado == "Pendiente":
        dashboard_bridge.trigger("next")
    elif estado in ("Preparando", "En curso", "Pausada"):
        dashboard_bridge.trigger("home")

    # --------------------------------------------------------
    # ENCABEZADO
    # --------------------------------------------------------

    encabezado = RoundedCard(
        principal, fill="#922b2b", outline="#922b2b",
        radius=24, padding=10, height=112
    )
    encabezado.pack(fill="x", padx=18, pady=(8, 0))

    encabezado_interior = encabezado.content
    encabezado_interior.grid_columnconfigure(0, weight=3, uniform="encabezado")
    encabezado_interior.grid_columnconfigure(1, weight=1, uniform="encabezado")
    encabezado_interior.grid_rowconfigure(0, weight=1)

    if etapa == "Grupo" and grupo:
        modo_texto = f"GRUPOS - {grupo.upper()} - RONDA {ronda or 1}"
    elif etapa == "Todos":
        modo_texto = "TODOS CONTRA TODOS"
    else:
        modo_texto = f"ELIMINATORIAS - {str(etapa).upper()}"

    tk.Label(
        encabezado_interior, text=modo_texto,
        font=("Segoe UI", 20, "bold"), fg="#fbeaea", bg="#922b2b",
        anchor="w", justify="left", wraplength=780
    ).grid(row=0, column=0, sticky="w", padx=(22, 10), pady=8)

    tk.Label(
        encabezado_interior, text=f"BATALLA {id_batalla}",
        font=("Segoe UI", 28, "bold"), fg="white", bg="#922b2b",
        anchor="center"
    ).grid(row=0, column=1, sticky="nsew", padx=(4, 18), pady=8)

    # Las batallas se controlan completamente desde Python; no se usa puerto serie.

    # --------------------------------------------------------
    # ESTADO
    # --------------------------------------------------------

    estado_frame = RoundedCard(
        principal, fill="#e8eeee", outline="#e8eeee",
        radius=20, padding=5, height=44
    )
    estado_frame.pack(pady=10)

    estado_label = tk.Label(
        estado_frame.content, text=estado.upper(),
        font=("Segoe UI", 11, "bold"), fg="#17202a",
        bg="#e8eeee", padx=25, pady=5
    )
    estado_label.pack()

    # --------------------------------------------------------
    # COMBATE
    # --------------------------------------------------------

    combate = tk.Frame(
        principal,
        bg="#f3f5f7"
    )

    combate.pack(
        fill="x",
        padx=60
    )

    # --------------------------------------------------------
    # TARJETA ROBOT 1
    # --------------------------------------------------------

    tarjeta1_card = RoundedCard(
        combate, fill="#ffffff", outline="#d7dde2",
        radius=20, padding=5, height=132
    )
    tarjeta1_card.pack(side="left", expand=True, fill="both")
    tarjeta1 = tarjeta1_card.content

    tarjeta1.grid_columnconfigure(0, weight=1)
    tarjeta1.grid_rowconfigure(0, weight=1)
    tarjeta1.grid_rowconfigure(4, weight=1)
    tk.Label(
        tarjeta1, text="ROBOT 1",
        font=("Segoe UI", 12, "bold"), fg="#7a858e", bg="white"
    ).grid(row=1, column=0, pady=(0, 2))

    tk.Label(
        tarjeta1, text=robot1,
        font=("Segoe UI", 19, "bold"), fg="#17202a", bg="white"
    ).grid(row=2, column=0)

    tk.Label(
        tarjeta1, text=nombre1,
        font=("Segoe UI", 14), fg="#68737d", bg="white"
    ).grid(row=3, column=0, pady=(2, 0))

    # --------------------------------------------------------
    # VS
    # --------------------------------------------------------

    tk.Label(
        combate,
        text="VS",
        font=("Segoe UI", 19, "bold"),
        fg="#68737d",
        bg="#f3f5f7"
    ).pack(
        side="left",
        padx=22
    )

    # --------------------------------------------------------
    # TARJETA ROBOT 2
    # --------------------------------------------------------

    tarjeta2_card = RoundedCard(
        combate, fill="#ffffff", outline="#d7dde2",
        radius=20, padding=5, height=132
    )
    tarjeta2_card.pack(side="left", expand=True, fill="both")
    tarjeta2 = tarjeta2_card.content

    tarjeta2.grid_columnconfigure(0, weight=1)
    tarjeta2.grid_rowconfigure(0, weight=1)
    tarjeta2.grid_rowconfigure(4, weight=1)
    tk.Label(
        tarjeta2, text="ROBOT 2",
        font=("Segoe UI", 12, "bold"), fg="#7a858e", bg="white"
    ).grid(row=1, column=0, pady=(0, 2))

    tk.Label(
        tarjeta2, text=robot2,
        font=("Segoe UI", 19, "bold"), fg="#17202a", bg="white"
    ).grid(row=2, column=0)

    tk.Label(
        tarjeta2, text=nombre2,
        font=("Segoe UI", 14), fg="#68737d", bg="white"
    ).grid(row=3, column=0, pady=(2, 0))

    # --------------------------------------------------------
    # PANEL TIEMPO / ATAQUES
    # --------------------------------------------------------

    datos_card = RoundedCard(
        principal, fill="white", outline="#d7dde2",
        radius=22, padding=8, height=112
    )
    datos_card.pack(fill="x", padx=60, pady=12)
    datos = datos_card.content
    for columna in range(3):
        datos.grid_columnconfigure(columna, weight=1, uniform="estadisticas")

    tk.Label(
        datos, text="⚔  ATAQUES R1",
        font=("Segoe UI", 9, "bold"), fg="#7a858e", bg="white"
    ).grid(row=0, column=0, pady=(12, 0), sticky="ew")
    ataques1_label = tk.Label(
        datos, text="0", font=("Segoe UI", 25, "bold"),
        fg="#17202a", bg="white"
    )
    ataques1_label.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
    dashboard_bridge.set_attacks_callback(
        lambda a1, a2: principal.after(
            0, lambda: (
                ataques1_label.config(text=str(a1)),
                ataques2_label.config(text=str(a2))
            ) if principal.winfo_exists() else None
        )
    )
    principal.bind(
        "<Destroy>",
        lambda evento: dashboard_bridge.set_attacks_callback(None)
        if evento.widget is principal else None,
        add="+"
    )

    tk.Label(
        datos, text="◷  TIEMPO",
        font=("Segoe UI", 9, "bold"), fg="#7a858e", bg="white"
    ).grid(row=0, column=1, pady=(12, 0), sticky="ew")
    tiempo_frame = tk.Frame(datos, bg="white")
    tiempo_frame.grid(row=1, column=1, padx=18, pady=(0, 12))
    tiempo_principal_label = tk.Label(
        tiempo_frame, text="00:00", font=("Segoe UI", 25, "bold"),
        fg="#17202a", bg="white", padx=0, bd=0
    )
    tiempo_principal_label.pack(side="left", anchor="s", padx=0, ipadx=0)
    tiempo_centesimas_label = tk.Label(
        tiempo_frame, text="00", font=("Segoe UI", 13, "bold"),
        fg="#17202a", bg="white", padx=0, bd=0
    )
    tiempo_centesimas_label.pack(side="left", anchor="s", padx=0, pady=(0, 3), ipadx=0)

    tk.Label(
        datos, text="⚔  ATAQUES R2",
        font=("Segoe UI", 9, "bold"), fg="#7a858e", bg="white"
    ).grid(row=0, column=2, pady=(12, 0), sticky="ew")
    ataques2_label = tk.Label(
        datos, text="0", font=("Segoe UI", 25, "bold"),
        fg="#17202a", bg="white"
    )
    ataques2_label.grid(row=1, column=2, padx=18, pady=(0, 12), sticky="ew")

    # --------------------------------------------------------
    # CONTROLES
    # --------------------------------------------------------

    controles = tk.Frame(
        principal,
        bg="#f3f5f7"
    )

    controles.pack(
        pady=5
    )

    boton_iniciar = RoundedButton(
        controles, text="▶  INICIAR", command=None,
        width=150, height=48, bg="#16a34a", fg="white",
        activebackground="#15803d", activeforeground="white",
        font=("Segoe UI", 11, "bold"), radius=16
    )
    boton_pausar = RoundedButton(
        controles, text="Ⅱ  PAUSAR", command=None,
        width=150, height=48, bg="#e9a23b", fg="white",
        activebackground="#d18b28", activeforeground="white",
        font=("Segoe UI", 11, "bold"), radius=16
    )
    boton_continuar = RoundedButton(
        controles, text="▶  CONTINUAR", command=None,
        width=150, height=48, bg="#2563eb", fg="white",
        activebackground="#1d4ed8", activeforeground="white",
        font=("Segoe UI", 11, "bold"), radius=16
    )
    boton_finalizar = RoundedButton(
        controles, text="■  FINALIZAR", command=None,
        width=150, height=48, bg="#dc3545", fg="white",
        activebackground="#b91c2b", activeforeground="white",
        font=("Segoe UI", 11, "bold"), radius=16
    )

    boton_iniciar.pack(
        side="left",
        padx=5
    )

    boton_pausar.pack(
        side="left",
        padx=5
    )

    boton_continuar.pack(
        side="left",
        padx=5
    )

    boton_finalizar.pack(
        side="left",
        padx=5
    )

    # --------------------------------------------------------
    # ACTUALIZACIÓN LOCAL DEL CRONÓMETRO
    # --------------------------------------------------------

    ventana_raiz = principal.winfo_toplevel()

    def interfaz_batallas_disponible():
        try:
            return bool(principal.winfo_exists())
        except tk.TclError:
            return False

    finalizacion_automatica_activada = False
    alarma_activada = False
    alarma_audio_completada = False
    alarma_inicio_monotonic = None
    inicio_epoch_bd = obtener_inicio_epoch(id_batalla)
    reloj = RelojBatalla(
        tiempo_inicial=tiempo_bd or "0:00:00",
        inicio_epoch=inicio_epoch_bd if estado == "En curso" else None
    )
    if estado == "Pausada":
        reloj.estado = "Pausada"
    elif estado == "En curso":
        reloj.estado = "En curso"
        # Compatibilidad con batallas que ya estaban activas antes de guardar
        # la marca temporal en la base de datos.
        if inicio_epoch_bd is None:
            reloj._inicio_tramo = time.time()
            guardar_reloj(
                id_batalla, "En curso",
                reloj.obtener_tiempo_base(), reloj.inicio_epoch()
            )
    cuenta_regresiva_activa = cuenta_ya_activa
    cuenta_regresiva_restante = 0

    def actualizar_datos():
        nonlocal alarma_activada, alarma_audio_completada, alarma_inicio_monotonic
        nonlocal cuenta_regresiva_activa

        # El reloj y la finalización automática deben seguir activos aunque
        # el usuario cambie de pestaña y se destruya el panel de Batallas.
        # Si la batalla se reinició desde el control superior, detener este
        # ciclo antiguo para que no siga avanzando ni abra el diálogo de ganador.
        if reloj.estado in ("En curso", "Pausada") or cuenta_regresiva_activa:
            conexion_estado = conectar_bd()
            try:
                fila_estado = conexion_estado.execute(
                    "SELECT estado FROM enfrentamientos WHERE id = ?", (id_batalla,)
                ).fetchone()
            finally:
                conexion_estado.close()
            estado_bd_actual = fila_estado[0] if fila_estado else None
            if estado_bd_actual not in ("En curso", "Pausada", "Preparando"):
                reloj.estado = "Finalizada"
                cuenta_regresiva_activa = False
                dashboard_bridge.set_time(0, running=False)
                dashboard_bridge.set_state({
                    "battle_id": id_batalla, "phase": "ready",
                    "status": "BATALLA REINICIADA", "elapsed_seconds": 0,
                    "countdown_active": False, "countdown_value": ""
                })
                return

        if (not interfaz_batallas_disponible()
                and not cuenta_regresiva_activa
                and reloj.estado != "En curso"):
            return

        tiempo_actual = reloj.segundos()
        dashboard_bridge.set_time(tiempo_actual)
        if (not alarma_activada and reloj.estado == "En curso" and reloj.segundos() >= 115):
            alarma_activada = True
            alarma_inicio_monotonic = time.monotonic()
            dashboard_bridge.trigger("alarm")

        # Se espera a que termine el audio de alarma antes de elegir ganador.
        # Si el navegador no confirma el final, se conserva un límite de seguridad.
        if (
            not cuenta_regresiva_activa
            and reloj.estado == "En curso"
            and reloj.segundos() >= 120
            and (
                not alarma_activada
                or alarma_audio_completada
                or (alarma_inicio_monotonic is not None
                    and time.monotonic() - alarma_inicio_monotonic >= 10)
            )
        ):
            finalizar(automatica=True)
            return

        # La actualización periódica no debe tapar los números 3, 2 y 1.
        if not cuenta_regresiva_activa and interfaz_batallas_disponible():
            _actualizar_tiempo_visual(tiempo_principal_label, tiempo_centesimas_label, reloj.obtener_tiempo())
        ventana_raiz.after(80, actualizar_datos)

    # --------------------------------------------------------
    # INICIAR
    # --------------------------------------------------------

    def iniciar():
        nonlocal cuenta_regresiva_activa, cuenta_regresiva_restante
        nonlocal alarma_activada, alarma_audio_completada

        if cuenta_regresiva_activa or reloj.estado in ("En curso", "Pausada", "Finalizada"):
            return

        reloj.reiniciar()
        guardar_reloj(id_batalla, "Preparando", reloj.obtener_tiempo_base(), None)
        alarma_activada = False
        alarma_audio_completada = False
        dashboard_bridge.set_time(0, running=False)
        cuenta_regresiva_activa = True
        cuenta_regresiva_restante = 2
        dashboard_bridge.set_state({
            "battle_id": id_batalla,
            "phase": "ready", "status": "PREPARADOS PARA LA BATALLA",
            "elapsed_seconds": 0, "countdown_active": True, "countdown_value": "3"
        })
        dashboard_bridge.trigger("countdown_start")
        estado_label.config(text="PREPÁRATE...")
        tiempo_principal_label.config(text="3")
        tiempo_centesimas_label.config(text="")
        boton_iniciar.config(state="disabled")
        boton_pausar.config(state="disabled")
        boton_continuar.config(state="disabled")
        boton_finalizar.config(state="disabled")

        def avanzar_cuenta():
            nonlocal cuenta_regresiva_activa, cuenta_regresiva_restante
            if not cuenta_regresiva_activa:
                return
            if obtener_estado_batalla(id_batalla) != "Preparando":
                cuenta_regresiva_activa = False
                return
            if cuenta_regresiva_restante > 0:
                valor = cuenta_regresiva_restante
                if interfaz_batallas_disponible():
                    tiempo_principal_label.config(text=str(valor))
                    tiempo_centesimas_label.config(text="")
                    estado_label.config(text="PREPÁRATE...")
                dashboard_bridge.set_state({"countdown_value": str(valor)})
                cuenta_regresiva_restante -= 1
                ventana_raiz.after(1000, avanzar_cuenta)
                return

            # La cuenta y el inicio dependen de la ventana principal, no de la pestaña.
            if interfaz_batallas_disponible():
                tiempo_principal_label.config(text="¡YA!")
                tiempo_centesimas_label.config(text="")
                estado_label.config(text="¡YA!")
            dashboard_bridge.set_state({"countdown_value": "¡YA!"})
            # Inicia un segundo después de mostrar ¡YA!, sin esperar a que
            # termine el audio de fondo del dashboard.
            ventana_raiz.after(1000, iniciar_batalla_tras_audio)

        def iniciar_batalla_tras_audio():
            nonlocal cuenta_regresiva_activa
            if not cuenta_regresiva_activa:
                return
            if obtener_estado_batalla(id_batalla) != "Preparando":
                cuenta_regresiva_activa = False
                return
            cuenta_regresiva_activa = False
            dashboard_bridge.set_state({
                "countdown_active": False, "phase": "running",
                "status": "BATALLA EN CURSO", "elapsed_seconds": 0
            })
            dashboard_bridge.set_time(0, running=True)
            reloj.iniciar()
            guardar_reloj(
                id_batalla, "En curso",
                reloj.obtener_tiempo_base(), reloj.inicio_epoch()
            )
            if interfaz_batallas_disponible():
                estado_label.config(text="EN CURSO")
                _actualizar_tiempo_visual(
                    tiempo_principal_label, tiempo_centesimas_label, reloj.obtener_tiempo()
                )
                boton_pausar.config(state="normal")
                boton_continuar.config(state="disabled")
                boton_finalizar.config(state="normal")
            dashboard_bridge.trigger("home")

        def completar_audio(action):
            nonlocal alarma_audio_completada
            # El final del audio puede notificarse desde cualquiera de los
            # dashboards conectados. No debe adelantar la cuenta regresiva
            # controlada por Python; el inicio ya está programado con after().
            if action == "countdown_complete":
                return
            elif action == "alarm_complete":
                alarma_audio_completada = True
                # Si el audio termina antes de los 120 s, esperar al límite
                # exacto; si ya llegó, abrir el registro inmediatamente.
                if reloj.estado == "En curso" and reloj.segundos() >= 120:
                    try:
                        ventana_raiz.after(0, lambda: finalizar(automatica=True))
                    except tk.TclError:
                        pass

        # Si la cuenta ya estaba activa en una vista anterior, su callback sigue
        # siendo el propietario del audio y del inicio; no lo reemplazamos.
        if not cuenta_ya_activa:
            dashboard_bridge.set_ui_callback(completar_audio)
            ventana_raiz.after(1000, avanzar_cuenta)

    # --------------------------------------------------------
    # PAUSAR
    # --------------------------------------------------------

    def pausar():

        reloj.pausar()
        guardar_reloj(
            id_batalla, "Pausada", reloj.obtener_tiempo(), None
        )

        dashboard_bridge.set_time(reloj.segundos(), running=False)
        dashboard_bridge.set_state({"phase": "paused", "status": "BATALLA PAUSADA", "elapsed_seconds": reloj.segundos(), "countdown_active": False})
        dashboard_bridge.trigger("home")
        estado_label.config(
            text="PAUSADA"
        )

        boton_pausar.config(
            state="disabled"
        )

        boton_continuar.config(
            state="normal"
        )

    # --------------------------------------------------------
    # CONTINUAR
    # --------------------------------------------------------

    def continuar():
        nonlocal alarma_activada, alarma_audio_completada

        reloj.continuar()
        if reloj.segundos() >= 115:
            alarma_activada = False
            alarma_audio_completada = False
        guardar_reloj(
            id_batalla, "En curso",
            reloj.obtener_tiempo_base(), reloj.inicio_epoch()
        )

        dashboard_bridge.set_time(reloj.segundos(), running=True)
        dashboard_bridge.set_state({"phase": "running", "status": "BATALLA EN CURSO", "elapsed_seconds": reloj.segundos(), "countdown_active": False})
        dashboard_bridge.trigger("home")
        estado_label.config(
            text="EN CURSO"
        )

        boton_pausar.config(
            state="normal"
        )

        boton_continuar.config(
            state="disabled"
        )

    # --------------------------------------------------------
    # FINALIZAR
    # --------------------------------------------------------

    def finalizar(automatica=False):

        nonlocal finalizacion_automatica_activada

        # Evita abrir más de un diálogo de resultado.
        if finalizacion_automatica_activada:
            return
        finalizacion_automatica_activada = True

        tiempo_agotado = reloj.segundos() >= 120
        reloj.finalizar(limite_segundos=120)
        guardar_reloj(
            id_batalla, "En curso", reloj.obtener_tiempo(), None
        )

        boton_iniciar.config(
            state="disabled"
        )

        boton_pausar.config(
            state="disabled"
        )

        boton_continuar.config(
            state="disabled"
        )

        boton_finalizar.config(
            state="disabled"
        )

        tiempo_final = reloj.obtener_tiempo()
        ataques_finales1, ataques_finales2 = dashboard_bridge.attacks()
        dashboard_bridge.set_time(_tiempo_a_segundos(tiempo_final), running=False)
        dashboard_bridge.set_state({"phase": "finished", "status": "BATALLA FINALIZADA", "elapsed_seconds": _tiempo_a_segundos(tiempo_final), "countdown_active": False})
        dashboard_bridge.trigger("home")
        batalla_resultado = list(batalla)
        batalla_resultado[9] = "En curso"
        batalla_resultado[12] = tiempo_final
        batalla_resultado[13] = ataques_finales1
        batalla_resultado[14] = ataques_finales2

        def despues_resultado():
            # Actualizar Batallas en segundo plano inmediatamente; los controles
            # de una nueva batalla permanecen bloqueados hasta que pasen 10 s.
            try:
                mostrar_batallas(
                    contenedor,
                    al_terminar_fase=al_terminar_fase,
                    resultado_recien_guardado=True
                )
            except tk.TclError:
                pass

        abrir_resultado(
            contenedor.winfo_toplevel(),
            tuple(batalla_resultado),
            despues_resultado,
            tiempo_agotado=tiempo_agotado
        )

    # --------------------------------------------------------
    # ASIGNAR BOTONES
    # --------------------------------------------------------

    boton_iniciar.config(
        command=iniciar
    )

    boton_pausar.config(
        command=pausar
    )

    boton_continuar.config(
        command=continuar
    )

    boton_finalizar.config(
        command=finalizar
    )

    # --------------------------------------------------------
    # ESTADO INICIAL
    # --------------------------------------------------------

    if estado == "Preparando":

        boton_iniciar.config(state="disabled")
        boton_pausar.config(state="disabled")
        boton_continuar.config(state="disabled")
        boton_finalizar.config(state="disabled")
        tiempo_principal_label.config(text=estado_puente_previo.get("countdown_value", "3"))
        tiempo_centesimas_label.config(text="")
        estado_label.config(text="PREPÁRATE..." if estado_puente_previo.get("countdown_value", "3") != "¡YA!" else "¡YA!")

        def refrescar_cuenta_recuperada():
            nonlocal cuenta_regresiva_activa, reloj
            if not interfaz_batallas_disponible() or not cuenta_regresiva_activa:
                return

            estado_actual = dashboard_bridge.get_state()
            if not estado_actual.get("countdown_active", False):
                cuenta_regresiva_activa = False

                # La cuenta original pudo terminar mientras esta vista estaba
                # reconstruida. Recuperar el inicio real guardado en la BD para
                # activar también el reloj local de esta nueva instancia.
                if estado_actual.get("phase") == "running":
                    inicio_epoch_actual = obtener_inicio_epoch(id_batalla)
                    reloj = RelojBatalla(
                        tiempo_inicial=obtener_batalla_actual()[12] or "0:00:00",
                        inicio_epoch=inicio_epoch_actual
                    )
                    if reloj.estado != "En curso":
                        reloj.iniciar()
                        guardar_reloj(
                            id_batalla, "En curso",
                            reloj.obtener_tiempo_base(), reloj.inicio_epoch()
                        )

                    estado_label.config(text="EN CURSO")
                    _actualizar_tiempo_visual(
                        tiempo_principal_label,
                        tiempo_centesimas_label,
                        reloj.obtener_tiempo()
                    )
                    boton_iniciar.config(state="disabled")
                    boton_pausar.config(state="normal")
                    boton_continuar.config(state="disabled")
                    boton_finalizar.config(state="normal")
                    actualizar_datos()
                return

            valor = estado_actual.get("countdown_value", "3")
            tiempo_principal_label.config(text=valor)
            tiempo_centesimas_label.config(text="")
            estado_label.config(text="¡YA!" if valor == "¡YA!" else "PREPÁRATE...")
            ventana_raiz.after(100, refrescar_cuenta_recuperada)

        refrescar_cuenta_recuperada()

    elif estado == "Pendiente":

        bloqueo_restante = max(0.0, BLOQUEO_CONTROLES_HASTA - time.monotonic())
        if bloqueo_restante > 0:
            boton_iniciar.config(state="disabled")
            boton_pausar.config(state="disabled")
            boton_continuar.config(state="disabled")
            boton_finalizar.config(state="disabled")

            def desbloquear_controles_siguiente():
                if not interfaz_batallas_disponible():
                    return
                estado_actual = obtener_estado_batalla(id_batalla)
                if estado_actual == "Pendiente":
                    boton_iniciar.config(state="normal")
                    boton_pausar.config(state="disabled")
                    boton_continuar.config(state="disabled")
                    boton_finalizar.config(state="disabled")
                elif estado_actual == "En curso":
                    boton_iniciar.config(state="disabled")
                    boton_pausar.config(state="normal")
                    boton_continuar.config(state="disabled")
                    boton_finalizar.config(state="normal")
                elif estado_actual == "Pausada":
                    boton_iniciar.config(state="disabled")
                    boton_pausar.config(state="disabled")
                    boton_continuar.config(state="normal")
                    boton_finalizar.config(state="normal")
                elif estado_actual == "Preparando":
                    boton_iniciar.config(state="disabled")
                    boton_pausar.config(state="disabled")
                    boton_continuar.config(state="disabled")
                    boton_finalizar.config(state="disabled")

            ventana_raiz.after(max(1, int(bloqueo_restante * 1000)), desbloquear_controles_siguiente)
        else:
            boton_iniciar.config(state="normal")
            boton_pausar.config(state="disabled")
            boton_continuar.config(state="disabled")
            boton_finalizar.config(state="disabled")

    elif estado == "En curso":

        boton_iniciar.config(
            state="disabled"
        )

        boton_pausar.config(
            state="normal"
        )

        boton_continuar.config(
            state="disabled"
        )

        boton_finalizar.config(
            state="normal"
        )

    elif estado == "Pausada":

        boton_iniciar.config(
            state="disabled"
        )

        boton_pausar.config(
            state="disabled"
        )

        boton_continuar.config(
            state="normal"
        )

        boton_finalizar.config(
            state="normal"
        )

    # Se inicia el refresco cuando todos los callbacks ya están definidos.
    actualizar_datos()
