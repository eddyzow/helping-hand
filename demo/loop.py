"""One round of the drawing feedback loop. Run it once per fresh sheet:

    python loop.py house.json

Draws each stroke, folds the arm back and photographs the page after every stroke, flattens the photos to
millimetres (the A4 sheet's four corners), finds each stroke's own ink (what is new since the last photo),
measures it against the intended stroke, and saves a correction for the next round (state.json).
The gate: every stroke drawn, 95 % of the intended line has ink within 2 mm, and the ink's average distance
from the intended line is at most 1 mm. Pictures of every step go to run/roundN/."""
import json, math, os, socketserver, sys, threading, time
import tkinter as tk
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo root
os.environ.update(FOLLOWER_PORT="COM3", ARM_NO_PROMPT="1")
sys.path.insert(0, WT); sys.path.insert(0, HERE)
import arm
import vision
from grid import interpolate

STATE = os.path.join(HERE, os.environ.get("STATE", "state.json"))
SPOT = os.path.join(HERE, "last_spot.json")
PRESS, STEP_S, STEP_MM, LIFT, GAIN = -0.13, 0.0375, 1.5, -0.3, 0.35   # 40 mm/s (was 30)   # 0.7 until round 10: near the target it chased round-to-round noise
GATE_COVER, GATE_MEAN_MM, NEAR_MM = 0.95, 1.0, 2.0
grid = json.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_2x2.json")).read())
strokes = json.loads(open(sys.argv[1]).read())
state = json.loads(open(STATE).read()) if os.path.exists(STATE) else {"round": 0}
state["round"] += 1
OUT = os.path.join(WT, "outputs", "demo", f"round{state['round']}")
os.makedirs(OUT, exist_ok=True)
halt = threading.Event()
# Playtests, 14 Nov (run/playtest_*): firm pressure (-0.13) draws a complete line and light (-0.22) does not touch;
# 50 mm/s draws as complete a line as 25; motor gain 32 makes the pen chatter (kept at 16). A circle comes out as a
# box because each joint has slack to take up when it reverses: pushing the command 3 mm ahead along each axis's
# direction of travel gave the roundest 16 mm circle of eight (radial spread 10 %, against 18 to 28 % with none).
LEAD = [float(v) for v in os.environ.get("LEAD", "3,3").split(",")]    # mm: base turn, reach
FAST = os.environ.get("FAST") == "1"   # demo mode: no photo after each stroke, quicker pen-up travel; draws only, no scoring
PLANE = [1.03, 0.10 / 35, 0.15 / 35]                                  # touch depth = a + b X + c Y, from the last height measurement
if os.path.exists(os.path.join(HERE, "height.json")):
    PLANE = json.loads(open(os.path.join(HERE, "height.json")).read())

PAN = [p["shoulder_pan.pos"] for p in grid["down"]]
RF = 105 / math.sin(math.radians((PAN[1] - PAN[0]) / 2))
RN = 105 / math.sin(math.radians((PAN[3] - PAN[2]) / 2))
R0, PAN0 = (RF + RN) / 2, math.radians(sum(PAN) / 4)
CX, CY = R0 * math.sin(PAN0), R0 * math.cos(PAN0)


def polar(X, Y):
    return math.atan2(CX + X, CY - Y), math.hypot(CX + X, CY - Y)


def leads(c):
    """For each command point of a stroke: how far ahead to push it (turn mm, reach mm), from the way it is moving."""
    pol = [polar(X, Y) for X, Y in c]
    out = []
    for i in range(len(pol)):
        j = min(i, len(pol) - 2)
        turn, reach = (pol[j + 1][0] - pol[j][0]) * pol[j][1], pol[j + 1][1] - pol[j][1]
        out.append((LEAD[0] * math.tanh(turn / 0.3), LEAD[1] * math.tanh(reach / 0.3)))
    return out


