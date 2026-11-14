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
    job, idle = reply["job"], 0
    while True:  # wait for the result of THIS run, not whatever finished last
        status = ask("status")
        last = status["last"]
        if last.get("job") == job:
            print(last, flush=True)
            return 0 if last.get("ok") else 1
        if last.get("job", 0) > job:
            print(f"run {job} finished, but a later run has replaced its result; check the dispatcher's output")
            return 1
        idle = 0 if status["busy"] else idle + 1
        if idle > 10:  # nothing running for 2 seconds and still no result for this run
            print(f"run {job} is not running and left no result (was the dispatcher restarted?)")
            return 1
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
