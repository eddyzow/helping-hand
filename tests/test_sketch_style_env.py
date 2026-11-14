"""Fake .env loader and temporary caches: python -B -m tests.test_sketch_style_env."""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import draw


def test_loaded_style(imported, loaded):
    detailed = [[(.1, .1), (.9, .9)]]
    simple = [[(.2, .2), (.8, .8)]]
    see = SimpleNamespace(load_env=lambda: os.environ.update(DRAW_DETAIL=loaded),
                          ask_claude=lambda *args, **kwargs: (_ for _ in ()).throw(
                              AssertionError("cached request called provider")))
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ), \
            patch.dict(sys.modules, {"see": see}), patch.object(draw, "DETAIL", imported), \
            patch.object(draw, "HERE", Path(temporary)):
        folder = Path(temporary) / "drawings"
        folder.mkdir()
        (folder / "sketch_a_cat.json").write_text(json.dumps(detailed))
        (folder / "simple_a_cat.json").write_text(json.dumps(simple))
        actual = draw.sketch("a cat")
        expected = detailed if loaded == "detailed" else simple
        assert actual == expected, (imported, loaded, actual)


if __name__ == "__main__":
    failed = []
    for imported, loaded in (("detailed", "detailed"), ("simple", "simple"),
                             ("detailed", "simple"), ("simple", "detailed")):
        try:
            test_loaded_style(imported, loaded)
            print("pass", imported, "->", loaded)
        except AssertionError as error:
            failed.append(str(error))
            print("FAIL", error)
    assert not failed, failed