def pose(X, Y, lift=None, lower=0.0, lead=(0.0, 0.0)):
    phi, rho = polar(X, Y)
    phi, rho = phi + lead[0] / rho, rho + lead[1]
    v = (RF - rho) / (RF - RN)
    left, right = PAN[0] * (1 - v) + PAN[2] * v, PAN[1] * (1 - v) + PAN[3] * v
    u = (math.degrees(phi) - left) / (right - left)
    assert 0.02 <= u <= 0.98 and 0.02 <= v <= 0.98, (X, Y, u, v)
    depth = lift if lift is not None else PLANE[0] + PLANE[1] * X + PLANE[2] * Y + PRESS + lower
    up, down = interpolate(grid["up"], 2, u, v), interpolate(grid["down"], 2, u, v)
    p = {k: down[k] + depth * (down[k] - up[k]) for k in down}
    assert all(math.isfinite(a) for a in p.values())
    p["gripper.pos"] = max(0.0, down["gripper.pos"] - 8)
    return p


def dense(stroke):
    out, corner = [tuple(stroke[0])], [True]
    for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / STEP_MM))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
        corner += [False] * (n - 1) + [True]
    return np.array(out), corner


ref = [dense(s) for s in strokes]                                   # what the page should show
fix = [np.array(c) for c in state.get("fix", [])]                   # learned offsets, added to the command
if len(fix) != len(ref) or any(len(f) != len(r[0]) for f, r in zip(fix, ref)):
    fix = [np.zeros_like(r[0]) for r in ref]
lower = state.get("lower", [0.0] * len(ref))
if len(lower) != len(ref):
    lower = [0.0] * len(ref)
cmd = [r[0] + f for r, f in zip(ref, fix)]
for c, low in zip(cmd, lower):                                       # every point checked before anything moves
    for (X, Y), ld in zip(c, leads(c)):
        pose(X, Y, lower=low, lead=ld)


class Keys(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            for raw in self.rfile:
                if raw.decode(errors="replace").strip() == "stop":
                    halt.set()
                self.wfile.write(b'{"ok": false, "reason": "drawing"}\n')
        except OSError:
            pass


socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.daemon_threads = True
threading.Thread(target=socketserver.ThreadingTCPServer(("127.0.0.1", 8765), Keys).serve_forever, daemon=True).start()

root = tk.Tk(); root.attributes("-topmost", True); root.geometry("1000x260+100+60"); root.protocol("WM_DELETE_WINDOW", lambda: None)
label = tk.Label(root, font=("Segoe UI", 32, "bold"), fg="white", bg="#a00", wraplength=960); label.pack(fill="both", expand=True)


def show(text, bg="#223"):
    label.config(text=text, bg=bg); root.update()


cam = vision.open_camera()
H = np.array(state["H"]) if "H" in state else None
began = time.time()
while True:                                                           # wait for a clean sheet, fully in view
    frame = vision.grab(cam)
    quad = vision.find_sheet(frame)
    if quad is not None:                                             # from this sheet, every round: the camera or the
        H = vision.homography(quad)                                   # mat can get nudged when a sheet is changed
    marks = 0 if quad is None else int(vision.ink_mask(vision.flatten(frame, H)).sum())
    blank = quad is not None and (marks < 60 or os.environ.get("USED") == "1")   # USED=1: draw on a sheet that already has marks
    if blank and os.path.exists(SPOT) and os.environ.get("OVERDRAW") != "1":   # OVERDRAW=1: draw over an old drawing anyway         # where the pen works, in the camera image, from the last scored drawing
        px = np.array(json.loads(open(SPOT).read()) + [1.0])
        mm = H @ px; mm = mm[:2] / mm[2]
        x0, x1 = [int(max(0, v) * vision.PX) for v in (mm[0] - 32, mm[0] + 32)]
        y0, y1 = [int(max(0, v) * vision.PX) for v in (mm[1] - 48, mm[1] + 48)]
        under = int(vision.ink_mask(vision.flatten(frame, H))[y0:y1, x0:x1].sum())
        if under > 150:
            show(f"ROUND {state['round']}: an old drawing is under the pen. SLIDE the sheet sideways so a clean part is in front of the arm", "#a00")
            time.sleep(0.5)
            continue
    if blank:
        break
    show(f"ROUND {state['round']}: " + ("put a FRESH sheet in the same place" if quad is not None else "the camera must see all 4 corners of the sheet"), "#a00")
    if time.time() - began > 900:
        sys.exit("no clean sheet in view after 15 minutes; nothing moved")
    time.sleep(0.5)
state["H"] = H.tolist()
for left in range(5, 0, -1):
    show(f"ROUND {state['round']}: FOLLOWER ARM DRAWS IN {left}\nhands off the page, pad stop key holds the arm", "#a00"); time.sleep(1)
show(f"ROUND {state['round']}: drawing")

robot = arm.follower()
robot.config.disable_torque_on_disconnect = False
bus = robot.bus
bus.disable_torque("wrist_roll", num_retry=8)   # faulty motor: it reached 63 C on 15 Nov; friction holds the joint
bus.sync_read = (lambda read: lambda *a, **k: read(*a, **{**k, "num_retry": 12}))(bus.sync_read)
if bus.sync_read("Present_Temperature", normalize=False)["gripper"] >= 66:
    robot.disconnect(); sys.exit("the claw motor is 66 C or more: let it cool first; nothing moved")
bus.sync_write("Torque_Limit", {j: 600 for j in ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]}, normalize=False, num_retry=5)
bus.write("Torque_Limit", "gripper", int(os.environ.get("GRIP", "500")), normalize=False, num_retry=8)   # 220 let a tilted pen pivot in the claw: the heart came out half size
roll = arm.read_pose(robot)["wrist_roll.pos"]
AWAY = {k: v for k, v in interpolate(grid["up"], 2, 0.5, 0.97).items() if k != "gripper.pos"}


