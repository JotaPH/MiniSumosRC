import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os


# ============================================================
# BASE DE DATOS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(BASE_DIR).lower() == "interfaz":
    BASE_DIR = os.path.dirname(BASE_DIR)
ruta_bd = os.path.join(BASE_DIR, "BasesDeDatos", "competencia.db")

conexion = sqlite3.connect(ruta_bd)
cursor = conexion.cursor()


def confirmar_y_limpiar_competencia(accion, parent=None):
    """Confirma el reinicio si ya hubo actividad y limpia el calendario antes del cambio."""
    try:
        conexion_local = sqlite3.connect(ruta_bd)
        cursor_local = conexion_local.cursor()
        cursor_local.execute("""
            SELECT COUNT(*) FROM enfrentamientos
            WHERE estado IN ('En curso', 'En Curso', 'Pausada', 'Completado')
        """)
        hay_actividad = cursor_local.fetchone()[0] > 0
        conexion_local.close()
    except sqlite3.OperationalError:
        # La tabla aún no existe: todavía no hay una competencia preparada.
        hay_actividad = False
    except Exception as error:
        messagebox.showerror(
            "No se pudo verificar la competencia",
            f"No se puede comprobar el estado de las batallas. No se realizó ningún cambio.\n\n{error}",
            parent=parent
        )
        return False

    if hay_actividad:
        confirmar = messagebox.askyesno(
            "Reiniciar competencia",
            f"Hay una batalla en curso o completada. Si continúas para {accion}, "
            "se reiniciarán todas las batallas y sus resultados, y se generará "
            "un nuevo calendario con los participantes actuales.\n\n¿Deseas continuar?",
            parent=parent
        )
        if not confirmar:
            return False

    # Se limpian las referencias antiguas antes de modificar participantes.
    try:
        try:
            from .enfrentamientos import limpiar_competencia_anterior
        except ImportError:
            from enfrentamientos import limpiar_competencia_anterior
        limpiar_competencia_anterior()
    except Exception as error:
        messagebox.showerror(
            "No se pudo reiniciar",
            f"No se pudo limpiar el calendario anterior. No se realizó el cambio.\n\n{error}",
            parent=parent
        )
        return False

    return True


def regenerar_calendario_participantes(parent=None):
    """Genera un calendario nuevo con la lista actual de participantes."""
    try:
        try:
            from .enfrentamientos import preparar_competencia
        except ImportError:
            from enfrentamientos import preparar_competencia
        exito, mensaje = preparar_competencia()
        if not exito:
            messagebox.showwarning(
                "Calendario no generado",
                f"{mensaje}\n\nLos participantes se guardaron, pero no hay un calendario nuevo.",
                parent=parent
            )
    except Exception as error:
        messagebox.showerror(
            "Error al generar calendario",
            f"Los participantes se guardaron, pero no se pudo generar el calendario.\n\n{error}",
            parent=parent
        )


