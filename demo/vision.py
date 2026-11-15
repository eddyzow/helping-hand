"""Camera helpers for the drawing feedback loop: find the A4 sheet, flatten the view to millimetres, find ink."""
import cv2
import numpy as np

A4 = (297.0, 210.0)   # as the camera sees it the long side runs across: measured, the first house came out 1.7 times too deep the other way
PX = 5  # pixels per millimetre in the flattened view


def open_camera():
    cam = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920); cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    return cam


def grab(cam, flush=6):
    for _ in range(flush):
        ok, frame = cam.read()
    return frame if ok else None


def find_sheet(frame):
    """The sheet's four corners in the image, or None. All four must be inside the picture."""
    gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (7, 7), 0)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    white = ((gray > 150) & (hsv[..., 1] < 60)).astype(np.uint8) * 255
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    h, w = gray.shape
    best = None
    for c in cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        area = cv2.contourArea(c)
        if area < 0.02 * h * w:
            continue
        hull = cv2.convexHull(c)
        quad = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True).reshape(-1, 2)
        if len(quad) != 4 or cv2.contourArea(quad) < 0.9 * cv2.contourArea(hull):
            continue
        if (quad[:, 0] < 6).any() or (quad[:, 0] > w - 7).any() or (quad[:, 1] < 6).any() or (quad[:, 1] > h - 7).any():
            continue
        if not (hull[:, 0, 1].max() > h * 0.5):   # the sheet lies on the table, in the lower half
            continue
        inside = np.zeros_like(white); cv2.fillConvexPoly(inside, quad.astype(np.int32), 255)
        if (white[inside > 0] > 0).mean() < 0.85:        # a sheet is white all over: a hand or sleeve across it is not one
            continue
        if best is None or area > best[0]:
            best = (area, quad.astype(np.float32))
    return None if best is None else best[1]


def homography(quad):
    """Image -> sheet millimetres. Corner 0 = the image's top-left corner of the sheet (far edge, left)."""
    q = quad[np.argsort(quad[:, 1])]
    top, bottom = q[:2][np.argsort(q[:2, 0])], q[2:][np.argsort(q[2:, 0])]
    src = np.array([top[0], top[1], bottom[1], bottom[0]], np.float32)
    dst = np.array([[0, 0], [A4[0], 0], [A4[0], A4[1]], [0, A4[1]]], np.float32)
    return cv2.getPerspectiveTransform(src, dst)


def flatten(frame, H):
    scale = np.diag([PX, PX, 1.0])
    return cv2.warpPerspective(frame, scale @ H, (int(A4[0] * PX), int(A4[1] * PX)), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))


def ink_mask(flat, dark=45):
    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    paper = cv2.medianBlur(gray, 51)                      # local paper brightness, so a shadow is not ink
    mask = ((paper.astype(np.int16) - gray) > dark).astype(np.uint8)   # dark: how much darker than the paper counts as ink
    m = 12 * PX   # the edges (hands, tape) and the far 45 mm, where the parked pen hangs over the sheet, are not looked at
    mask[:45 * PX] = 0; mask[-m:] = 0; mask[:, :m] = 0; mask[:, -m:] = 0
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))


def points(mask):
    ys, xs = np.nonzero(mask)
    return np.column_stack([xs, ys]).astype(np.float64) / PX