def move(target, seconds):
    start = arm.read_pose(robot)
    steps = max(1, int(seconds * 30))
    for i in range(1, steps + 1):
        if halt.is_set():
            raise KeyboardInterrupt
        robot.send_action({**{k: start[k] + (target[k] - start[k]) * i / steps for k in target}, "wrist_roll.pos": roll})
        time.sleep(1 / 30)
    root.update()


def away_photo(name):
    move({**arm.read_pose(robot), **AWAY}, 1.6)
    time.sleep(0.5)
    frame = vision.grab(cam)
    cv2.imwrite(os.path.join(OUT, name + ".jpg"), frame)
    quad = vision.find_sheet(frame)            # the sheet is found again in every photo: a hand-held sheet creeps, and
    if quad is not None:                       # with one fixed mapping every old line then showed up shifted, as new ink
        last_H[0] = vision.homography(quad)
    else:
        print(f"photo {name}: sheet corners not found, using the last mapping", flush=True)
    return vision.flatten(frame, last_H[0])


flats, ok, t_draw = [], False, time.time()
last_H = [H]
try:
    flats.append(away_photo("0_blank"))
    for k, (c, (_, corner)) in enumerate(zip(cmd, ref)):
        ld = leads(c)
        move(pose(*c[0], lift=LIFT, lead=ld[0]), 0.6 if FAST else 1.2)
        move(pose(*c[0], lower=lower[k], lead=ld[0]), 0.35 if FAST else 0.5)
        time.sleep(0.3)                                                # the pen lands late: strokes were starting with a gap
        tick = time.perf_counter()
        for (X, Y), is_corner, l in zip(c[1:], corner[1:], ld[1:]):
            if halt.is_set():
                raise KeyboardInterrupt
            p = pose(X, Y, lower=lower[k], lead=l)                   # straight to the motors, no read first: 30 mm/s
            bus.sync_write("Goal_Position", {j[:-4]: (roll if j == "wrist_roll.pos" else p[j]) for j in p})
            time.sleep(max(0.0, STEP_S - (time.perf_counter() - tick)) + (0.1 if is_corner else 0.0)); tick = time.perf_counter()
        time.sleep(0.15)
        move(pose(*c[-1], lift=LIFT, lead=ld[-1]), 0.4)
        if not FAST or k == len(cmd) - 1:
            flats.append(away_photo(f"{k + 1}_after_stroke_{k + 1}"))
    ok = True
except KeyboardInterrupt:
    print("STOPPED: the arm is holding where it was", flush=True)
finally:
    print("temps", bus.sync_read("Present_Temperature", normalize=False), flush=True)
    bus.write("Torque_Limit", "gripper", 150, normalize=False, num_retry=8)
    robot.disconnect()
    cam.release()
if not ok:
    sys.exit(1)

print(f"drawing took {time.time() - t_draw:.0f} s", flush=True)
if FAST:
    sys.exit(0)
