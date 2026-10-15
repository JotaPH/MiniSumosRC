import tkinter as tk
from tkinter import messagebox
import sqlite3
import os
from tkinter import ttk
from serial.tools import list_ports

from .esp32 import esp32
from .llaves import actualizar_llaves_tras_resultado


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

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

ruta_bd = os.path.join(
    BASE_DIR,
    "BasesDeDatos",
    "competencia.db"
)


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

        WHERE e.estado IN ('En curso', 'Pausada')

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

    # Al guardar un resultado, comprobar si terminó la fase inicial
    # o si ya se puede crear la siguiente ronda eliminatoria.
    try:
        actualizar_llaves_tras_resultado()
    except Exception as error:
        print(f"Error al actualizar las llaves eliminatorias: {error}")


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
    actualizar
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

    # --------------------------------------------------------
    # OBTENER ÚLTIMOS DATOS ESP32
    # --------------------------------------------------------

    tiempo, ataques1, ataques2 = esp32.obtener_datos()

    # Si ESP32 no tiene datos, usamos los de BD
    if tiempo == "--:--" and tiempo_bd:
        tiempo = tiempo_bd

    if ataques1 == 0 and ataques1_bd:
        ataques1 = ataques1_bd

    if ataques2 == 0 and ataques2_bd:
        ataques2 = ataques2_bd

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

    # --------------------------------------------------------
    # REGISTRAR
    # --------------------------------------------------------

    def registrar():

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

        registrar_resultado(
            id_batalla,
            ganador.get(),
            criterio.get(),
            tiempo,
            ataques1,
            ataques2
        )

        # Reiniciamos los datos para la siguiente batalla
        esp32.reiniciar_datos()

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

