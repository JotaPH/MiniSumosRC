"""Puente por eventos entre Tkinter y el dashboard web.

El único envío periódico es el reloj (80 ms). El estado se envía cuando cambia
y los contadores de ataques llegan por el flujo SSE del servidor.
"""
import json
import os
import threading
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

DASHBOARD_URL = os.environ.get("MINISUMOS_DASHBOARD_URL", "http://127.0.0.1:8000").rstrip("/")


class DashboardBridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._state = None
        self._elapsed = 0.0
        self._time_anchor = time.monotonic()
        self._time_running = False
        self._event_id = int(time.time() * 1000)
        self._event = {"ui_action": "", "ui_action_id": 0}
        self._event_queue = []
        self._attacks = (0, 0)
        self._attacks_callback = None
        self._ui_callback = None
        self._dirty = False
        self._running = True
        threading.Thread(target=self._worker, name="MiniSumosDashboardBridge", daemon=True).start()
        threading.Thread(target=self._listen_events, name="MiniSumosDashboardEvents", daemon=True).start()

    def set_attacks_callback(self, callback):
        """Registra el refresco visual de ataques, sin temporizador."""
        with self._lock:
            self._attacks_callback = callback
            attacks = self._attacks
        if callback:
            try:
                callback(*attacks)
            except Exception:
                pass

    def set_ui_callback(self, callback):
        """Registra eventos de finalización de audio enviados por el dashboard."""
        with self._lock:
            self._ui_callback = callback

    def get_state(self):
        """Devuelve una copia del último estado, útil al reconstruir una pestaña."""
        with self._lock:
            return dict(self._state) if self._state is not None else {}

    def set_state(self, payload):
        """Marca el estado pendiente solo cuando cambia algún dato."""
        callback = None
        attacks = None
        with self._condition:
            if self._state is None:
                self._state = {}
            changed = any(self._state.get(key) != value for key, value in payload.items())
            if "battle_id" in payload and self._state.get("battle_id") != payload["battle_id"]:
                self._attacks = (0, 0)
                callback = self._attacks_callback
                attacks = self._attacks
            self._state.update(payload)
            if changed:
                self._dirty = True
                self._condition.notify()
        if callback:
            try:
                callback(*attacks)
            except Exception:
                pass

    def set_time(self, elapsed_seconds, running=None):
        """Actualiza el reloj y permite al puente mantenerlo aunque se cierre Batallas."""
        try:
            value = max(0.0, float(elapsed_seconds))
        except (TypeError, ValueError):
            value = 0.0
        now = time.monotonic()
        with self._lock:
            self._elapsed = value
            self._time_anchor = now
            if running is not None:
                self._time_running = bool(running)

    def trigger(self, action, **payload):
        """Encola una acción visual para enviarla inmediatamente."""
        with self._condition:
            self._event_id += 1
            event = {"ui_action": str(action), "ui_action_id": self._event_id, **payload}
            self._event = event
            self._event_queue.append(event)
            self._dirty = True
            self._condition.notify()

    def attacks(self):
        with self._lock:
            return self._attacks

    def _request(self, path, method="GET", payload=None, timeout=0.12):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = Request(DASHBOARD_URL + path, data=data, headers=headers, method=method)
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _worker(self):
        retry_after = 0.0
        last_time = 0.0
        while self._running:
            now = time.monotonic()
            with self._condition:
                state = dict(self._state) if self._state is not None else None
                elapsed = self._elapsed
                if self._time_running:
                    elapsed += max(0.0, now - self._time_anchor)
                event_from_queue = bool(self._event_queue)
                event = dict(self._event_queue.pop(0)) if event_from_queue else dict(self._event)
                dirty = self._dirty
                if dirty:
                    self._dirty = False
                    if self._event_queue:
                        self._dirty = True
                        self._condition.notify()
            if state is not None and now >= retry_after:
                try:
                    # Prioriza los cambios visuales y las acciones de la interfaz
                    # para que no esperen al envío periódico del reloj.
                    if dirty:
                        payload = {**state, **event}
                        event_elapsed = event.get("elapsed_seconds") if event.get("ui_action") == "winner" else None
                        payload.pop("elapsed_seconds", None)
                        if event_elapsed is not None:
                            payload["elapsed_seconds"] = event_elapsed
                        self._request("/api/python/sync", "POST", payload, timeout=0.15)
                    if now - last_time >= 0.08:
                        self._request("/api/python/time", "POST", {"elapsed_seconds": elapsed}, timeout=0.10)
                        last_time = now
                except (URLError, HTTPError, TimeoutError, OSError, ValueError):
                    retry_after = time.monotonic() + 1.0
                    with self._condition:
                        if event_from_queue:
                            self._event_queue.insert(0, event)
                        self._dirty = True
            with self._condition:
                self._condition.wait(timeout=max(0.001, 0.08 - (time.monotonic() - now)))

    def _listen_events(self):
        """Recibe cambios del servidor sin consultar /api/state periódicamente."""
        while self._running:
            try:
                request = Request(DASHBOARD_URL + "/api/stream", headers={"Accept": "text/event-stream"})
                with urlopen(request, timeout=30) as response:
                    for raw_line in response:
                        if not self._running:
                            return
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data:"):
                            continue
                        try:
                            message = json.loads(line[5:].strip())
                            data = message.get("data") or {}
                            if message.get("type") == "state":
                                updated = (
                                    max(0, int(data.get("attacks1", 0))),
                                    max(0, int(data.get("attacks2", 0))),
                                )
                                with self._lock:
                                    changed = updated != self._attacks
                                    self._attacks = updated
                                    callback = self._attacks_callback
                                if changed and callback:
                                    try:
                                        callback(*updated)
                                    except Exception:
                                        pass
                            elif message.get("type") == "command":
                                action = str(data.get("action", ""))
                                with self._lock:
                                    callback = self._ui_callback
                                if callback and action in ("countdown_complete", "alarm_complete"):
                                    try:
                                        callback(action)
                                    except Exception:
                                        pass
                        except (ValueError, TypeError, json.JSONDecodeError):
                            continue
            except (URLError, HTTPError, TimeoutError, OSError):
                time.sleep(1)


dashboard_bridge = DashboardBridge()
