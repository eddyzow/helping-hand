"""Playtest on one sheet: eight 16 mm circles (the size of a flower petal, the shape that came out square), each
with a different pen pressure, pen speed and motor position gain. After every circle the arm folds back, the
webcam photographs the page, and that circle's own ink is measured: how round, how complete, how wide the line.

    row 1: motor gain 16 (LeRobot's default)      row 2: motor gain 32
    columns: light+slow, light+fast, firm+slow, firm+fast

Stroke points are written straight to the motors (no read first), so the pen can be commanded 50 times a second.
The gain is put back to 16 at the end (LeRobot also resets it at every connect)."""
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

OUT = os.path.join(WT, "outputs", "drawloop", "playtest" + time.strftime("_%H%M%S"))
os.makedirs(OUT, exist_ok=True)
grid = json.loads(open(os.path.join(WT, "poses", "paper_2x2.json")).read())
PLANE = json.loads(open(os.path.join(HERE, "height.json")).read())
M = np.array(json.loads(open(os.path.join(HERE, "house_map.json")).read()))   # command = [X, Y, 1] @ M, learned on the house
LIFT, RADIUS = -0.3, 8.0
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
GAINED = JOINTS[:4]
PRESSES = {"light": float(os.environ.get("LIGHT", "-0.22")), "firm": float(os.environ.get("FIRM", "-0.12"))}
SPEEDS = {"slow": 25.0, "fast": 50.0}
TESTS = [dict(gain=g, press=p, speed=s, X=-30 + 20 * i, Y=12 if g == 16 else -12)
         for g in (16, 32) for i, (p, s) in enumerate([("light", "slow"), ("light", "fast"), ("firm", "slow"), ("firm", "fast")])]
halt = threading.Event()

PAN = [p["shoulder_pan.pos"] for p in grid["down"]]
RF = 105 / math.sin(math.radians((PAN[1] - PAN[0]) / 2))
RN = 105 / math.sin(math.radians((PAN[3] - PAN[2]) / 2))
R0, PAN0 = (RF + RN) / 2, math.radians(sum(PAN) / 4)
CX, CY = R0 * math.sin(PAN0), R0 * math.cos(PAN0)


def pose(X, Y, lift=None, press=0.0):
    depth = lift if lift is not None else PLANE[0] + PLANE[1] * X + PLANE[2] * Y + press   # height from the plan's position
    X, Y = np.array([X, Y, 1.0]) @ M
    x, y = CX + X, CY - Y
    v = (RF - math.hypot(x, y)) / (RF - RN)
    left, right = PAN[0] * (1 - v) + PAN[2] * v, PAN[1] * (1 - v) + PAN[3] * v
    u = (math.degrees(math.atan2(x, y)) - left) / (right - left)
    assert 0.02 <= u <= 0.98 and 0.02 <= v <= 0.98, (X, Y, u, v)
    up, down = interpolate(grid["up"], 2, u, v), interpolate(grid["down"], 2, u, v)
    p = {k: down[k] + depth * (down[k] - up[k]) for k in down}
    assert all(math.isfinite(a) for a in p.values())
    p["gripper.pos"] = max(0.0, down["gripper.pos"] - 8)
    return p


def circle(t):
    n = int(2 * math.pi * RADIUS)                       # about 1 mm between points
    return [(t["X"] + RADIUS * math.sin(2 * math.pi * i / n), t["Y"] + RADIUS * math.cos(2 * math.pi * i / n)) for i in range(n + 6)]


for t in TESTS:                                          # every point checked before anything moves
    for X, Y in circle(t):
        pose(X, Y, press=PRESSES[t["press"]])


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
began = time.time()
while True:
    frame = vision.grab(cam)
    quad = None if frame is None else vision.find_sheet(frame)
    if quad is not None:
        H = vision.homography(quad)
        if vision.ink_mask(vision.flatten(frame, H)).sum() < 60:
            break
    show("PLAYTEST: put a FRESH sheet in place, all 4 corners in view", "#a00")
    if time.time() - began > 300:
        sys.exit("no clean sheet in view after 5 minutes; nothing moved")
    time.sleep(0.5)
for left in range(5, 0, -1):
    show(f"PLAYTEST: FOLLOWER ARM DRAWS IN {left}\nhands off the page, pad stop key holds the arm", "#a00"); time.sleep(1)

robot = arm.follower()
robot.config.disable_torque_on_disconnect = False
bus = robot.bus
bus.sync_read = (lambda read: lambda *a, **k: read(*a, **{**k, "num_retry": 12}))(bus.sync_read)
bus.sync_write("Torque_Limit", {j: 600 for j in JOINTS[:5]}, normalize=False, num_retry=5)
bus.write("Torque_Limit", "gripper", 220, normalize=False, num_retry=8)
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


def set_gain(gain):
    for name in GAINED:                                  # one joint at a time, so the arm never goes limp as a whole
        with bus.torque_disabled(name):
            bus.write("P_Coefficient", name, gain, num_retry=8)
    print("motor gain", gain, bus.sync_read("P_Coefficient", GAINED, normalize=False), flush=True)


