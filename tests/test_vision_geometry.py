"""Image geometry contracts with fake outlines, frame and filesystem only."""
import json
import math
from types import SimpleNamespace

from tests.test_perception_boundaries import functions


def test_outline_helpers():
    found = [None]
    scope = {"_outline": lambda *args: found[0]}
    functions("see.py", {"centre_of", "long_axis"}, scope)
    box = {"x0": 0, "x1": 100, "y0": 0, "y1": 60}
    assert scope["centre_of"](None, box) == (50., 30.)
    assert scope["long_axis"](None, box) is None
    found[0] = ((55., 32.), (20., 10.), 30.)
    assert scope["centre_of"](None, box) == (55., 32.)
    assert scope["long_axis"](None, box) == (30., 2.)
    found[0] = ((95., 32.), (10., 20.), 30.)
    assert scope["centre_of"](None, box) == (50., 30.)
    assert scope["long_axis"](None, box) == (120., 2.)


def test_camera_correction():
    frame = SimpleNamespace(shape=(100, 100, 3))
    picked = {"x0": 70, "x1": 90, "y0": 40, "y1": 60}
    base = {"x0": 50, "x1": 70, "y0": 40, "y1": 60}
    place = {"u": .605, "v": .5, "height_mm": 10., "box": base}
    scope = {"json": json, "math": math, "CORNERS": SimpleNamespace(read_text=lambda: "[]"),
             "to_uv": lambda x, y, corners: (x / 100, y / 100), "GRID_ASPECT": 1., "EDGE": .05,
             "CAMERA_HEIGHT_MM": 100., "BRICK_MM": 19., "HELD_DROP_MM": 0., "CENTRED": .03,
             "LAYER_GAP_MM": 40., "ROBOT_UV": (.5, 1.6), "jaw_turn": lambda *args: 0.,
             "cv2": SimpleNamespace(polylines=lambda *args: None, drawMarker=lambda *args: None,
                                    MARKER_CROSS=0, imwrite=lambda *args: True),
             "np": SimpleNamespace(int32=lambda value: value),
             "Path": lambda *args: SimpleNamespace(mkdir=lambda **kwargs: None),
             "see": SimpleNamespace(numbered=lambda *args: None,
                 centre_of=lambda frame, box: (80., 50.) if box is picked else (66., 50.),
                 find_all=lambda *args: ([(80, 50, "roof", picked)], "stack", [picked, base], True, place, 0.))}
    functions("pick.py", {"locate"}, scope)
    targets, _, spot, problem, lift = scope["locate"](frame, "stack")
    assert not problem and lift == 0.
    assert math.isclose(targets[0][0], .7715)
    assert math.isclose(spot[0], .652) and spot[2] == .25
    place["u"] = .7
    assert math.isclose(scope["locate"](frame, "stack")[2][0], .752)
    scope["CAMERA_HEIGHT_MM"] = 0.
    assert scope["locate"](frame, "stack")[0][0][0] == .8


if __name__ == "__main__":
    test_outline_helpers()
    test_camera_correction()
    print("vision geometry ok")
