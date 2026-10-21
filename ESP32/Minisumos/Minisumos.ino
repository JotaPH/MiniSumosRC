/*
  codigo.ino - Firmware inicial de comunicación para MiniSumos RC
  Placa: ESP32-WROOM-32
  Puerto serie: 115200 baudios

  Botones:
    - GPIO 18: ataque del Robot 1 (conectar pulsador entre GPIO18 y GND)
    - GPIO 19: ataque del Robot 2 (conectar pulsador entre GPIO19 y GND)

  Los pines usan INPUT_PULLUP. Cada botón se valida con una máquina de estados
  en loop(): debe permanecer estable 70 ms al presionar o soltar para aceptar
  el cambio. Cada ciclo completo de presión cuenta como máximo un ataque.

  Protocolo desde Python:
    INICIAR|<id_batalla>|<robot1>|<robot2>
    PAUSAR
    CONTINUAR
    PAUSA_FIN
    FINALIZAR|<ganador>|<criterio>

  Protocolo hacia Python:
    TIEMPO=m:ss:cc (minutos:segundos:centésimas)
    ATAQUES1=n
    ATAQUES2=n
*/

#include <Arduino.h>

// -------------------- CONFIGURACIÓN --------------------

constexpr uint8_t PIN_BOTON_R1 = 18;
constexpr uint8_t PIN_BOTON_R2 = 19;
constexpr uint32_t ANTIRREBOTE_MS = 70;  // Estabilidad requerida al presionar/soltar
constexpr uint64_t DURACION_MAXIMA_MS = 120000;  // 2 minutos
constexpr uint32_t INTERVALO_ENVIO_MS = 10;  // Actualizar cronómetro cada 10 ms

// -------------------- ESTADO DE LA BATALLA --------------------

enum EstadoBatalla {
  ESPERANDO,
  EN_CURSO,
  PAUSADA,
  CUENTA_REGRESIVA,
  PAUSA_FIN,
  FINALIZADA
};

EstadoBatalla estado = ESPERANDO;

String idBatalla = "";
String robot1 = "";
String robot2 = "";

volatile uint32_t ataques1 = 0;
volatile uint32_t ataques2 = 0;
volatile bool conteoHabilitado = false;

// Máquina de estados independiente para cada botón.
struct BotonAtaque {
  uint8_t pin;
  bool lecturaAnterior;
  bool estadoEstable;
  uint32_t instanteCambio;
};

BotonAtaque botonR1 = {PIN_BOTON_R1, HIGH, HIGH, 0};
BotonAtaque botonR2 = {PIN_BOTON_R2, HIGH, HIGH, 0};

uint64_t tiempoAcumuladoMs = 0;
uint32_t inicioTramoMs = 0;
uint32_t inicioCuentaRegresivaMs = 0;
uint32_t ultimoEnvioMs = 0;

constexpr uint32_t DURACION_CUENTA_REGRESIVA_MS = 4000;  // 3, 2, 1 y 0; un segundo cada uno

// -------------------- MÁQUINAS DE ESTADOS DE LOS BOTONES --------------------

// INPUT_PULLUP: LOW significa presionado.
// Solo se cuenta al confirmar una transición estable a LOW.
// Para volver a contar, primero debe confirmarse una liberación estable.
void actualizarBoton(BotonAtaque &boton, volatile uint32_t &contador) {
  const bool lectura = digitalRead(boton.pin);
  const uint32_t ahora = millis();

  // Cualquier cambio reinicia el temporizador de estabilidad.
  if (lectura != boton.lecturaAnterior) {
    boton.lecturaAnterior = lectura;
    boton.instanteCambio = ahora;
  }

  // Ignorar transiciones hasta que la lectura permanezca estable.
  if (static_cast<uint32_t>(ahora - boton.instanteCambio) >= ANTIRREBOTE_MS) {
    if (lectura != boton.estadoEstable) {
      boton.estadoEstable = lectura;

      // Contar solo la presión confirmada, nunca al soltar.
      if (boton.estadoEstable == LOW && conteoHabilitado) {
        contador++;
      }
    }
  }
}

// -------------------- TIEMPO --------------------

uint64_t obtenerTiempoMs() {
  if (estado == EN_CURSO) {
    return tiempoAcumuladoMs + static_cast<uint32_t>(millis() - inicioTramoMs);
  }
  return tiempoAcumuladoMs;
}

