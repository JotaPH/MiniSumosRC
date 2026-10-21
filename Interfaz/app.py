from flask import Flask, jsonify, request, render_template, send_from_directory, Response, stream_with_context
from threading import Lock, Thread
from queue import Queue, Empty
import json
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
lock = Lock()
event_lock = Lock()
event_subscribers = set()


def publish_event(kind, data):
    message = json.dumps({"type": kind, "data": data}, ensure_ascii=False)
    with event_lock:
        subscribers = list(event_subscribers)
    for subscriber in subscribers:
        try:
            subscriber.put_nowait(message)
        except Exception:
            pass


state = {
    "robot1": "POR DEFINIR", "robot2": "POR DEFINIR",
    "robot1_image": "/Imagenes/No_Batalla.png", "robot2_image": "/Imagenes/No_Batalla.png",
    "battle_number": 0,
    "attacks1": 0, "attacks2": 0,
    "status": "NO HAY BATALLAS PENDIENTES",
    "elapsed_seconds": 0, "started_at": None,
    "winner": "", "winner_person": "", "reason": "", "phase": "no_battles",
    "ui_action": "no_battles", "ui_action_id": 1,
    "battle_id": None, "person1": "", "person2": "",
    "countdown_active": False, "countdown_value": "3",
    "time_source": "dashboard", "python_mode": False
}

def snapshot():
    data = dict(state)
    if data["time_source"] != "python" and data["phase"] == "running" and data["started_at"] is not None:
        data["elapsed_seconds"] = time.time() - data["started_at"]
    return data

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/winner")
def winner_page():
    """Abre directamente la pantalla de ganador; los datos vienen del estado actual."""
    return render_template("index.html")

@app.get("/attacks/<int:robot>")
def attacks_page(robot):
    if robot not in (1, 2):
        return jsonify({"error": "Robot inválido"}), 404
    return render_template("attacks.html", robot=robot)

@app.get("/<path:filename>")
def assets(filename):
    allowed = {"Imagenes/Fondo.jpg", "Imagenes/Fondo_Ganar.jpg", "Imagenes/Fondo_Proxima.jpg", "Imagenes/No_Batalla.png", "Imagenes/R_Amarillo.png", "Imagenes/R_Morado.png", "Imagenes/R_Rojo.png", "Imagenes/R_Verde.png", "Audios/videoplayback.m4a", "Audios/audio_final.m4a"}
    if filename not in allowed:
        return jsonify({"error": "Recurso no encontrado"}), 404
    return send_from_directory(PROJECT_ROOT, filename)

@app.get("/api/stream")
def event_stream():
    subscriber = Queue()
    with event_lock:
        event_subscribers.add(subscriber)

    def generate():
        try:
            with lock:
                initial = snapshot()
            yield "data: " + json.dumps({"type": "state", "data": initial}, ensure_ascii=False) + "\n\n"
            while True:
                try:
                    message = subscriber.get(timeout=15)
                    yield "data: " + message + "\n\n"
                except Empty:
                    yield ": keep-alive\n\n"
        finally:
            with event_lock:
                event_subscribers.discard(subscriber)

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/state")
def get_state():
    with lock:
        return jsonify(snapshot())

@app.get("/api/time")
def get_time():
    with lock:
        data = snapshot()
        return jsonify({
            "elapsed_seconds": data["elapsed_seconds"],
            "phase": data["phase"],
            "time_source": data.get("time_source", "dashboard")
        })


@app.get("/api/events")
def get_events():
    with lock:
        return jsonify({
            "ui_action": state.get("ui_action", ""),
            "ui_action_id": state.get("ui_action_id", 0),
            "countdown_active": state.get("countdown_active", False),
            "countdown_value": state.get("countdown_value", "3"),
            "python_mode": state.get("python_mode", False),
            "phase": state.get("phase", "ready")
        })


@app.post("/api/python/time")
def python_time():
    payload = request.get_json(silent=True) or {}
    try:
        elapsed = max(0.0, min(float(payload.get("elapsed_seconds", 0)), 86400.0))
    except (TypeError, ValueError):
        return jsonify({"error": "Tiempo inválido"}), 400
    with lock:
        state["elapsed_seconds"] = elapsed
        state["started_at"] = None
        state["time_source"] = "python"
        state["python_mode"] = True
        publish_event("time", {"elapsed_seconds": state["elapsed_seconds"], "phase": state["phase"], "time_source": "python"})
        return jsonify({"elapsed_seconds": state["elapsed_seconds"]})


