"""Send one command to the running dispatcher and, for a skill, wait for its result.

    python -m core.send "run wave"
    python -m core.send 'run gd_tap {"times": 3}'
    python -m core.send stop

Works from Windows or WSL. Exit code 0 when the reply (or the finished skill) says ok.
"""
import json
import os
import socket
import sys
import time

PORT = int(os.environ.get("BUDDY_PORT", "8765"))


def ask(line: str):
    with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s:
        s.sendall((line + "\n").encode())
        return json.loads(s.makefile().readline())


def main() -> int:
    command = " ".join(sys.argv[1:])
    reply = ask(command)
    print(reply, flush=True)
    if not (command.startswith(("run ", "home")) and isinstance(reply, dict) and reply.get("ok")):
        return 0 if not isinstance(reply, dict) or reply.get("ok", True) else 1
    while (status := ask("status"))["busy"]:
        time.sleep(0.2)
    print(status["last"], flush=True)
    return 0 if status["last"].get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
