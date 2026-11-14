"""Pure trend summaries and in-memory HTTP handler; no server, devices or MuJoCo."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import steady
from core.tremor import insights


def test_assets():
    with TemporaryDirectory() as folder, patch.object(steady, "HERE", Path(folder)):
        root = Path(folder)
        (root / "dashboard").mkdir()
        (root / "dashboard" / "app.js").write_text("safe asset")
        (root / "outside.js").write_text("outside sentinel")
        (root / "dashboard" / "secret.txt").write_text("unsupported sentinel")
        for url, expected in (("/dashboard/app.js?v=1", 200), ("/dashboard/../outside.js", 404),
                              ("/dashboard/secret.txt", 404), ("/dashboard/missing.js", 404)):
            status, body = [], BytesIO()
            request = SimpleNamespace(path=url, wfile=body, send_response=status.append,
                send_error=status.append, send_header=lambda *args: None, end_headers=lambda: None)
            steady.Dashboard.do_GET(request)
            assert status == [expected], (url, status)
            assert body.getvalue() == (b"safe asset" if expected == 200 else b""), url


def test_elapsed_time():
    calm = insights([[i * 2, .1, 0, 0, 0] for i in range(5)])
    shaking = insights([[i * 2, 2, .2, 40, 6] for i in range(5)])
    grip = next(row for row in shaking if row["id"] == "grip")
    wrong = [row for row in (calm[0], grip) if "5 seconds" in row["text"]]
    assert not wrong, wrong


if __name__ == "__main__":
    test_assets()
    print("static asset allowlist and traversal controls pass")
    test_elapsed_time()
    print("trend elapsed-time checks pass")