# ============================================================
# CREAR TABLA
# ============================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS participantes (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    robot TEXT NOT NULL,
    peso REAL DEFAULT 0,
    cumple_dimensiones INTEGER DEFAULT 1,
    tipo_rc INTEGER DEFAULT 1,
    interruptor_visible INTEGER DEFAULT 1,
    sin_elementos_fijacion INTEGER DEFAULT 1,
    sensores_tapados INTEGER DEFAULT 1
)
""")

conexion.commit()


# ============================================================
# COMPATIBILIDAD CON BASES DE DATOS ANTIGUAS
# ============================================================

cursor.execute(
    "PRAGMA table_info(participantes)"
)

columnas_existentes = [
    columna[1]
    for columna in cursor.fetchall()
]

nuevas_columnas = {

    "peso":
        "REAL DEFAULT 0",

    "cumple_dimensiones":
        "INTEGER DEFAULT 1",

    "tipo_rc":
        "INTEGER DEFAULT 1",

    "interruptor_visible":
        "INTEGER DEFAULT 1",

    "sin_elementos_fijacion":
        "INTEGER DEFAULT 1",

    "sensores_tapados":
        "INTEGER DEFAULT 1"
}


for columna, tipo in nuevas_columnas.items():

    if columna not in columnas_existentes:

        cursor.execute(
            f"""
            ALTER TABLE participantes
            ADD COLUMN {columna} {tipo}
            """
        )


conexion.commit()


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
GRIS_CLARO = "#E5E7EB"


# ============================================================
# VERIFICAR CUMPLIMIENTO
# ============================================================

def verificar_cumplimiento(
    peso,
    cumple_dimensiones,
    tipo_rc,
    interruptor_visible,
    sin_elementos_fijacion,
    sensores_tapados
):

    try:

        peso = float(peso)

    except (ValueError, TypeError):

        return False


    if peso <= 0:
        return False

    if peso > 500:
        return False

    if not cumple_dimensiones:
        return False

    if not tipo_rc:
        return False

    if not interruptor_visible:
        return False

    if not sin_elementos_fijacion:
        return False

    if not sensores_tapados:
        return False

    return True


# ============================================================
# MOSTRAR REGISTRO
# ============================================================

def mostrar_registro(contenedor):

    # ========================================================
    # ESTILOS
    # ========================================================

    estilo = ttk.Style()

    estilo.configure(
        "Checklist.TCheckbutton",
        font=("Arial", 12),
        background=FONDO,
        foreground=TEXTO
    )

    estilo.map(
        "Checklist.TCheckbutton",
        background=[
            ("active", FONDO)
        ]
    )


    # --------------------------------------------------------
    # BOTÓN AGREGAR
    # --------------------------------------------------------

    estilo.configure(
        "Agregar.TButton",
        font=("Arial", 10, "bold"),
        foreground=BLANCO,
        background=VERDE,
        padding=(15, 8)
    )

    estilo.map(
        "Agregar.TButton",
        background=[
            ("active", VERDE_OSCURO),
            ("pressed", VERDE_OSCURO)
        ]
    )


    # --------------------------------------------------------
    # BOTÓN ELIMINAR
    # --------------------------------------------------------

    estilo.configure(
        "Eliminar.TButton",
        font=("Arial", 10, "bold"),
        foreground=BLANCO,
        background=ROJO,
        padding=(15, 8)
    )

    estilo.map(
        "Eliminar.TButton",
        background=[
            ("active", ROJO_OSCURO),
            ("pressed", ROJO_OSCURO)
        ]
    )


    # --------------------------------------------------------
    # BOTÓN GUARDAR
    # --------------------------------------------------------

    estilo.configure(
        "Guardar.TButton",
        font=("Arial", 10, "bold"),
        foreground=BLANCO,
        background=VERDE,
        padding=(15, 8)
    )

    estilo.map(
        "Guardar.TButton",
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
        rowheight=38,
        background=BLANCO,
        foreground=TEXTO,
        fieldbackground=BLANCO
    )

    estilo.configure(
        "Treeview.Heading",
        font=("Arial", 15, "bold"),
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


    # ========================================================
    # CONTENIDO
    # ========================================================

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


    # ========================================================
    # TÍTULO
    # ========================================================

    tk.Label(
        contenido,
        text="PARTICIPANTES REGISTRADOS:",
        font=("Arial", 20, "bold"),
        fg="#8E1B1B",
        bg=FONDO
    ).pack(
        anchor="w",
        pady=(0, 15)
    )


    # ========================================================
    # TABLA
    # ========================================================

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
        columns=(
            "ID",
            "Nombre",
            "Robot",
            "Peso",
            "Cumple"
        ),
        show="headings",
        selectmode="browse"
    )


    tabla.tag_configure("cumple", background="#DCFCE7", foreground="#166534")
    tabla.tag_configure("no_cumple", background="#FEE2E2", foreground="#991B1B")

    # ========================================================
    # ENCABEZADOS
    # ========================================================

    tabla.heading(
        "ID",
        text="ID"
    )

    tabla.heading(
        "Nombre",
        text="NOMBRE"
    )

    tabla.heading(
        "Robot",
        text="ROBOT"
    )

    tabla.heading(
        "Peso",
        text="PESO (g)"
    )

    tabla.heading(
        "Cumple",
        text="CUMPLE"
    )


    # ========================================================
    # COLUMNAS
    # ========================================================

    tabla.column(
        "ID",
        width=65,
        minwidth=65,
        anchor="center",
        stretch=False
    )

    tabla.column(
        "Nombre",
        width=260,
        minwidth=150,
        anchor="center",
        stretch=True
    )

    tabla.column(
        "Robot",
        width=260,
        minwidth=150,
        anchor="center",
        stretch=True
    )

    tabla.column(
        "Peso",
        width=110,
        minwidth=100,
        anchor="center",
        stretch=False
    )

    tabla.column(
        "Cumple",
        width=100,
        minwidth=90,
        anchor="center",
        stretch=False
    )


    # ========================================================
    # SCROLLBAR
    # ========================================================

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
        expand=True,
        padx=1,
        pady=1
    )

    scrollbar.pack(
        side="right",
        fill="y"
    )


    # ========================================================
    # CARGAR PARTICIPANTES
    # ========================================================

    def cargar_participantes():

        tabla.delete(
            *tabla.get_children()
        )

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


        for participante in participantes:

            (
                identificacion,
                nombre,
                robot,
                peso,
                cumple_dimensiones,
                tipo_rc,
                interruptor_visible,
                sin_elementos_fijacion,
                sensores_tapados
            ) = participante


            cumple = verificar_cumplimiento(
                peso,
                cumple_dimensiones,
                tipo_rc,
                interruptor_visible,
                sin_elementos_fijacion,
                sensores_tapados
            )


            simbolo = "✓" if cumple else "✗"


            if peso is None:

                peso_mostrar = "-"

            else:

                peso_mostrar = f"{peso:.1f}"


            tabla.insert(
                "",
                "end",
                values=(
                    f"{identificacion:02d}",
                    nombre,
                    robot,
                    peso_mostrar,
                    simbolo
                ),
                tags=("cumple" if cumple else "no_cumple",)
            )


    # ========================================================
    # FORMULARIO AGREGAR / EDITAR
    # ========================================================

    def abrir_formulario(id_participante=None):

        editando = id_participante is not None


        # ====================================================
        # OBTENER DATOS
        # ====================================================

        datos = None


        if editando:

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
                WHERE id = ?
            """, (
                id_participante,
            ))


            datos = cursor.fetchone()


            if datos is None:

                messagebox.showerror(
                    "Error",
                    "No se encontró el participante."
                )

                return


        # ====================================================
        # VENTANA
        # ====================================================

        ventana_formulario = tk.Toplevel(
            contenedor.winfo_toplevel()
        )


        if editando:

            ventana_formulario.title(
                "Editar participante"
            )

        else:

            ventana_formulario.title(
                "Nuevo participante"
            )


        ancho = 600
        alto = 650


        ventana_formulario.geometry(
            f"{ancho}x{alto}"
        )


        ventana_formulario.resizable(
            False,
            False
        )


        ventana_formulario.configure(
            bg=FONDO
        )


        ventana_formulario.transient(
            contenedor.winfo_toplevel()
        )


        # ====================================================
        # CENTRAR
        # ====================================================

        ventana_formulario.update_idletasks()


        pantalla_ancho = (
            ventana_formulario.winfo_screenwidth()
        )

        pantalla_alto = (
            ventana_formulario.winfo_screenheight()
        )


        x = (
            pantalla_ancho - ancho
        ) // 2


        y = 30


        ventana_formulario.geometry(
            f"{ancho}x{alto}+{x}+{y}"
        )


        ventana_formulario.grab_set()


        # ====================================================
        # CABECERA DEL FORMULARIO
        # ====================================================

        tk.Label(
            ventana_formulario,
            text=(
                "EDITAR PARTICIPANTE"
                if editando
                else
                "NUEVO PARTICIPANTE"
            ),
            font=("Arial", 21, "bold"),
            bg=FONDO,
            fg=ROJO_OSCURO
        ).pack(
            pady=(20, 5)
        )


        tk.Label(
            ventana_formulario,
            text="Información de inscripción y verificación",
            font=("Arial", 10),
            bg=FONDO,
            fg=GRIS
        ).pack(
            pady=(0, 15)
        )


        # ====================================================
        # FORMULARIO
        # ====================================================

        formulario = tk.Frame(
            ventana_formulario,
            bg=FONDO
        )

        formulario.pack(
            fill="both",
            expand=True,
            padx=45
        )


        # ====================================================
        # NOMBRE
        # ====================================================

        tk.Label(
            formulario,
            text="Nombre del participante",
            font=("Arial", 11, "bold"),
            bg=FONDO,
            fg=TEXTO
        ).pack(
            anchor="w"
        )


        entrada_nombre = tk.Entry(
            formulario,
            font=("Arial", 13),
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground="#B0B0B0",
            highlightcolor="#1976D2"
        )

        entrada_nombre.pack(
            fill="x",
            pady=(5, 12)
        )


        # ====================================================
        # ROBOT
        # ====================================================

        tk.Label(
            formulario,
            text="Nombre del robot",
            font=("Arial", 11, "bold"),
            bg=FONDO,
            fg=TEXTO
        ).pack(
            anchor="w"
        )


        entrada_robot = tk.Entry(
            formulario,
            font=("Arial", 13),
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground="#B0B0B0",
            highlightcolor="#1976D2"
        )

        entrada_robot.pack(
            fill="x",
            pady=(5, 12)
        )


        # ====================================================
        # PESO
        # ====================================================

        marco_peso = tk.Frame(
            formulario,
            bg=FONDO
        )

        marco_peso.pack(
            fill="x",
            pady=(2, 12)
        )


        tk.Label(
            marco_peso,
            text="Peso (g)",
            font=("Arial", 11, "bold"),
            bg=FONDO,
            fg=TEXTO
        ).pack(
            anchor="w"
        )


        fila_peso = tk.Frame(
            marco_peso,
            bg=FONDO
        )

        fila_peso.pack(
            fill="x",
            pady=(5, 0)
        )


        entrada_peso = tk.Entry(
            fila_peso,
            font=("Arial", 13),
            width=12,
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground="#B0B0B0",
            highlightcolor="#1976D2"
        )

        entrada_peso.pack(
            side="left"
        )


        etiqueta_peso = tk.Label(
            fila_peso,
            text="",
            font=("Arial", 10, "bold"),
            bg=FONDO
        )

        etiqueta_peso.pack(
            side="left",
            padx=12
        )


        # ====================================================
        # VARIABLES
        # ====================================================

        cumple_dimensiones = tk.BooleanVar(
            value=True
        )

        tipo_rc = tk.BooleanVar(
            value=True
        )

        interruptor_visible = tk.BooleanVar(
            value=True
        )

        sin_elementos_fijacion = tk.BooleanVar(
            value=True
        )

        sensores_tapados = tk.BooleanVar(
            value=True
        )


        # ====================================================
        # ACTUALIZAR ESTADO
        # ====================================================

        def actualizar_estado(*args):

            peso_texto = entrada_peso.get().strip()


            if peso_texto == "":

                etiqueta_estado.config(
                    text="⚠ INGRESE EL PESO DEL ROBOT",
                    fg="#E67E22"
                )

                return


            try:

                peso = float(
                    peso_texto
                )

            except ValueError:

                etiqueta_estado.config(
                    text="⚠ PESO NO VÁLIDO",
                    fg=ROJO
                )

                return


            cumple = verificar_cumplimiento(
                peso,
                cumple_dimensiones.get(),
                tipo_rc.get(),
                interruptor_visible.get(),
                sin_elementos_fijacion.get(),
                sensores_tapados.get()
            )


            if cumple:

                etiqueta_estado.config(
                    text="✓ PARTICIPANTE CUMPLE TODOS LOS REQUISITOS",
                    fg=VERDE
                )

            else:

                etiqueta_estado.config(
                    text="✗ PARTICIPANTE NO CUMPLE TODOS LOS REQUISITOS",
                    fg=ROJO
                )


        # ====================================================
        # VALIDAR PESO
        # ====================================================

        def validar_peso(event=None):

            valor = entrada_peso.get().strip()


            if valor == "":

                etiqueta_peso.config(
                    text="Ingrese el peso",
                    fg=GRIS
                )

                entrada_peso.config(
                    highlightbackground="#B0B0B0"
                )

                actualizar_estado()

                return


            try:

                peso = float(
                    valor
                )

            except ValueError:

                etiqueta_peso.config(
                    text="✗ Valor no válido",
                    fg=ROJO
                )

                entrada_peso.config(
                    highlightbackground=ROJO
                )

                actualizar_estado()

                return


            if peso <= 500 and peso > 0:

                etiqueta_peso.config(
                    text="✓ Cumple con el peso",
                    fg=VERDE
                )

                entrada_peso.config(
                    highlightbackground=VERDE
                )

            elif peso > 500:

                etiqueta_peso.config(
                    text="✗ Supera 500 g",
                    fg=ROJO
                )

                entrada_peso.config(
                    highlightbackground=ROJO
                )

            else:

                etiqueta_peso.config(
                    text="✗ Peso inválido",
                    fg=ROJO
                )

                entrada_peso.config(
                    highlightbackground=ROJO
                )


            actualizar_estado()


        # ====================================================
        # REQUISITOS
        # ====================================================

        marco_requisitos = tk.LabelFrame(
            formulario,
            text=" Verificación del reglamento ",
            font=("Arial", 11, "bold"),
            bg=FONDO,
            fg=ROJO_OSCURO,
            padx=15,
            pady=8
        )

        marco_requisitos.pack(
            fill="x",
            pady=(2, 15)
        )


        opciones = [

            (
                "Cumple dimensiones",
                cumple_dimensiones
            ),

            (
                "Tipo RC",
                tipo_rc
            ),

            (
                "Interruptor visible",
                interruptor_visible
            ),

            (
                "Sin elementos que fijen al robot",
                sin_elementos_fijacion
            ),

            (
                "Sensores tapados",
                sensores_tapados
            )
        ]


        for texto, variable in opciones:

            ttk.Checkbutton(
                marco_requisitos,
                text=texto,
                variable=variable,
                style="Checklist.TCheckbutton"
            ).pack(
                anchor="w",
                pady=5
            )


        # ====================================================
        # ESTADO GENERAL
        # ====================================================

        marco_estado = tk.Frame(
            formulario,
            bg="#F5F5F5",
            highlightbackground="#DDDDDD",
            highlightthickness=1
        )

        marco_estado.pack(
            fill="x",
            pady=(0, 15)
        )


        etiqueta_estado = tk.Label(
            marco_estado,
            text="",
            font=("Arial", 13, "bold"),
            bg="#F5F5F5",
            fg=GRIS
        )

        etiqueta_estado.pack(
            pady=10
        )


        # ====================================================
        # EVENTOS
        # ====================================================

        entrada_peso.bind(
            "<KeyRelease>",
            validar_peso
        )


        for _, variable in opciones:

            variable.trace_add(
                "write",
                actualizar_estado
            )


        # ====================================================
        # CARGAR DATOS SI ES EDICIÓN
        # ====================================================

        if editando:

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
            ) = datos


            entrada_nombre.insert(
                0,
                nombre
            )


            entrada_robot.insert(
                0,
                robot
            )


            if peso is not None:

                entrada_peso.insert(
                    0,
                    str(peso)
                )


            cumple_dimensiones.set(
                bool(dimensiones)
            )

            tipo_rc.set(
                bool(rc)
            )

            interruptor_visible.set(
                bool(interruptor)
            )

            sin_elementos_fijacion.set(
                bool(fijacion)
            )

            sensores_tapados.set(
                bool(sensores)
            )


            validar_peso()
            actualizar_estado()


        # ====================================================
        # GUARDAR
        # ====================================================

        def guardar():

            nombre = entrada_nombre.get().strip()
            robot = entrada_robot.get().strip()
            peso_texto = entrada_peso.get().strip()


            if not nombre:

                messagebox.showwarning(
                    "Dato incompleto",
                    "Debes ingresar el nombre del participante.",
                    parent=ventana_formulario
                )

                entrada_nombre.focus()

                return


            if not robot:

                messagebox.showwarning(
                    "Dato incompleto",
                    "Debes ingresar el nombre del robot.",
                    parent=ventana_formulario
                )

                entrada_robot.focus()

                return


            try:

                peso = float(
                    peso_texto
                )

            except ValueError:

                messagebox.showwarning(
                    "Peso inválido",
                    "Debes ingresar un peso válido en gramos.",
                    parent=ventana_formulario
                )

                entrada_peso.focus()

                return


            if peso <= 0:

                messagebox.showwarning(
                    "Peso inválido",
                    "El peso debe ser mayor que 0 g.",
                    parent=ventana_formulario
                )

                entrada_peso.focus()

                return


            # Antes de modificar datos, pedir confirmación si ya hubo batallas
            # y limpiar las referencias del calendario anterior.
            if not confirmar_y_limpiar_competencia(
                "editar el participante" if editando else "agregar el participante",
                parent=ventana_formulario
            ):
                return

            # =================================================
            # EDITAR
            # =================================================

            if editando:

                cursor.execute("""
                    UPDATE participantes
                    SET
                        nombre = ?,
                        robot = ?,
                        peso = ?,
                        cumple_dimensiones = ?,
                        tipo_rc = ?,
                        interruptor_visible = ?,
                        sin_elementos_fijacion = ?,
                        sensores_tapados = ?
                    WHERE id = ?
                """, (
                    nombre,
                    robot,
                    peso,
                    int(cumple_dimensiones.get()),
                    int(tipo_rc.get()),
                    int(interruptor_visible.get()),
                    int(sin_elementos_fijacion.get()),
                    int(sensores_tapados.get()),
                    id_participante
                ))


            # =================================================
            # NUEVO
            # =================================================

            else:

                cursor.execute("""
                    SELECT MAX(id)
                    FROM participantes
                """)

                resultado = cursor.fetchone()[0]


                if resultado is None:

                    numero = 1

                else:

                    numero = resultado + 1


                cursor.execute("""
                    INSERT INTO participantes (
                        id,
                        nombre,
                        robot,
                        peso,
                        cumple_dimensiones,
                        tipo_rc,
                        interruptor_visible,
                        sin_elementos_fijacion,
                        sensores_tapados
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    numero,
                    nombre,
                    robot,
                    peso,
                    int(cumple_dimensiones.get()),
                    int(tipo_rc.get()),
                    int(interruptor_visible.get()),
                    int(sin_elementos_fijacion.get()),
                    int(sensores_tapados.get())
                ))


            conexion.commit()

            regenerar_calendario_participantes(
                parent=contenedor.winfo_toplevel()
            )
            cargar_participantes()
            ventana_formulario.destroy()


        # ====================================================
        # BOTONES DEL FORMULARIO
        # ====================================================

        marco_botones = tk.Frame(
            formulario,
            bg=FONDO
        )

        marco_botones.pack(
            fill="x"
        )


        ttk.Button(
            marco_botones,
            text=(
                "GUARDAR CAMBIOS"
                if editando
                else
                "REGISTRAR PARTICIPANTE"
            ),
            command=guardar,
            style="Guardar.TButton"
        ).pack(
            side="left",
            padx=(0, 5)
        )


        ttk.Button(
            marco_botones,
            text="CANCELAR",
            command=ventana_formulario.destroy,
            style="Eliminar.TButton"
        ).pack(
            side="right"
        )


        entrada_nombre.focus()

        # ENTER = GUARDAR
        ventana_formulario.bind(
            "<Return>",
            lambda event: guardar()
        )


    # ========================================================
    # EDITAR CON DOBLE CLICK
    # ========================================================

    def editar_participante(event=None):

        seleccionado = tabla.selection()


        if not seleccionado:
            return


        elemento = seleccionado[0]


        datos = tabla.item(
            elemento
        )["values"]


        if not datos:
            return


        identificacion = int(
            datos[0]
        )


        abrir_formulario(
            identificacion
        )


    tabla.bind(
        "<Double-1>",
        editar_participante
    )


    # ========================================================
    # AGREGAR
    # ========================================================

    def agregar_participante():

        abrir_formulario()


    # ========================================================
    # ELIMINAR
    # ========================================================

    def eliminar_participante():

        seleccionado = tabla.selection()


        if not seleccionado:

            messagebox.showwarning(
                "Sin selección",
                "Selecciona un participante."
            )

            return


        confirmar = messagebox.askyesno(
            "Eliminar participante",
            "¿Quieres eliminar el participante seleccionado?"
            if len(seleccionado) == 1
            else "¿Quieres eliminar los participantes seleccionados?",
            parent=contenedor.winfo_toplevel()
        )

        if not confirmar:
            return

        if not confirmar_y_limpiar_competencia(
            "eliminar el/los participante(s)",
            parent=contenedor.winfo_toplevel()
        ):
            return

        for elemento in seleccionado:

            datos = tabla.item(
                elemento
            )["values"]


            identificacion = int(
                datos[0]
            )


            cursor.execute("""
                DELETE FROM participantes
                WHERE id = ?
            """, (
                identificacion,
            ))


        conexion.commit()


        # ====================================================
        # REORGANIZAR IDS
        # ====================================================

        cursor.execute("""
            SELECT id
            FROM participantes
            ORDER BY id
        """)

        participantes = cursor.fetchall()


        # Primero IDs negativos
        # para evitar conflictos.

        for numero, participante in enumerate(
            participantes,
            start=1
        ):

            cursor.execute("""
                UPDATE participantes
                SET id = ?
                WHERE id = ?
            """, (
                -numero,
                participante[0]
            ))


        conexion.commit()


        # ====================================================
        # ASIGNAR IDS DEFINITIVOS
        # ====================================================

        cursor.execute("""
            SELECT id
            FROM participantes
            ORDER BY id DESC
        """)

        participantes = cursor.fetchall()


        for numero, participante in enumerate(
            participantes,
            start=1
        ):

            cursor.execute("""
                UPDATE participantes
                SET id = ?
                WHERE id = ?
            """, (
                numero,
                participante[0]
            ))


        conexion.commit()


        regenerar_calendario_participantes(
            parent=contenedor.winfo_toplevel()
        )
        cargar_participantes()

    # ========================================================
    # TECLA SUPR / DELETE PARA ELIMINAR
    # ========================================================

    tabla.bind(
        "<Delete>",
        lambda event: eliminar_participante()
    )

    tabla.bind(
        "<KP_Delete>",
        lambda event: eliminar_participante()
    )


    # ========================================================
    # BOTONES PRINCIPALES
    # ========================================================

    marco_botones = tk.Frame(
        contenido,
        bg=FONDO
    )

    marco_botones.pack(
        fill="x",
        pady=(15, 0)
    )


    ttk.Button(
        marco_botones,
        text="AGREGAR PARTICIPANTE",
        command=agregar_participante,
        style="Agregar.TButton"
    ).pack(
        side="left"
    )


    ttk.Button(
        marco_botones,
        text="ELIMINAR PARTICIPANTE",
        command=eliminar_participante,
        style="Eliminar.TButton"
    ).pack(
        side="right"
    )


    # ========================================================
    # CARGAR DATOS
    # ========================================================

    cargar_participantes()


# ============================================================
# CERRAR BASE DE DATOS
# ============================================================

def cerrar_registro():

    try:

        conexion.close()

    except:

        pass