@app.post("/api/python/sync")
def python_sync():
    payload = request.get_json(silent=True) or {}
    allowed = (
        "robot1", "robot2", "robot1_image", "robot2_image",
        "battle_number", "battle_id", "person1", "person2",
        "status", "phase", "winner", "winner_person", "reason",
        "countdown_active", "countdown_value"
    )
    with lock:
        incoming_battle = payload.get("battle_id", state.get("battle_id"))
        if incoming_battle != state.get("battle_id"):
            state["attacks1"] = 0
            state["attacks2"] = 0
        for key in allowed:
            if key not in payload:
                continue
            value = payload[key]
            if key in ("robot1", "robot2", "person1", "person2", "winner", "winner_person", "reason", "status"):
                value = str(value or "")[:100]
            elif key == "phase":
                if value not in ("ready", "running", "paused", "finished"):
                    continue
            elif key == "battle_number":
                try:
                    value = max(0, int(value))
                except (TypeError, ValueError):
                    continue
            elif key == "battle_id":
                try:
                    value = int(value) if value is not None else None
                except (TypeError, ValueError):
                    continue
            elif key in ("robot1_image", "robot2_image"):
                value = str(value or "")
                if value not in ("/Imagenes/R_Amarillo.png", "/Imagenes/R_Morado.png",
                                 "/Imagenes/R_Rojo.png", "/Imagenes/R_Verde.png"):
                    continue
            elif key == "countdown_active":
                value = bool(value)
            elif key == "countdown_value":
                value = str(value or "3")[:8]
            state[key] = value

        state["time_source"] = "python"
        state["python_mode"] = True
        state["started_at"] = None
        if "elapsed_seconds" in payload:
            try:
                state["elapsed_seconds"] = max(0.0, min(float(payload["elapsed_seconds"]), 86400.0))
            except (TypeError, ValueError):
                pass

        # Los ataques los gestiona este servidor. Python solo entrega los valores
        # finales al mostrar al ganador, no sobrescribe el contador durante la pelea.
        action = str(payload.get("ui_action", ""))
        try:
            action_id = int(payload.get("ui_action_id", 0))
        except (TypeError, ValueError):
            action_id = 0
        if action_id > int(state.get("ui_action_id", 0)):
            state["ui_action"] = action[:40]
            state["ui_action_id"] = action_id
            if action == "winner":
                for key in ("attacks1", "attacks2"):
                    if key in payload:
                        try:
                            state[key] = max(0, int(payload[key]))
                        except (TypeError, ValueError):
                            pass
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)


@app.post("/api/ui-complete")
def ui_audio_complete():
    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action", ""))
    if action not in ("countdown_complete", "alarm_complete"):
        return jsonify({"error": "Evento de audio inválido"}), 400
    publish_event("command", {"action": action})
    return jsonify({"ok": True, "action": action})


@app.post("/api/attack/<int:robot>")
def add_attack(robot):
    if robot not in (1, 2):
        return jsonify({"error": "Robot inválido"}), 400
    with lock:
        if state["phase"] != "running":
            return jsonify({"error": "Solo se pueden registrar ataques durante una batalla en curso"}), 409
        key = "attacks1" if robot == 1 else "attacks2"
        state[key] += 1
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

@app.post("/api/attack/<int:robot>/decrement")
def remove_attack(robot):
    if robot not in (1, 2):
        return jsonify({"error": "Robot inválido"}), 400
    with lock:
        if state["phase"] != "running":
            return jsonify({"error": "Solo se pueden corregir ataques durante una batalla en curso"}), 409
        key = "attacks1" if robot == 1 else "attacks2"
        state[key] = max(0, state[key] - 1)
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

@app.post("/api/config")
def configure():
    payload = request.get_json(silent=True) or {}
    with lock:
        for key in ("robot1", "robot2"):
            if key in payload:
                name = str(payload[key]).strip()[:40]
                if name:
                    state[key] = name
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

@app.post("/api/start")
def start_battle():
    with lock:
        state.update({
            "attacks1": 0, "attacks2": 0, "winner": "", "reason": "",
            "elapsed_seconds": 0, "started_at": time.time(), "time_source": "dashboard", "python_mode": False,
            "status": "BATALLA EN CURSO", "phase": "running"
        })
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

@app.post("/api/pause")
def pause_battle():
    with lock:
        if state["phase"] == "running" and state["started_at"] is not None:
            state["elapsed_seconds"] += time.time() - state["started_at"]
        state["started_at"] = None
        state["phase"] = "paused"
        state["status"] = "BATALLA PAUSADA"
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

@app.post("/api/finish")
def finish_battle():
    payload = request.get_json(silent=True) or {}
    with lock:
        if state["phase"] == "running" and state["started_at"] is not None:
            state["elapsed_seconds"] = int(time.time() - state["started_at"])
        state["started_at"] = None
        state["phase"] = "finished"
        state["status"] = "BATALLA FINALIZADA"
        state["winner"] = str(payload.get("winner", "")).strip()[:40]
        state["reason"] = str(payload.get("reason", "")).strip()[:80]
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

