"""Runs one skill at a time and owns the arm. Contract: newcontext.md section 5.

    python -m core.dispatcher --mock     # no hardware
    python -m core.dispatcher            # real follower: its motors switch on

Type a command, or send it as one line to TCP port 8765 (the keypad and voice scripts do this):
    run <skill> [json params]   |   stop   |   home   |   status   |   cue   |   ready   |   list
To quit: type home, wait for it to finish, then Ctrl+C. Quitting never moves the arm: it stops,
then asks you to hold the arm before the motors switch off.
"""
import importlib
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

from core import cue, key_down, key_events, waiting
from core.arm import get_arm

PORT = int(os.environ.get("BUDDY_PORT", "8765"))
SKILLS = {}
_arm = None
_worker = None
_lock = threading.Lock()
_closing = False  # set by shutdown(): no new skill may start after it
_last = {}        # the last finished skill and its result, for `status`
_job = 0          # counts accepted runs, so a waiting client can tell its own result from a later one


class _Home:  # the operator's own "go home", run like a skill so busy and stop apply to it
    NAME = "home"
    PARAMS = {}

    @staticmethod
    def run(arm, params, stop):
        return {"ok": True, "reason": ""} if arm.home() else {"ok": False, "reason": "stopped"}


def load(arm) -> None:
    global _arm, _closing
    _arm, _closing = arm, False
    for path in sorted((Path(__file__).parent.parent / "skills").glob("[!_]*.py")):
        module = importlib.import_module(f"skills.{path.stem}")
        SKILLS[module.NAME] = module


def list_skills() -> list[dict]:
    return [{"name": m.NAME, "description": m.DESCRIPTION, "params": m.PARAMS} for m in SKILLS.values()]


def dispatch(skill_name: str, params: dict | None = None) -> dict:
    """Start a skill in the background. Refuses if one is already running."""
    global _worker, _job
    skill = _Home if skill_name == "home" else SKILLS.get(skill_name)
    if params is not None and not isinstance(params, dict):
        return {"ok": False, "reason": "params must be a JSON object"}
    with _lock:
        if _closing:
            return {"ok": False, "reason": "shutting down"}
        if _worker and _worker.is_alive():
            return {"ok": False, "reason": "busy"}
        if skill is None:
            return {"ok": False, "reason": f"unknown skill '{skill_name}'"}
        if unknown := sorted(set(params or {}) - set(skill.PARAMS)):
            return {"ok": False, "reason": f"{skill_name} has no option {unknown}; it takes {sorted(skill.PARAMS)}"}
        _arm.halt.clear()
        _job += 1
        job = _job
        _worker = threading.Thread(target=_run, args=(skill, params or {}, job), daemon=True)
        _worker.start()
    return {"ok": True, "reason": "started", "job": job}


def _run(skill, params: dict, job: int) -> None:
    try:
        result = skill.run(_arm, params, _arm.halt)
    except Exception as err:  # a broken skill must not kill the dispatcher; the arm holds where it is
        result = {"ok": False, "reason": f"{type(err).__name__}: {err}"}
    global _last
    _last = {"job": job, "skill": skill.NAME, **result}
    print(f"[{skill.NAME}] {result}", flush=True)


def stop_all() -> dict:
    _arm.stop()
    return {"ok": True, "reason": "stopped"}


def shutdown(confirm=input, server=None) -> None:
    """Refuse new commands, stop, wait for the skill to end, then switch the motors off once the
    operator confirms the arm is held. Never commands a move. Without a confirmation the motors
    stay on and holding: an arm that holds is safer than an arm that drops."""
    global _closing
    with _lock:
        _closing = True
    stop_all()
    if server:
        server.shutdown()
        server.server_close()  # free the port for the next dispatcher
    if _worker:
        _worker.join()  # moves check the stop flag every 1/30 s, so this is quick
    if _arm.REAL:
        try:
            confirm("Motors switch off next and the arm will drop. Hold it or check it is resting, then press Enter. ")
        except (EOFError, KeyboardInterrupt):
            print("No confirmation, so the motors stay ON and holding. Hold the arm and cut the 12 V power, "
                  "or start the dispatcher again.", flush=True)
            _arm.close(release=False)
            return
    _arm.close()


def handle(line: str):
    command, _, rest = line.strip().partition(" ")
    if command == "stop":
        return stop_all()
    if command == "list":
        return list_skills()
    if command == "status":
        return {"ok": True, "busy": bool(_worker and _worker.is_alive()), "last": _last}
    if command == "temps":  # motor temperatures; only while idle, because it uses the serial bus
        with _lock:
            if _worker and _worker.is_alive():
                return {"ok": False, "reason": "busy"}
            return {"ok": True, "temps": _arm.temperatures()}
    if command == "home":
        return dispatch("home")
    if command == "key":  # the keypad listener reports the jump key: "key down" / "key up"
        (key_down.set if rest.strip() == "down" else key_down.clear)()
        key_events[0] += 1
        return {"ok": True, "reason": ""}
    if command == "cue":
        cue.set()
        return {"ok": True, "reason": "cue"}
    if command == "ready":
        return {"ok": waiting.is_set(), "reason": "a skill is waiting for the cue" if waiting.is_set() else ""}
    if command == "run":
        name, _, raw = rest.strip().partition(" ")
        try:
            return dispatch(name, json.loads(raw) if raw.strip() else None)
        except ValueError:
            return {"ok": False, "reason": "params must be JSON"}
    return {"ok": False, "reason": "commands: run <skill> [json params] | stop | home | list"}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            self.wfile.write((json.dumps(handle(line.decode())) + "\n").encode())


def main() -> None:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    # A client that keeps its connection open (the keypad listener does) must not keep this process
    # alive after shutdown: without this the dispatcher hung on exit and went on holding the port.
    socketserver.ThreadingTCPServer.daemon_threads = True
    # localhost only: this port moves a robot, and WSL mirrored networking would put 0.0.0.0 on the Wi-Fi.
    # Bind before touching the arm: a second dispatcher fails here and never opens the serial port.
    server = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), _Handler)
    load(get_arm(mock="--mock" in sys.argv))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"skills: {', '.join(SKILLS)}. Listening on port {PORT}. Type: run <skill> | stop | home | list",
          flush=True)
    try:
        for line in sys.stdin:
            if line.strip():
                print(handle(line), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown(server=server)


if __name__ == "__main__":
    main()