def mostrar_batallas(contenedor):

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
        elif total_grupos > 0 and grupos_pendientes == 0 and not hay_llaves:
            tk.Label(
                principal, text="FASE DE GRUPOS FINALIZADA",
                font=("Segoe UI", 18, "bold"), fg="#17202a", bg="#f3f5f7"
            ).pack(pady=(95, 12))
            tk.Label(
                principal, text="Calculando clasificados",
                font=("Segoe UI", 27, "bold"), fg="#922b2b", bg="#f3f5f7"
            ).pack(pady=(0, 12))
            tk.Label(
                principal,
                text="Visita la página de Enfrentamientos para revisar la clasificación\ny generar las llaves eliminatorias.",
                font=("Segoe UI", 15), fg="#475569", bg="#f3f5f7",
                justify="center"
            ).pack()
        elif total_todos > 0 and todos_pendientes == 0 and total_finales_actual == 0:
            tk.Label(
                principal, text="FASE TODOS CONTRA TODOS FINALIZADA",
                font=("Segoe UI", 18, "bold"), fg="#17202a", bg="#f3f5f7"
            ).pack(pady=(95, 12))
            tk.Label(
                principal, text="CLASIFICACIÓN LISTA",
                font=("Segoe UI", 27, "bold"), fg="#922b2b", bg="#f3f5f7"
            ).pack(pady=(0, 12))
            tk.Label(
                principal,
                text="Visita Enfrentamientos para anunciar a los dos primeros\ny generar la batalla final.",
                font=("Segoe UI", 15), fg="#475569", bg="#f3f5f7",
                justify="center"
            ).pack()
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

    # --------------------------------------------------------
    # ENCABEZADO
    # --------------------------------------------------------

    encabezado = RoundedCard(
        principal, fill="#922b2b", outline="#922b2b",
        radius=24, padding=10, height=112
    )
    encabezado.pack(fill="x", padx=18, pady=(8, 0))

    encabezado_interior = encabezado.content
    for columna in range(3):
        encabezado_interior.grid_columnconfigure(columna, weight=1, uniform="encabezado")
    encabezado_interior.grid_rowconfigure(0, weight=1)

    modo_texto = (
        f"Grupos - {grupo}" if etapa == "Grupo" and grupo
        else "Todos vs Todos" if etapa == "Todos"
        else etapa
    )
    tk.Label(
        encabezado_interior, text=modo_texto,
        font=("Segoe UI", 12, "bold"), fg="#fbeaea", bg="#922b2b",
        anchor="w"
    ).grid(row=0, column=0, sticky="w", padx=(18, 6), pady=8)

    tk.Label(
        encabezado_interior, text=f"BATALLA {id_batalla}",
        font=("Segoe UI", 26, "bold"), fg="white", bg="#922b2b",
        anchor="center"
    ).grid(row=0, column=1, sticky="nsew", padx=4, pady=8)

    zona_puerto = tk.Frame(encabezado_interior, bg="#922b2b")
    zona_puerto.grid(row=0, column=2, sticky="e", padx=(6, 18), pady=5)

    def obtener_puertos_disponibles():
        try:
            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

    puertos_disponibles = obtener_puertos_disponibles()
    puerto_var = tk.StringVar(
        value=puertos_disponibles[0] if puertos_disponibles else "No disponible"
    )
    estilo_puertos = ttk.Style()
    estilo_puertos.configure(
        "Puerto.TCombobox",
        fieldbackground="#e5e7eb",
        background="#e5e7eb",
        foreground="#374151",
        selectbackground="#e5e7eb",
        selectforeground="#374151",
        padding=4
    )
    estilo_puertos.map(
        "Puerto.TCombobox",
        fieldbackground=[("readonly", "#e5e7eb"), ("!disabled", "#e5e7eb")],
        background=[("readonly", "#e5e7eb"), ("!disabled", "#e5e7eb")],
        foreground=[("readonly", "#374151"), ("!disabled", "#374151")],
        selectbackground=[("readonly", "#e5e7eb")],
        selectforeground=[("readonly", "#374151")]
    )

    selector_puerto = ttk.Combobox(
        zona_puerto, textvariable=puerto_var,
        values=puertos_disponibles or ["No disponible"],
        width=15, state="readonly", font=("Segoe UI", 11),
        justify="center", style="Puerto.TCombobox"
    )
    selector_puerto.pack(pady=(0, 4))

    estado_conexion = tk.Label(
        zona_puerto, text="● No conectado",
        font=("Segoe UI", 9, "bold"), fg="#d1d5db", bg="#922b2b"
    )
    estado_conexion.pack()

    def conectar_puerto(event=None, mostrar_error=False):
        puerto = puerto_var.get()
        if puerto == "No disponible":
            if getattr(esp32, "conectado", False):
                esp32.desconectar()
            estado_conexion.config(text="● No conectado", fg="#d1d5db")
            return
        try:
            correcto = esp32.conectar(puerto)
            if correcto:
                estado_conexion.config(text=f"● Conectado ({puerto})", fg="#86efac")
            else:
                estado_conexion.config(text="● No conectado", fg="#d1d5db")
        except Exception as error:
            estado_conexion.config(text="● No conectado", fg="#d1d5db")
            if mostrar_error:
                messagebox.showerror(
                    "Conexión ESP32", str(error),
                    parent=contenedor.winfo_toplevel()
                )

    def refrescar_puertos():
        if not principal.winfo_exists():
            return
        encontrados = obtener_puertos_disponibles()
        valores = encontrados or ["No disponible"]
        actual = puerto_var.get()
        selector_puerto.configure(values=valores)

        # Si Windows ya no detecta puertos, desconectar y limpiar el estado.
        if not encontrados:
            puerto_var.set("No disponible")
            if getattr(esp32, "conectado", False):
                esp32.desconectar()
            estado_conexion.config(text="● No conectado", fg="#d1d5db")
        elif actual not in valores:
            puerto_var.set(valores[0])
            if getattr(esp32, "conectado", False):
                esp32.desconectar()
            estado_conexion.config(text="● No conectado", fg="#d1d5db")
            conectar_puerto()
        elif not getattr(esp32, "conectado", False):
            conectar_puerto()

        principal.after(2500, refrescar_puertos)

    selector_puerto.bind(
        "<<ComboboxSelected>>",
        lambda evento: conectar_puerto(evento, True)
    )
    if puertos_disponibles:
        conectar_puerto()
    principal.after(2500, refrescar_puertos)

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

    tk.Label(
        datos, text="◷  TIEMPO",
        font=("Segoe UI", 9, "bold"), fg="#7a858e", bg="white"
    ).grid(row=0, column=1, pady=(12, 0), sticky="ew")
    tiempo_label = tk.Label(
        datos, text="00:00", font=("Segoe UI", 25, "bold"),
        fg="#17202a", bg="white"
    )
    tiempo_label.grid(row=1, column=1, padx=18, pady=(0, 12), sticky="ew")

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
    # ACTUALIZACIÓN ESP32
    # --------------------------------------------------------

    def actualizar_datos():

        if not principal.winfo_exists():
            return

        tiempo, ataques1, ataques2 = esp32.obtener_datos()
        if puerto_var.get() != "No disponible" and getattr(esp32, "conectado", False):
            estado_conexion.config(text=f"● Conectado ({puerto_var.get()})", fg="#86efac")
        else:
            estado_conexion.config(text="● No conectado", fg="#d1d5db")

        tiempo_label.config(
            text=tiempo
        )

        ataques1_label.config(
            text=str(ataques1)
        )

        ataques2_label.config(
            text=str(ataques2)
        )

        principal.after(
            100,
            actualizar_datos
        )

    actualizar_datos()

    # --------------------------------------------------------
    # INICIAR
    # --------------------------------------------------------

    def iniciar():

        actualizar_estado(
            id_batalla,
            "En curso"
        )

        esp32.reiniciar_datos()

        esp32.enviar(
            "INICIAR"
        )

        estado_label.config(
            text="EN CURSO"
        )

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

    # --------------------------------------------------------
    # PAUSAR
    # --------------------------------------------------------

    def pausar():

        actualizar_estado(
            id_batalla,
            "Pausada"
        )

        esp32.enviar(
            "PAUSAR"
        )

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

        actualizar_estado(
            id_batalla,
            "En curso"
        )

        esp32.enviar(
            "CONTINUAR"
        )

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

    def finalizar():

        # SIN CONFIRMACIÓN
        esp32.enviar(
            "FINALIZAR"
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

        abrir_resultado(
            contenedor.winfo_toplevel(),
            batalla,
            lambda: mostrar_batallas(contenedor)
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

    if estado == "Pendiente":

        boton_iniciar.config(
            state="normal"
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