# ---- compare with the intended drawing -------------------------------------------------------------------------
masks = [vision.ink_mask(f) for f in flats]
centre, own = [], []                                                              # each stroke's own ink, in sheet millimetres
for k in range(len(ref)):
    new = cv2.subtract(masks[k + 1], cv2.dilate(masks[k], np.ones((5, 5), np.uint8)))
    new = cv2.morphologyEx(new, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    own.append(vision.points(new))
    thin, work, cross = np.zeros_like(new), new.copy(), cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while work.any():                                                 # the line's centre: a marker line is 2 mm wide,
        opened = cv2.morphologyEx(work, cv2.MORPH_OPEN, cross)        # and its width is not a position error
        thin |= work & ~opened
        work = cv2.erode(work, cross)
    centre.append(vision.points(thin))
drawn = [len(p) > 30 for p in own]
print("ink points per stroke", [len(p) for p in own], flush=True)


def rigid(a, b, mirror):
    """Rotation (with or without a mirror) and shift taking points a onto points b, least squares."""
    ca, cb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(vt.T @ u.T)) * (-1 if mirror else 1)
    R = vt.T @ np.diag([1, d]) @ u.T
    return R, cb - R @ ca


def nearest(p, cloud):
    d = np.linalg.norm(cloud[None, :, :] - p[:, None, :], axis=2)
    i = d.argmin(1)
    return cloud[i], d[np.arange(len(p)), i]


if True:   # placed afresh every round: where the drawing sits on the sheet is not judged, only its shape (round 11's
    # house was a good house 5 mm to the left, after the sheet was slid in under the arm, and scored 53 %)
    have = [k for k in range(len(ref)) if drawn[k]]
    if not have:
        sys.exit("no stroke left ink: cannot place the drawing on the page. Pen cap? Pen height?")
    best = None
    starts = [(m, None) for m in (False, True)] if len(have) >= 3 else [(m, a) for m in (False, True) for a in range(0, 360, 15)]
    for mirror, turn in starts:
        if turn is None:
            R, t = rigid(np.array([ref[k][0].mean(0) for k in have]), np.array([own[k].mean(0) for k in have]), mirror)
        else:   # one or two strokes: their middles cannot fix a turn, so every 15 degrees is tried as a start
            c, s_ = math.cos(math.radians(turn)), math.sin(math.radians(turn))
            R = np.array([[c, -s_], [s_, c]]) @ np.diag([1.0, -1.0 if mirror else 1.0])
            t = np.vstack([own[k] for k in have]).mean(0) - np.vstack([ref[k][0] for k in have]).mean(0) @ R.T
        for _ in range(15):                                           # refine on the lines themselves
            a = np.vstack([ref[k][0] for k in have])
            b = np.vstack([nearest(ref[k][0] @ R.T + t, own[k])[0] for k in have])
            R, t = rigid(a, b, mirror)
        err = np.mean([nearest(ref[k][0] @ R.T + t, own[k])[1].mean() for k in have])
        if best is None or err < best[0]:
            best = (err, R, t)
    _, R, t = best
    state["R"], state["t"] = R.tolist(), t.tolist()