@app.post("/api/next")
def next_battle():
    payload = request.get_json(silent=True) or {}
    with lock:
        next_number = state["battle_number"] + 1
        pairs = [
            ("/Imagenes/R_Amarillo.png", "/Imagenes/R_Morado.png", "AMARILLO", "MORADO"),
            ("/Imagenes/R_Rojo.png", "/Imagenes/R_Verde.png", "ROJO", "VERDE")
        ]
        pair = pairs[(next_number - 1) % 2]
        state.update({
            "robot1": str(payload.get("robot1", pair[2])).strip()[:40] or pair[2],
            "robot2": str(payload.get("robot2", pair[3])).strip()[:40] or pair[3],
            "robot1_image": pair[0], "robot2_image": pair[1],
            "battle_number": next_number,
            "attacks1": 0, "attacks2": 0, "elapsed_seconds": 0,
            "started_at": None, "winner": "", "winner_person": "", "reason": "",
            "status": "PREPARADOS PARA LA BATALLA", "phase": "ready", "time_source": "dashboard", "python_mode": False,
            "battle_id": None, "person1": "", "person2": "", "countdown_active": False, "countdown_value": "3"
        })
        current = snapshot()
        publish_event("state", current)
        return jsonify(current)

def terminal_command_loop():
    print("\nComandos: r.NOMBRE | rr.NOMBRE | t.MIN.SEG.CENTESIMAS | mot.MOTIVO | ini | pau | con | fin | g.1 | g.2 | p.NOMBRE1.NOMBRE2 | pn | home | salir")
    while True:
        try:
            raw = input("MiniSumos > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue
        command = raw.lower()
        if command in ("salir", "exit", "quit"):
            print("Consola de comandos cerrada; el dashboard sigue activo.")
            break
        try:
            with lock:
                if command.startswith("rr.") and raw[3:].strip():
                    state["robot2"] = raw[3:].strip()[:40]
                elif command.startswith("r.") and raw[2:].strip():
                    state["robot1"] = raw[2:].strip()[:40]
                elif command.startswith("t."):
                    parts = raw.split(".")
                    if len(parts) != 4 or not all(p.isdigit() for p in parts[1:]):
                        raise ValueError("Formato: t.MINUTOS.SEGUNDOS.CENTESIMAS (ej. t.1.23.45)")
                    minutes, seconds, centiseconds = map(int, parts[1:])
                    if seconds > 59 or centiseconds > 99:
                        raise ValueError("Segundos: 0-59; centésimas: 0-99.")
                    elapsed = minutes * 60 + seconds + centiseconds / 100
                    state["elapsed_seconds"] = elapsed
                    if state["phase"] == "running":
                        state["started_at"] = time.time() - elapsed
                elif command.startswith("mot.") and raw[4:].strip():
                    state["reason"] = raw[4:].strip().replace("_", " ")[:80]
                elif command == "home":
                    state.update({"ui_action": "home", "ui_action_id": state["ui_action_id"] + 1})
                elif command == "ini":
                    state.update({"attacks1": 0, "attacks2": 0, "winner": "",
                                  "started_at": time.time() - state["elapsed_seconds"],
                                  "status": "BATALLA EN CURSO", "phase": "running"})
                elif command == "pau":
                    if state["phase"] == "running" and state["started_at"] is not None:
                        state["elapsed_seconds"] += time.time() - state["started_at"]
                    state.update({"started_at": None, "status": "BATALLA PAUSADA", "phase": "paused"})
                elif command == "con":
                    state.update({"started_at": time.time() - state["elapsed_seconds"],
                                  "status": "BATALLA EN CURSO", "phase": "running"})
                elif command == "fin":
                    if state["phase"] == "running" and state["started_at"] is not None:
                        state["elapsed_seconds"] += time.time() - state["started_at"]
                    state.update({"started_at": None, "status": "BATALLA FINALIZADA", "phase": "finished"})
                elif command in ("g.1", "g.2"):
                    if state["phase"] == "running" and state["started_at"] is not None:
                        state["elapsed_seconds"] += time.time() - state["started_at"]
                    state.update({"started_at": None, "phase": "finished", "status": "BATALLA FINALIZADA",
                                  "winner": state["robot1"] if command == "g.1" else state["robot2"],
                                  "reason": state["reason"] or "DECISIÓN ARBITRAL", "ui_action": "winner",
                                  "ui_action_id": state["ui_action_id"] + 1})
                elif command.startswith("p."):
                    parts = raw.split(".")
                    if len(parts) < 3 or not parts[1].strip() or not ".".join(parts[2:]).strip():
                        raise ValueError("Formato: p.NOMBRE1.NOMBRE2")
                    state.update({"robot1": parts[1].strip()[:40],
                                  "robot2": ".".join(parts[2:]).strip()[:40],
                                  "ui_action": "next", "ui_action_id": state["ui_action_id"] + 1})
                elif command == "pn":
                    state.update({"ui_action": "no_battles", "ui_action_id": state["ui_action_id"] + 1})
                else:
                    raise ValueError("Comando no reconocido.")
            publish_event("state", snapshot())
            print("Comando aplicado:", raw)
        except ValueError as exc:
            print("Error:", exc)

if __name__ == "__main__":
    Thread(target=terminal_command_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