String tiempoComoTexto(uint64_t tiempoMs) {
  const uint64_t totalCentisegundos = tiempoMs / 10ULL;
  const uint64_t minutos = totalCentisegundos / 6000ULL;
  const uint64_t segundos = (totalCentisegundos / 100ULL) % 60ULL;
  const uint64_t centesimas = totalCentisegundos % 100ULL;

  char texto[24];
  snprintf(texto, sizeof(texto), "%llu:%02llu:%02llu",
           static_cast<unsigned long long>(minutos),
           static_cast<unsigned long long>(segundos),
           static_cast<unsigned long long>(centesimas));
  return String(texto);
}

void congelarTiempo() {
  if (estado == EN_CURSO) {
    tiempoAcumuladoMs += static_cast<uint32_t>(millis() - inicioTramoMs);
  }
  conteoHabilitado = false;
}

void reiniciarContadores() {
  noInterrupts();
  ataques1 = 0;
  ataques2 = 0;
  interrupts();
}

// -------------------- ENVÍO DE DATOS --------------------

void enviarDatos() {
  uint32_t copiaAtaques1;
  uint32_t copiaAtaques2;

  noInterrupts();
  copiaAtaques1 = ataques1;
  copiaAtaques2 = ataques2;
  interrupts();

  Serial.print("TIEMPO=");
  if (estado == CUENTA_REGRESIVA) {
    const uint32_t transcurrido = static_cast<uint32_t>(millis() - inicioCuentaRegresivaMs);
    const uint32_t restante = (DURACION_CUENTA_REGRESIVA_MS - 1 - transcurrido) / 1000;
    Serial.println(restante);
  } else {
    Serial.println(tiempoComoTexto(obtenerTiempoMs()));
  }
  Serial.print("ATAQUES1=");
  Serial.println(copiaAtaques1);
  Serial.print("ATAQUES2=");
  Serial.println(copiaAtaques2);
}

void imprimirInicio() {
  Serial.print("Inicio: BATALLA ");
  Serial.print(idBatalla);
  Serial.print(" - ");
  Serial.print(robot1);
  Serial.print(" vs ");
  Serial.println(robot2);
}

// -------------------- COMANDOS SERIE --------------------

