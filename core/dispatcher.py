"""Runs one skill at a time and owns the arm. Contract: newcontext.md section 5.

    python -m core.dispatcher --mock     # no hardware
    python -m core.dispatcher            # real follower: its motors switch on

Type a command, or send it as one line to TCP port 8765 (the keypad and voice scripts do this):
    run <skill> [json params]   |   stop   |   list
Ctrl+C sends the arm home and switches the motors off.
"""
import importlib
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

from core.arm import get_arm

PORT = int(os.environ.get("BUDDY_PORT", "8765"))
SKILLS = {}
_arm = None
_worker = None
_lock = threading.Lock()


def load(arm) -> None:
    global _arm
    _arm = arm
    for path in sorted((Path(__file__).parent.parent / "skills").glob("[!_]*.py")):
        module = importlib.import_module(f"skills.{path.stem}")
        SKILLS[module.NAME] = module


def list_skills() -> list[dict]:
    return [{"name": m.NAME, "description": m.DESCRIPTION, "params": m.PARAMS} for m in SKILLS.values()]


def dispatch(skill_name: str, params: dict | None = None) -> dict:
    """Start a skill in the background. Refuses if one is already running."""
    global _worker
    with _lock:
        if _worker and _worker.is_alive():
            return {"ok": False, "reason": "busy"}
        if skill_name not in SKILLS:
            return {"ok": False, "reason": f"unknown skill '{skill_name}'"}
        _arm.halt.clear()
        _worker = threading.Thread(target=_run, args=(SKILLS[skill_name], params or {}), daemon=True)
        _worker.start()
    return {"ok": True, "reason": "started"}


def _run(skill, params: dict) -> None:
    try:
        result = skill.run(_arm, params, _arm.halt)
    except Exception as err:  # a broken skill must not kill the dispatcher; the arm holds where it is
        result = {"ok": False, "reason": f"{type(err).__name__}: {err}"}
    print(f"[{skill.NAME}] {result}", flush=True)


def stop_all() -> dict:
    _arm.stop()
    return {"ok": True, "reason": "stopped"}


def handle(line: str):
    command, _, rest = line.strip().partition(" ")
    if command == "stop":
        return stop_all()
    if command == "list":
        return list_skills()
    if command == "run":
        name, _, raw = rest.strip().partition(" ")
        try:
            return dispatch(name, json.loads(raw) if raw.strip() else None)
        except ValueError:
            return {"ok": False, "reason": "params must be JSON"}
    return {"ok": False, "reason": "commands: run <skill> [json params] | stop | list"}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            self.wfile.write((json.dumps(handle(line.decode())) + "\n").encode())


def main() -> None:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    # localhost only: this port moves a robot, and WSL mirrored networking would put 0.0.0.0 on the Wi-Fi.
    # Bind before touching the arm: a second dispatcher fails here and never opens the serial port.
    server = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), _Handler)
    load(get_arm(mock="--mock" in sys.argv))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"skills: {', '.join(SKILLS)}. Listening on port {PORT}. Type: run <skill> | stop | list", flush=True)
    try:
        for line in sys.stdin:
            if line.strip():
                print(handle(line), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()
        if _worker:
            _worker.join(2)
        _arm.close()


if __name__ == "__main__":
    main()
