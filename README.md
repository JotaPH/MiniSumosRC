# MiniSumosRC_HTML

Prototipo de nuevas vistas **integradas sobre el HTML original del dashboard MiniSumos RC**. No es un dashboard independiente: conserva Home, el marcador, las imágenes de robots, el cronómetro, las pantallas de ganador/próxima batalla y las páginas existentes de Ataques 1 y Ataques 2 como base visual.

## Ejecutar el proyecto

Este repositorio incluye ahora un servidor Flask para servir el dashboard, las páginas de ataques y los recursos de `Imagenes/` y `Audios/`.

1. Instala Python 3.10 o superior.
2. En una terminal, dentro de la carpeta del repositorio, ejecuta `python -m pip install -r requirements.txt`.
3. Inicia el servidor con `python app.py`.
4. Abre `http://127.0.0.1:8000`.

Las rutas principales son `/`, `/battles`, `/attacks/1` y `/attacks/2`. No abras `index.html` directamente con doble clic: las rutas `/api/...`, las imágenes y los audios necesitan el servidor activo.

## Archivo principal

- [index.html](./index.html): base del dashboard con las opciones nuevas añadidas al menú de la tuerca ⚙️:
  - **ATAQUES 1** y **ATAQUES 2**: conservan los contadores y ahora incluyen navegación a las demás vistas.
  - **BATALLAS · JUEZ**: nueva vista basada en `batallas.py`, con inicio y cuenta regresiva, pausa, continuar, finalizar con selección de ganador, próxima batalla, marcador, tiempo y controles de pantalla completa y menú.
  - **PARTICIPANTES**: formulario web con piloto, robot, peso máximo de 500 g y cinco requisitos reglamentarios; permite agregar, editar y eliminar participantes.
  - **TABLAS · GANADORES / PERDEDORES**: incluye una prueba provisional de doble eliminación con participantes válidos de SQLite, botones “Gana R1” y “Gana R2”, índices de depuración a tres decimales y contador acumulado de combates.

## Qué es funcional en este preview

La pestaña TABLAS prepara el cuadro con los participantes válidos registrados, permite elegir provisionalmente el ganador de cada combate y muestra en tiempo real Winners, Lossers, ronda, byes, índices y combates acumulados. El estado de la prueba se guarda en SQLite para que la bandera de torneo iniciado pueda bloquear cambios en participantes.

## Alcance y limitaciones

- Los resultados de la prueba de TABLAS se guardan como estado de depuración en SQLite; todavía no se incorporan como resultados oficiales a las tablas de enfrentamientos e historial.
- La prueba de TABLAS ya consulta participantes desde SQLite y activa una bandera persistente de torneo iniciado. Aún no está conectada con el módulo de torneos Python ni con el ESP32.
- El servidor incluido permite probar la interfaz, rutas, recursos y contadores en el navegador. La nueva vista de Batallas controla un estado web de demostración, pero todavía no está conectada al ESP32 ni a la base SQLite de la aplicación principal; el selector de puerto es visual por ahora.
- La lógica de emparejamientos, especialmente con números impares, debe validarse con casos de 2, 3, 5, 6, 7 y 8 robots antes de usarla en competencia.

## Siguiente paso

Después de revisar y corregir el diseño y las reglas, conectar estas pantallas al backend Python existente, reutilizando SQLite para los participantes/resultados y el mecanismo de eventos del dashboard para reflejar cambios en tiempo real. La comunicación serial con el ESP32 debe continuar centralizada en Python.

## Base de datos SQLite

La interfaz web consulta y modifica los participantes mediante la API Flask y usa el esquema existente de `BasesDeDatos/competencia.db`.

- Si las carpetas `MiniSumosRC` y `MiniSumosRC_HTML` están al mismo nivel, la web intenta usar primero `MiniSumosRC/BasesDeDatos/competencia.db`.
- Si no encuentra esa ruta, usa la copia incluida en `MiniSumosRC_HTML/BasesDeDatos/competencia.db`.
- Para definir la ruta exacta, configura la variable de entorno `MINISUMOS_DB_PATH` antes de iniciar `app.py`.
- `GET /api/database-status` informa si la conexión está disponible; `GET /api/participants` consulta los participantes y `GET /api/matches` consulta los enfrentamientos guardados.

Por seguridad, el formulario web bloquea cambios en participantes si encuentra enfrentamientos iniciados o completados. La interfaz de doble eliminación y los controles de batalla todavía requieren conectar sus acciones de resultados a SQLite; no deben considerarse persistentes hasta completar esa integración.
