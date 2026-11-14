"""Mock subprocess and loopback only: python -m tests.test_dispatcher_exit."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def test_dispatcher_exit():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-B", "-m", "core.dispatcher", "--mock"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "BUDDY_PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"},
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    client = None
    try:
        deadline = time.monotonic() + 10
        while client is None:
            if process.poll() is not None:
                raise AssertionError(process.stdout.read().decode())
            try:
                client = socket.create_connection(("127.0.0.1", port), timeout=.2)
            except OSError:
                assert time.monotonic() < deadline, "mock dispatcher did not start"
                time.sleep(.05)
        client.settimeout(2)
        client.sendall(b"status\n")
        assert b'"ok": true' in client.recv(4096)
        process.stdin.close()
        assert process.wait(timeout=5) == 0, process.stdout.read().decode()
        # Keep the accepted client open through exit and the new bind.
        with socket.socket() as rebound:
            rebound.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            rebound.bind(("127.0.0.1", port))
    finally:
        if client is not None:
            client.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()


if __name__ == "__main__":
    test_dispatcher_exit()
    print("dispatcher exit ok")