cover, ink_err, report, stray = [], [], [], 0
overlay = flats[-1].copy()
for k, (pts, _) in enumerate(ref):
    want = pts @ R.T + t
    cv2.polylines(overlay, [np.round(want * vision.PX).astype(np.int32)], False, (0, 170, 0), 2)
    if not drawn[k]:
        lower[k] += 0.1                                               # no ink: the pen was too high for this stroke
        cover.append(np.zeros(len(pts), bool)); report.append(f"stroke {k + 1}: NO INK, pen lowered 2 mm for next round")
        continue
    if k:                                                             # the sheet can creep between photos, and old ink then
        earlier = np.vstack([ref[j][0] @ R.T + t for j in range(k)])  # shows up as "new": ink lying on an earlier stroke's
        keep = (nearest(own[k], earlier)[1] > 2.5) | (nearest(own[k], want)[1] < 2.5)   # line, and not on this one, is dropped
        own[k] = own[k][keep] if keep.sum() > 30 else own[k]
    hit, dist = nearest(want, own[k])
    cover.append(dist <= NEAR_MM)
    back = nearest(own[k], want)[1]
    # A part of the intended line that no ink is closest to was not drawn at all: the pen was off the paper there.
    owner = np.linalg.norm(want[None, :, :] - own[k][:, None, :], axis=2).argmin(1)
    reached = np.zeros(len(want), bool); reached[owner] = True
    reached = np.convolve(reached, np.ones(5), "same") > 0
    seen = (dist <= 10.0) & reached
    err = np.where(seen[:, None], (hit - want) @ R, 0.0)              # in the drawing's own axes
    if np.linalg.norm(want[0] - want[-1]) > 3:                        # an open stroke (roof, door): ink running on past an end
        for end, inner in ((0, 1), (-1, -2)):                         # has no intended point to be compared with, so nearest-
            out = (want[end] - want[inner]) / np.linalg.norm(want[end] - want[inner])   # point matching never sees it. Measure it.
            close = own[k][np.linalg.norm(own[k] - want[end], axis=1) < 7]
            over = ((close - want[end]) @ out).max() - 1.0 if len(close) else 0.0       # 1 mm = half the line's width
            if over > 0.5:
                rows = slice(0, 3) if end == 0 else slice(-3, None)
                err[rows] += (over * out) @ R
    kernel = np.ones(5) / 5
    err = np.column_stack([np.convolve(np.pad(err[:, a], 2, mode="edge"), kernel, "valid") for a in (0, 1)])
    if cover[-1].mean() >= 0.5:
        fix[k] = fix[k] - GAIN * err
    elif len(own[k]) < 60:
        lower[k] += 0.1                                               # hardly any ink: the pen is too high
    else:
        # Plenty of ink but in the wrong place (round 8: the left window was a good square 9 mm off). Matching point
        # by point is meaningless that far out, so the whole stroke is moved by how far its middle is off.
        fix[k] = fix[k] - ((np.median(own[k], axis=0) - want.mean(0)) @ R)
    for q in np.round(own[k] * vision.PX).astype(np.int32):
        overlay[q[1], q[0]] = (0, 0, 255)
    report.append(f"stroke {k + 1}: covered {100 * cover[-1].mean():.0f} %, line off by mean {dist[seen].mean():.1f} mm, worst {dist[seen].max():.1f} mm, not drawn {100 * (~seen).mean():.0f} %, ink mean {back.mean():.2f} / worst {back.max():.1f} mm from the line")

final = cv2.subtract(masks[-1], cv2.dilate(masks[0], np.ones((5, 5), np.uint8)))   # only what this round drew
thin, cross = np.zeros_like(final), cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
while final.any():                                                    # centre of every line in the finished picture
    thin |= final & ~cv2.morphologyEx(final, cv2.MORPH_OPEN, cross)
    final = cv2.erode(final, cross)
every = np.vstack([p @ R.T + t for p, _ in ref])
back = nearest(vision.points(thin), every)[1]
stray = int((back > 10.0).sum())                                      # that far off is a shadow or a hand, counted apart
ink_err = [back[back <= 10.0]]
covered = float(np.concatenate(cover).mean())
mean_ink = float(np.concatenate(ink_err).mean()) if ink_err else float("nan")
passed = all(drawn) and covered >= GATE_COVER and mean_ink <= GATE_MEAN_MM
both = np.vstack([p @ R.T + t for p, _ in ref])
x0, y0 = np.maximum(0, (both.min(0) - 15) * vision.PX).astype(int)
x1, y1 = ((both.max(0) + 15) * vision.PX).astype(int)
cv2.imwrite(os.path.join(OUT, "compare.jpg"), cv2.resize(overlay[y0:y1, x0:x1], None, fx=1.6, fy=1.6))
cv2.imwrite(os.path.join(OUT, "page.jpg"), flats[-1])
centre_px = np.linalg.inv(last_H[0]) @ np.append(np.mean([p.mean(0) for p, _ in ref], axis=0) @ R.T + t, 1.0)
json.dump((centre_px[:2] / centre_px[2]).tolist(), open(SPOT, "w"))
state.update(fix=[f.tolist() for f in fix], lower=lower)
state.setdefault("history", []).append({"round": state["round"], "covered_pct": round(100 * covered, 1), "ink_mean_mm": round(mean_ink, 2),
                                         "strokes_drawn": int(sum(drawn)), "passed": bool(passed)})
json.dump(state, open(STATE, "w"))
print("\n".join(report))
print(f"ROUND {state['round']}: strokes drawn {sum(drawn)}/{len(ref)}, covered {100 * covered:.1f} % (gate {100 * GATE_COVER:.0f}), "
      f"ink mean {mean_ink:.2f} mm (line centre) from the intended line (gate {GATE_MEAN_MM}) -> {'PASS' if passed else 'FAIL'}; {stray} stray points left out", flush=True)
