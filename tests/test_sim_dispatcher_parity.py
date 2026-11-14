"""Extracted simulator parser with fake drawing functions; no simulation or API."""
import json
from types import SimpleNamespace

from tests.test_perception_boundaries import functions


def test_dispatcher(params, expected):
    scope = {"json": json, "draw": SimpleNamespace(FONTS={"print": "futural"},
        from_text=lambda text: ("text", text),
        from_writing=lambda text, style: ("write", text, style),
        sketch=lambda what: ("sketch", what))}
    functions("sim_draw.py", {"strokes_for"}, scope)
    actual = scope["strokes_for"](("run draw " + json.dumps(params)).split())
    assert actual == expected, (params, actual, expected)


if __name__ == "__main__":
    strokes = [[[.2, .2], [.8, .8]]]
    failures = []
    for params, expected in (({"strokes": strokes}, strokes), ({"text": "HI"}, ("text", "HI"))):
        try:
            test_dispatcher(params, expected)
        except AssertionError as error:
            failures.append(str(error))
            print("FAIL", error)
    assert not failures, failures
