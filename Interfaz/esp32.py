"""Comunicación serie centralizada con la ESP32 para MiniSumos RC.

Este módulo es responsable de:
- Descubrir puertos serie y conectar/desconectar.
- Enviar comandos de control a la ESP32.
- Leer y analizar telemetría, estados, avisos y resultados.
- Exponer los datos de forma segura para la interfaz Tkinter.

Protocolo de telemetría (ESP32 -> Python):
    TIEMPO=0:25:00 (minutos:segundos:centésimas)
    ATAQUES1=3
    ATAQUES2=2

Comandos (Python -> ESP32):
    INICIAR|<id_batalla>|<robot1>|<robot2>
    PAUSAR
    CONTINUAR
    PAUSA_FIN
    FINALIZAR|<ganador>|<criterio>
"""

import threading
import time
from collections import deque

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


class ComunicacionESP32:
    """Gestiona toda la comunicación serie con la placa ESP32."""

    def __init__(self, baudrate=115200, timeout=0.2):
        self.baudrate = baudrate
        self.timeout = timeout

        self.serial = None
        self.puerto = None
        self.conectado = False

        self._hilo = None
        self._detener = threading.Event()
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()

        self._tiempo = "0:00:00"
        self._ataques1 = 0
        self._ataques2 = 0

        self._estado = "Desconectado"
        self._ultimo_mensaje = ""
        self._ultimo_error = ""
        self._batalla_id = ""
        self._robot1 = ""
        self._robot2 = ""
        self._ganador = ""
        self._criterio = ""
        self._tiempo_final = ""
        self._mensajes = deque(maxlen=100)
        self._evento_pendiente = None

    # -------------------- PUERTOS Y CONEXIÓN --------------------

    def listar_puertos(self):
        """Devuelve los nombres de los puertos serie disponibles."""
        if list_ports is None:
            return []
        try:
            return [puerto.device for puerto in list_ports.comports()]
        except Exception:
            return []

    def conectar(self, puerto="COM4"):
        """Abre el puerto y arranca el hilo lector. Devuelve True si conecta."""
        if serial is None:
            raise RuntimeError(
                "No está instalado pyserial. Instálalo con: pip install pyserial"
            )

        puerto = str(puerto).strip()
        if not puerto or puerto == "No disponible":
            raise ValueError("Selecciona un puerto serie válido.")

        with self._lock:
            actual = self.serial
            if actual is not None:
                try:
                    if actual.is_open and self.puerto == puerto:
                        self.conectado = True
                        return True
                except Exception:
                    pass

        self.desconectar()

        try:
            conexion = serial.Serial(
                port=puerto,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=1
            )
            # Al abrir el puerto, algunas placas ESP32 se reinician.
            time.sleep(1.5)
            try:
                conexion.reset_input_buffer()
            except Exception:
                pass

            with self._lock:
                self.serial = conexion
                self.puerto = puerto
                self.conectado = True
                self._ultimo_error = ""
                self._estado = "Conectado"

            self._detener.clear()
            self._hilo = threading.Thread(
                target=self._leer_serie,
                daemon=True,
                name="LectorESP32"
            )
            self._hilo.start()
            return True
        except Exception:
            with self._lock:
                self.serial = None
                self.puerto = None
                self.conectado = False
                self._estado = "Error de conexión"
            raise

    def desconectar(self):
        """Detiene el lector y cierra el puerto, si está abierto."""
        self._detener.set()
        with self._lock:
            conexion = self.serial
            self.serial = None
            self.conectado = False
            self.puerto = None
            self._estado = "Desconectado"

        if conexion is not None:
            try:
                if conexion.is_open:
                    conexion.close()
            except Exception:
                pass

        hilo = self._hilo
        if hilo is not None and hilo.is_alive() and hilo is not threading.current_thread():
            hilo.join(timeout=0.5)
        self._hilo = None

    # -------------------- LECTURA Y PROCESAMIENTO --------------------

    def _leer_serie(self):
        while not self._detener.is_set():
            with self._lock:
                conexion = self.serial

            if conexion is None:
                break

            try:
                if not conexion.is_open:
                    break
                linea = conexion.readline().decode("utf-8", errors="ignore").strip()
                if linea:
                    self._procesar_linea(linea)
            except Exception as error:
                with self._lock:
                    self._ultimo_error = str(error)
                    self.conectado = False
                    self._estado = "Error de comunicación"
                break

        with self._lock:
            if self.serial is None or not getattr(self.serial, "is_open", False):
                self.conectado = False

    def _procesar_linea(self, linea):
        """Interpreta telemetría y mensajes legibles emitidos por el firmware."""
        linea = str(linea).strip()
        if not linea:
            return

        with self._lock:
            self._ultimo_mensaje = linea
            self._mensajes.append(linea)

            # El firmware actual envía normalmente una variable por línea.
            partes = linea.replace(";", ",").split(",")
            procesada = False

            for parte in partes:
                if "=" not in parte:
                    continue
                clave, valor = parte.split("=", 1)
                clave = clave.strip().upper()
                valor = valor.strip()

                if clave in ("TIEMPO", "TIME"):
                    self._tiempo = valor
                    procesada = True
                elif clave in ("ATAQUES1", "ATAQUE1", "ATTACKS1", "R1"):
                    try:
                        self._ataques1 = int(float(valor))
                        procesada = True
                    except ValueError:
                        pass
                elif clave in ("ATAQUES2", "ATAQUE2", "ATTACKS2", "R2"):
                    try:
                        self._ataques2 = int(float(valor))
                        procesada = True
                    except ValueError:
                        pass
                elif clave == "ERROR":
                    self._ultimo_error = valor
                    self._estado = "Error en ESP32"
                    procesada = True
                elif clave == "AVISO":
                    self._estado = valor
                    procesada = True
                elif clave == "EVENTO":
                    self._evento_pendiente = valor.strip().upper()
                    if self._evento_pendiente == "TIEMPO_LIMITE":
                        self._estado = "Esperando ganador"
                    procesada = True

            if procesada:
                return

            # Mensajes de estado y resultado del firmware.
            normalizada = linea.casefold()
            if normalizada.startswith("esp32 lista"):
                self._estado = "Lista"
            elif normalizada.startswith("inicio: batalla"):
                self._estado = "En curso"
                # Ejemplo: Inicio: BATALLA 12 - ALPHA vs GAMMA
                try:
                    cabecera, robots = linea.split(" - ", 1)
                    self._batalla_id = cabecera.rsplit(" ", 1)[-1].strip()
                    if " vs " in robots.casefold():
                        separador = robots.casefold().index(" vs ")
                        self._robot1 = robots[:separador].strip()
                        self._robot2 = robots[separador + 4:].strip()
                except ValueError:
                    pass
            elif normalizada == "pausado":
                self._estado = "Pausada"
            elif normalizada == "reanudado":
                self._estado = "En curso"
            elif normalizada.startswith("finalizado - a la espera"):
                self._estado = "Esperando ganador"
            elif normalizada.startswith("ganador:"):
                self._ganador = linea.split(":", 1)[1].strip()
                self._estado = "Resultado recibido"
            elif normalizada.startswith("tiempo final:"):
                self._tiempo_final = linea.split(":", 1)[1].strip()
            elif normalizada.startswith("criterio:"):
                self._criterio = linea.split(":", 1)[1].strip()
            elif normalizada == "batalla cerrada":
                self._estado = "Finalizada"

    # -------------------- CONSULTA DE DATOS --------------------

    def obtener_datos(self):
        """Devuelve (tiempo, ataques_robot1, ataques_robot2)."""
        with self._lock:
            return self._tiempo, self._ataques1, self._ataques2

    def obtener_estado(self):
        """Devuelve el último estado interpretado."""
        with self._lock:
            return self._estado

    def obtener_resultado(self):
        """Devuelve un diccionario con el resultado comunicado por la ESP32."""
        with self._lock:
            return {
                "batalla_id": self._batalla_id,
                "robot1": self._robot1,
                "robot2": self._robot2,
                "ganador": self._ganador,
                "criterio": self._criterio,
                "tiempo_final": self._tiempo_final,
                "tiempo": self._tiempo,
                "ataques1": self._ataques1,
                "ataques2": self._ataques2,
            }

    def consumir_evento(self):
        """Devuelve un evento pendiente una sola vez y lo elimina."""
        with self._lock:
            evento = self._evento_pendiente
            self._evento_pendiente = None
            return evento

    def obtener_ultimo_mensaje(self):
        with self._lock:
            return self._ultimo_mensaje

    def obtener_mensajes(self):
        """Copia reciente del historial de mensajes recibidos."""
        with self._lock:
            return list(self._mensajes)

    def obtener_error(self):
        with self._lock:
            return self._ultimo_error

    def reiniciar_datos(self):
        """Limpia telemetría y metadatos antes de iniciar otra batalla."""
        with self._lock:
            self._tiempo = "0:00:00"
            self._ataques1 = 0
            self._ataques2 = 0
            self._batalla_id = ""
            self._robot1 = ""
            self._robot2 = ""
            self._ganador = ""
            self._criterio = ""
            self._tiempo_final = ""
            self._ultimo_error = ""
            self._evento_pendiente = None

    # -------------------- COMANDOS DE BATALLA --------------------

    def iniciar_batalla(self, id_batalla, robot1, robot2):
        """Envía el comando de inicio y prepara los datos locales."""
        def limpiar_campo(valor):
            return str(valor).replace("|", "/").replace("\n", " ").replace("\r", " ").strip()

        id_texto = limpiar_campo(id_batalla)
        robot1_texto = limpiar_campo(robot1)
        robot2_texto = limpiar_campo(robot2)
        if not id_texto or not robot1_texto or not robot2_texto:
            return False

        self.reiniciar_datos()
        return self.enviar(
            f"INICIAR|{id_texto}|{robot1_texto}|{robot2_texto}"
        )

    def pausar_batalla(self):
        return self.enviar("PAUSAR")

    def continuar_batalla(self):
        return self.enviar("CONTINUAR")

    def pausar_para_resultado(self):
        """Congela el combate mientras el juez elige ganador y criterio."""
        return self.enviar("PAUSA_FIN")

    def finalizar_batalla(self, ganador, criterio):
        """Envía el resultado final a la ESP32."""
        def limpiar_campo(valor):
            return str(valor).replace("|", "/").replace("\n", " ").replace("\r", " ").strip()

        ganador_texto = limpiar_campo(ganador)
        criterio_texto = limpiar_campo(criterio)
        if not ganador_texto or not criterio_texto:
            return False
        return self.enviar(f"FINALIZAR|{ganador_texto}|{criterio_texto}")

    # -------------------- ESCRITURA --------------------

    def enviar(self, comando):
        """Envía un comando terminado en salto de línea; False si falla."""
        mensaje = str(comando).strip()
        if not mensaje or "\n" in mensaje or "\r" in mensaje:
            return False

        with self._write_lock:
            with self._lock:
                conexion = self.serial
                conectado = self.conectado

            if not conectado or conexion is None:
                return False

            try:
                if not conexion.is_open:
                    with self._lock:
                        self.conectado = False
                        self._estado = "Desconectado"
                    return False

                conexion.write((mensaje + "\n").encode("utf-8"))
                conexion.flush()
                return True
            except Exception as error:
                with self._lock:
                    self.conectado = False
                    self._ultimo_error = str(error)
                    self._estado = "Error de comunicación"
                return False


esp32 = ComunicacionESP32()
