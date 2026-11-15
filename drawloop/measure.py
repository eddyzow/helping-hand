"""Touch the pen down at 8 points round the circle to measure the paper height at each, then draw the circle
through those heights. Poses come from the taught 2x2 grid (Eddy's grid.py); 'depth' moves along the taught
up->down direction: 0 = taught down, +1 = about 2 cm lower. Photos are saved all the way through."""
import json, math, os, socketserver, sys, threading, time
import tkinter as tk
import cv2

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo root
OUT = os.path.join(WT, "outputs", "drawloop")
os.makedirs(OUT, exist_ok=True)
os.environ.update(FOLLOWER_PORT="COM3", ARM_NO_PROMPT="1")
sys.path.insert(0, WT)
import arm
from grid import interpolate

CU, CV, R = 0.5, 0.5, float(os.environ.get("CIRCLE_R", "0.2"))
PRESS = float(os.environ.get("PRESS", "-0.1"))   # added to the detected depth; detection fires a little after first touch
grid = json.loads(open(os.path.join(WT, "poses", "paper_2x2.json")).read())
halt = threading.Event()


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


def pose(u, v, depth):
    up, down = interpolate(grid["up"], 2, u, v), interpolate(grid["down"], 2, u, v)
    p = {k: down[k] + depth * (down[k] - up[k]) for k in down}
    assert all(math.isfinite(x) for x in p.values())
    p["gripper.pos"] = max(0.0, down["gripper.pos"] - 8)
    return p


cam = cv2.VideoCapture(1, cv2.CAP_DSHOW)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280); cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)


def photo(name, flush=4):
    for _ in range(flush):
        ok, frame = cam.read()
    if ok:
        cv2.imwrite(os.path.join(OUT, name), frame)


root = tk.Tk(); root.attributes("-topmost", True); root.geometry("1000x300+100+100"); root.protocol("WM_DELETE_WINDOW", lambda: None)
label = tk.Label(root, font=("Segoe UI", 40, "bold"), fg="white", bg="#a00"); label.pack(fill="both", expand=True)
import vision
cam.release(); cam = vision.open_camera(); began_wait = time.time()
while vision.find_sheet(vision.grab(cam)) is None:
    label.config(text="waiting: the camera must see all 4 corners of the sheet"); root.update()
    if time.time() - began_wait > 300:
        sys.exit("no sheet in view after 5 minutes; nothing moved")
    time.sleep(0.5)
for left in range(5, 0, -1):
    label.config(text=f"FOLLOWER ARM MOVES IN {left}\nhands clear, pad stop key holds it"); root.update(); time.sleep(1)
label.config(text="measuring the paper height at 5 points", bg="#223"); root.update()

robot = arm.follower()
robot.config.disable_torque_on_disconnect = False
bus = robot.bus
bus.sync_read = (lambda read: lambda *a, **k: read(*a, **{**k, "num_retry": 12}))(bus.sync_read)
bus.sync_write("Torque_Limit", {j: 600 for j in ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]}, normalize=False, num_retry=5)
roll = arm.read_pose(robot)["wrist_roll.pos"]
bus.write("Torque_Limit", "gripper", 250, normalize=False, num_retry=8)


def move(target, seconds):
    start = arm.read_pose(robot)
    steps = max(1, int(seconds * 30))
    for i in range(1, steps + 1):
        if halt.is_set():
            raise KeyboardInterrupt
        robot.send_action({**{k: start[k] + (target[k] - start[k]) * i / steps for k in target}, "wrist_roll.pos": roll})
        time.sleep(1 / 30)
    root.update()


def lag(target):
    here = arm.read_pose(robot)
    return [target[j] - here[j] for j in ("shoulder_lift.pos", "elbow_flex.pos")]


def touch(u, v, tag):
    """Lower in 2 mm steps until the arm's following error changes (the table starts carrying it)."""
    move(pose(u, v, -0.9), 1.2)
    free = []
    for i in range(28):
        depth = round(-0.4 + 0.1 * i, 2)
        target = pose(u, v, depth)
        move(target, 0.25)
        time.sleep(0.35)
        now = lag(target)
        if i < 3:
            free.append(now)
            continue
        base = [sum(f[k] for f in free) / len(free) for k in (0, 1)]
        change = math.hypot(now[0] - base[0], now[1] - base[1])
        if change > 0.45:
            photo(f"touch_{tag}.jpg")
            move(pose(u, v, -0.9), 0.6)
            return depth, round(change, 2)
    move(pose(u, v, -0.9), 0.6)
    return None, None



PAN = [p["shoulder_pan.pos"] for p in grid["down"]]
RF = 105 / math.sin(math.radians((PAN[1] - PAN[0]) / 2))
RN = 105 / math.sin(math.radians((PAN[3] - PAN[2]) / 2))
R0, PAN0 = (RF + RN) / 2, math.radians(sum(PAN) / 4)
CX, CY = R0 * math.sin(PAN0), R0 * math.cos(PAN0)


def uv(X, Y):
    x, y = CX + X, CY - Y
    v = (RF - math.hypot(x, y)) / (RF - RN)
    left, right = PAN[0] * (1 - v) + PAN[2] * v, PAN[1] * (1 - v) + PAN[3] * v
    return (math.degrees(math.atan2(x, y)) - left) / (right - left), v


POINTS = [(0, 0), (25, 25), (-25, 25), (-25, -25), (25, -25)]
import numpy as np
try:
    first = pose(*uv(*POINTS[0]), -0.9)
    here = arm.read_pose(robot)
    move({**here, **{k: first[k] for k in ("shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos")}}, 3.0)   # up first, then across
    found = []
    for i, (X, Y) in enumerate(POINTS):
        d, change = touch(*uv(X, Y), f"m{i}")
        print(f"point {i} at X={X} Y={Y}: touch depth {d} (change {change})", flush=True)
        if d is not None:
            found.append((X, Y, d))
    if len(found) < 4:
        raise SystemExit(f"only {len(found)} of 5 points found the paper; height not saved")
    f = np.array(found)
    plane, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(f)), f[:, 0], f[:, 1]]), f[:, 2], rcond=None)
    json.dump(plane.tolist(), open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "height.json"), "w"))
    print("PLANE", plane.round(4).tolist(), "was [1.03, 0.0029, 0.0043]; worst misfit", float(np.abs(np.column_stack([np.ones(len(f)), f[:, 0], f[:, 1]]) @ plane - f[:, 2]).max().round(3)), flush=True)
    move(pose(0.5, 0.97, -1.0), 2.5)
    print("DONE", flush=True)
except KeyboardInterrupt:
    print("STOPPED: the arm is holding where it was", flush=True)
finally:
    bus.write("Torque_Limit", "gripper", 180, normalize=False, num_retry=8)
    cam.release()
    robot.disconnect()
