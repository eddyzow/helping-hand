"""Fake database/provider and temporary cache only: python -B -m tests.test_sketch_fallback."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import draw


def test_database_fallback(count):
    stroke = [[(.1, .1), (.9, .9)]]
    calls = []

    def unavailable(prompt, *args, **kwargs):
        calls.append(prompt[:70])
        raise RuntimeError("fake provider unavailable")

    see = SimpleNamespace(load_env=lambda: None, parse_reply=json.loads, ask_claude=unavailable)
    with tempfile.TemporaryDirectory() as temporary, patch.object(draw, "HERE", Path(temporary)), \
            patch.dict(sys.modules, {"see": see}), patch.object(draw, "categories", return_value=["cat"]), \
            patch.object(draw, "doodles", return_value=[stroke] * count), \
            patch.object(draw, "most_typical", side_effect=lambda drawings: drawings), \
            patch.object(draw, "sheet", return_value=b"fake jpeg"), contextlib.redirect_stderr(io.StringIO()):
        try:
            result = draw.sketch("a cat")
        except RuntimeError as error:
            raise AssertionError(f"{count} database candidates available, but fallback called unavailable model: {calls[-1]}") from error
        assert result == stroke
        assert json.loads((Path(temporary) / "drawings/sketch_a_cat.json").read_text()) == [[[.1, .1], [.9, .9]]]


if __name__ == "__main__":
    failed = 0
    for count in (1, 2):
        try:
            test_database_fallback(count)
            print("database fallback", count, "ok")
        except AssertionError as error:
            failed += 1
            print("database fallback FAILED:", error)
    raise SystemExit(bool(failed))
