"""Model height conversion with fake vision, drawing and filesystem calls."""
import json
import math
from types import SimpleNamespace

from tests.test_perception_boundaries import functions


def test_height_conversion():
    box = {"x0": 0, "x1": 1, "y0": 0, "y1": 1}
    spot = {"u": .4, "v": .6, "height_mm": 10.}
    pick_height = [19.]
    scope = {"json": json, "CORNERS": SimpleNamespace(read_text=lambda: "[]"),
             "to_uv": lambda *args: (.2, .3), "GRID_ASPECT": 1., "EDGE": .05,
             "cv2": SimpleNamespace(polylines=lambda *args: None, drawMarker=lambda *args: None,
                                    MARKER_CROSS=0, imwrite=lambda *args: True),
             "np": SimpleNamespace(int32=lambda value: value), "jaw_turn": lambda *args: 0.,
             "Path": lambda *args: SimpleNamespace(mkdir=lambda **kwargs: None),
             "see": SimpleNamespace(numbered=lambda *args: None, find_all=lambda *args:
                 ([(0, 0, "roof", box)], "stack roof", [box], True, spot, pick_height[0]))}
    functions("pick.py", {"locate"}, scope)
    scope["LAYER_GAP_MM"] = 40.
    targets, _, place, problem, lift = scope["locate"](None, "stack roof")
    assert targets and problem is None and place == (.4, .6, .25, 0.)
    assert math.isclose(lift, .475)
    pick_height[0] = 41.
    assert scope["locate"](None, "stack roof")[3]
    pick_height[0] = 19.
    failures = []
    for gap in (float("inf"), float("nan"), 0., -1.):
        scope["LAYER_GAP_MM"] = gap
        try:
            targets, _, place, problem, lift = scope["locate"](None, "stack roof")
        except (ValueError, SystemExit):
            continue
        except ZeroDivisionError:
            failures.append((gap, "unhandled zero division"))
            continue
        if targets and not problem:
            failures.append((gap, place, lift))
    assert not failures, ("invalid layer gap was not refused", failures)


if __name__ == "__main__":
    test_height_conversion()
    print("height boundaries ok")