def away_photo(name):
    move({**arm.read_pose(robot), **AWAY}, 1.4)
    time.sleep(0.5)
    frame = vision.grab(cam)
    cv2.imwrite(os.path.join(OUT, name + ".jpg"), frame)
    return vision.flatten(frame, H)


flats, gain, done = [], 16, False
try:
    flats.append(away_photo("0_blank"))
    for k, t in enumerate(TESTS):
        show(f"PLAYTEST circle {k + 1} of 8: gain {t['gain']}, {t['press']} pressure, {t['speed']}")
        if t["gain"] != gain:
            gain = t["gain"]; set_gain(gain)
        pts, press = circle(t), PRESSES[t["press"]]
        move(pose(*pts[0], lift=LIFT), 1.0)
        move(pose(*pts[0], press=press), 0.4)
        time.sleep(0.2)
        tick, t0 = time.perf_counter(), time.perf_counter()
        for X, Y in pts[1:]:
            if halt.is_set():
                raise KeyboardInterrupt
            p = pose(X, Y, press=press)
            bus.sync_write("Goal_Position", {j: (roll if j == "wrist_roll" else p[j + ".pos"]) for j in JOINTS})
            time.sleep(max(0.0, 1.0 / SPEEDS[t["speed"]] - (time.perf_counter() - tick))); tick = time.perf_counter()
        t["mm_s"] = round((len(pts) - 1) / (time.perf_counter() - t0), 1)
        time.sleep(0.15)
        move(pose(*pts[-1], lift=LIFT), 0.3)
        flats.append(away_photo(f"{k + 1}_gain{t['gain']}_{t['press']}_{t['speed']}"))
    done = True
except KeyboardInterrupt:
    print("STOPPED: the arm is holding where it was", flush=True)
finally:
    if gain != 16:
        set_gain(16)
    print("temps", bus.sync_read("Present_Temperature", normalize=False), flush=True)
    bus.write("Torque_Limit", "gripper", 150, normalize=False, num_retry=8)
    robot.disconnect()
    cam.release()
if not done:
    sys.exit(1)

masks = [vision.ink_mask(f) for f in flats]
print(f"{'gain':>4} {'press':>6} {'speed':>5} {'mm/s':>5} | {'drawn %':>7} {'diam mm':>7} {'out-of-round %':>14} {'square %':>8} {'line mm':>7}")
results = []
for k, t in enumerate(TESTS):
    new = cv2.subtract(masks[k + 1], cv2.dilate(masks[k], np.ones((5, 5), np.uint8)))
    new = cv2.morphologyEx(new, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    p = vision.points(new)
    if len(p) > 200:                                     # keep this circle's blob only: within 20 mm of the densest spot
        p = p[np.linalg.norm(p - np.median(p, axis=0), axis=1) < 20]
    if len(p) < 40:
        results.append({**t, "drawn_pct": 0}); print(f"{t['gain']:>4} {t['press']:>6} {t['speed']:>5} {t['mm_s']:>5} | no ink"); continue
    A = np.column_stack([2 * p, np.ones(len(p))])        # least-squares circle
    (cx, cy, c), *_ = np.linalg.lstsq(A, (p ** 2).sum(1), rcond=None)
    r = np.linalg.norm(p - [cx, cy], axis=1); mean_r = math.sqrt(c + cx * cx + cy * cy)
    ang = np.arctan2(p[:, 1] - cy, p[:, 0] - cx)
    bins = np.floor((ang + math.pi) / (2 * math.pi) * 36).astype(int) % 36
    profile = np.array([r[bins == b].mean() for b in range(36) if (bins == b).any()])
    angles = np.array([(b + 0.5) / 36 * 2 * math.pi for b in range(36) if (bins == b).any()])
    out = {**t, "drawn_pct": round(100 * len(profile) / 36), "diam_mm": round(2 * mean_r, 1),
           "out_of_round_pct": round(100 * profile.std() / mean_r, 1),
           "square_pct": round(100 * 2 * abs(np.mean(profile * np.exp(4j * angles))) / mean_r, 1),   # 4-cornered share of the wobble
           "line_mm": round(len(p) / vision.PX ** 2 / (2 * math.pi * mean_r), 1)}
    results.append(out)
    print(f"{t['gain']:>4} {t['press']:>6} {t['speed']:>5} {t['mm_s']:>5} | {out['drawn_pct']:>7} {out['diam_mm']:>7} {out['out_of_round_pct']:>14} {out['square_pct']:>8} {out['line_mm']:>7}")
json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=1)
ys, xs = np.nonzero(masks[-1])
if len(xs):
    x0, y0, x1, y1 = max(0, xs.min() - 60), max(0, ys.min() - 60), xs.max() + 60, ys.max() + 60
    cv2.imwrite(os.path.join(OUT, "sheet.jpg"), cv2.resize(flats[-1][y0:y1, x0:x1], None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC))
print("PLAYTEST DONE", OUT, flush=True)