void procesarComando(String linea) {
  linea.trim();
  if (linea.length() == 0) return;

  const int separador1 = linea.indexOf('|');
  String comando = separador1 >= 0 ? linea.substring(0, separador1) : linea;
  comando.trim();
  comando.toUpperCase();

  if (comando == "INICIAR") {
    // Formato: INICIAR|id|robot1|robot2
    if (separador1 < 0) {
      Serial.println("ERROR=Faltan id y nombres de robots");
      return;
    }

    const int separador2 = linea.indexOf('|', separador1 + 1);
    const int separador3 = separador2 >= 0 ? linea.indexOf('|', separador2 + 1) : -1;

    if (separador2 < 0 || separador3 < 0) {
      Serial.println("ERROR=Formato INICIAR incorrecto");
      return;
    }

    idBatalla = linea.substring(separador1 + 1, separador2);
    robot1 = linea.substring(separador2 + 1, separador3);
    robot2 = linea.substring(separador3 + 1);
    idBatalla.trim();
    robot1.trim();
    robot2.trim();

    if (robot1.length() == 0 || robot2.length() == 0) {
      Serial.println("ERROR=Los nombres de los robots no pueden estar vacios");
      return;
    }

    congelarTiempo();
    tiempoAcumuladoMs = 0;
    reiniciarContadores();
    // Mostrar 3, 2, 1 y 0 durante un segundo cada uno antes del cronómetro.
    estado = CUENTA_REGRESIVA;
    inicioCuentaRegresivaMs = millis();
    conteoHabilitado = false;
    imprimirInicio();
    enviarDatos();
    ultimoEnvioMs = millis();
    return;
  }

  if (comando == "PAUSAR") {
    if (estado == CUENTA_REGRESIVA) {
      // Si se pausa durante la preparación, cancelar la cuenta atrás y
      // dejar la batalla pausada desde cero.
      tiempoAcumuladoMs = 0;
      conteoHabilitado = false;
      estado = PAUSADA;
      Serial.println("Pausado");
      enviarDatos();
    } else if (estado == EN_CURSO) {
      congelarTiempo();
      estado = PAUSADA;
      Serial.println("Pausado");
      enviarDatos();
    } else {
      Serial.println("AVISO=La batalla no estaba en curso");
    }
    return;
  }

  if (comando == "CONTINUAR") {
    if (estado == PAUSADA) {
      inicioTramoMs = millis();
      estado = EN_CURSO;
      conteoHabilitado = true;
      Serial.println("Reanudado");
      enviarDatos();
    } else {
      Serial.println("AVISO=La batalla no esta pausada");
    }
    return;
  }

  if (comando == "PAUSA_FIN") {
    if (estado == EN_CURSO) {
      congelarTiempo();
    }
    if (estado == EN_CURSO || estado == PAUSADA) {
      estado = PAUSA_FIN;
      conteoHabilitado = false;
      Serial.println("Finalizado - A la espera del ganador");
      enviarDatos();
    } else if (estado == PAUSA_FIN) {
      Serial.println("AVISO=Esperando el registro del ganador");
    } else {
      Serial.println("AVISO=No hay una batalla activa para finalizar");
    }
    return;
  }

  if (comando == "FINALIZAR") {
    // Formato: FINALIZAR|ganador|criterio
    const int separador2 = separador1 >= 0 ? linea.indexOf('|', separador1 + 1) : -1;
    if (estado != PAUSA_FIN) {
      Serial.println("AVISO=Use PAUSA_FIN antes de registrar el resultado");
      return;
    }
    if (separador1 < 0 || separador2 < 0) {
      Serial.println("ERROR=Formato FINALIZAR incorrecto");
      return;
    }

    String ganador = linea.substring(separador1 + 1, separador2);
    String criterio = linea.substring(separador2 + 1);
    ganador.trim();
    criterio.trim();

    estado = FINALIZADA;
    conteoHabilitado = false;

    Serial.print("Ganador: ");
    Serial.println(ganador);
    Serial.print("Tiempo final: ");
    Serial.println(tiempoComoTexto(tiempoAcumuladoMs));
    Serial.print("Criterio: ");
    Serial.println(criterio);
    enviarDatos();
    Serial.println("Batalla cerrada");
    return;
  }

  Serial.print("ERROR=Comando desconocido: ");
  Serial.println(comando);
}

// -------------------- SETUP / LOOP --------------------

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BOTON_R1, INPUT_PULLUP);
  pinMode(PIN_BOTON_R2, INPUT_PULLUP);

  Serial.println("ESP32 lista - MiniSumos RC");
  Serial.println("Boton R1: GPIO18 | Boton R2: GPIO19");
}

void loop() {
  while (Serial.available() > 0) {
    String linea = Serial.readStringUntil('\n');
    procesarComando(linea);
  }

  // Terminar la cuenta atrás e iniciar el cronómetro real en la ESP32.
  if (estado == CUENTA_REGRESIVA &&
      static_cast<uint32_t>(millis() - inicioCuentaRegresivaMs) >= DURACION_CUENTA_REGRESIVA_MS) {
    tiempoAcumuladoMs = 0;
    inicioTramoMs = millis();
    estado = EN_CURSO;
    conteoHabilitado = true;
    enviarDatos();  // El tiempo real comienza en 0:00:00.
    ultimoEnvioMs = millis();
  }

  // Al llegar a 2 minutos, la ESP32 congela el cronómetro y pide a Python
  // abrir el mismo diálogo que se abre al pulsar FINALIZAR.
  if (estado == EN_CURSO && obtenerTiempoMs() >= DURACION_MAXIMA_MS) {
    congelarTiempo();
    tiempoAcumuladoMs = DURACION_MAXIMA_MS;  // Mostrar exactamente 2:00:00
    estado = PAUSA_FIN;
    conteoHabilitado = false;
    Serial.println("EVENTO=TIEMPO_LIMITE");
    Serial.println("Finalizado - A la espera del ganador");
    enviarDatos();
  }

  // Actualizar ambas máquinas de estados en cada iteración.
  actualizarBoton(botonR1, ataques1);
  actualizarBoton(botonR2, ataques2);

  const uint32_t ahora = millis();
  if (estado != ESPERANDO && estado != FINALIZADA &&
      static_cast<uint32_t>(ahora - ultimoEnvioMs) >= INTERVALO_ENVIO_MS) {
    ultimoEnvioMs = ahora;
    enviarDatos();
  }
}