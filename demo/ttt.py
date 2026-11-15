"""Tic-tac-toe on paper against a person. The arm draws the grid and plays O; the person draws X with their own pen.

    python ttt.py

The webcam finds the A4 sheet in every photo (four corners), flattens it to millimetres and looks for NEW ink in
each of the nine cells. When exactly one empty cell has gained an X and the picture has stopped changing, the arm
answers. It never loses (full search of the game). Uses the same pen settings as the drawing loop: paper height
from height.json, 3 mm joint-slack lead, the size map learned on the house. The wrist-roll motor stays off.
A window on the laptop says whose turn it is. Pad stop key: the arm holds where it is.
"""
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

CELL = float(os.environ.get("CELL", "22"))      # mm
O_R = CELL * 0.35                                 # radius of the arm's O
PRESS, LIFT, SPEED, LEAD = float(os.environ.get("O_PRESS", "-0.17")), -0.3, 30.0, (4.5, 4.5)   # circle tests, 15 Nov 03:00: 4.5 mm lead + run-in gave 5.7 to 9.4 % out of round, no tail
GRID_PRESS = float(os.environ.get("GRID_PRESS", "-0.15"))   # the first grid, at -0.13, left almost no ink: straight lines take
                                                            # more pressure than curves without sticking (about 2 mm lower)
OUT = os.path.join(WT, "outputs", "demo", "ttt" + time.strftime("_%H%M%S")); os.makedirs(OUT, exist_ok=True)
grid = json.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_2x2.json")).read())
PLANE = json.loads(open(os.path.join(HERE, "height.json")).read())
M = np.array(json.loads(open(os.path.join(HERE, "house_map.json")).read()))
prior = json.loads(open(os.path.join(HERE, "ttt_prior.json")).read())   # which way the arm's axes lie on the sheet
halt = threading.Event()

PAN = [p["shoulder_pan.pos"] for p in grid["down"]]
RF = 105 / math.sin(math.radians((PAN[1] - PAN[0]) / 2))
RN = 105 / math.sin(math.radians((PAN[3] - PAN[2]) / 2))
R0, PAN0 = (RF + RN) / 2, math.radians(sum(PAN) / 4)
CX, CY = R0 * math.sin(PAN0), R0 * math.cos(PAN0)


def polar(X, Y):
    X, Y = np.array([X, Y, 1.0]) @ M
    return math.atan2(CX + X, CY - Y), math.hypot(CX + X, CY - Y)


def pose_polar(phi, rho, depth):
    v = (RF - rho) / (RF - RN)
    left, right = PAN[0] * (1 - v) + PAN[2] * v, PAN[1] * (1 - v) + PAN[3] * v
    u = (math.degrees(phi) - left) / (right - left)
    assert 0.02 <= u <= 0.98 and 0.02 <= v <= 0.98, (u, v)
    up, down = interpolate(grid["up"], 2, u, v), interpolate(grid["down"], 2, u, v)
    p = {k: down[k] + depth * (down[k] - up[k]) for k in down}
    assert all(math.isfinite(a) for a in p.values())
    p["gripper.pos"] = max(0.0, down["gripper.pos"] - 8)
    return p


def path(pts, lift=None, press=None):
    pol = [polar(X, Y) for X, Y in pts]
    out = []
    for i, ((phi, rho), (X, Y)) in enumerate(zip(pol, pts)):
        j = min(i, len(pol) - 2)
        turn, reach = (pol[j + 1][0] - pol[j][0]) * rho, pol[j + 1][1] - pol[j][1]
        depth = lift if lift is not None else PLANE[0] + PLANE[1] * X + PLANE[2] * Y + (PRESS if press is None else press)
        out.append(pose_polar(phi + LEAD[0] * math.tanh(turn / 0.3) / rho, rho + LEAD[1] * math.tanh(reach / 0.3), depth))
    return out


def dense(a, b, step=1.2):
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


H3 = 1.5 * CELL
GRID_LINES = [dense((-CELL / 2, H3), (-CELL / 2, -H3)), dense((CELL / 2, -H3), (CELL / 2, H3)),
              dense((-H3, CELL / 2), (H3, CELL / 2)), dense((H3, -CELL / 2), (-H3, -CELL / 2))]
centre = lambda c: ((c % 3 - 1) * CELL, (1 - c // 3) * CELL)                 # cell 0 = top-left in the arm's own axes
circle = lambda c: [(centre(c)[0] + O_R * math.sin(a), centre(c)[1] + O_R * math.cos(a)) for a in np.linspace(math.pi / 4, math.pi / 4 + 2 * math.pi + 0.5, int(2 * math.pi * O_R / 1.0) + 6)]   # starts where both joints are already moving
for s in GRID_LINES + [circle(c) for c in range(9)]:                          # every point checked before anything moves
    path(s)

WINS = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
winner = lambda b: next((b[a] for a, c, d in WINS if b[a] and b[a] == b[c] == b[d]), None)


def best_move(board):
    def score(b, turn):
        w = winner(b)
        if w:
            return 1 if w == "O" else -1
        free = [i for i in range(9) if not b[i]]
        if not free:
            return 0
        vals = [score(b[:i] + [turn] + b[i + 1:], "X" if turn == "O" else "O") for i in free]
        return max(vals) if turn == "O" else min(vals)
    free = [i for i in range(9) if not board[i]]
    return max(free, key=lambda i: (score(board[:i] + ["O"] + board[i + 1:], "X"), i == 4, i in (0, 2, 6, 8)))


class Keys(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            for raw in self.rfile:
                if raw.decode(errors="replace").strip() == "stop":
                    halt.set()
                self.wfile.write(b'{"ok": false, "reason": "tic-tac-toe"}\n')
        except OSError:
            pass


socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.daemon_threads = True
threading.Thread(target=socketserver.ThreadingTCPServer(("127.0.0.1", 8765), Keys).serve_forever, daemon=True).start()

root = tk.Tk(); root.title("Tic-tac-toe"); root.attributes("-topmost", True); root.geometry("1000x300+100+60"); root.protocol("WM_DELETE_WINDOW", lambda: None)
label = tk.Label(root, font=("Segoe UI", 34, "bold"), fg="white", bg="#a00", wraplength=960); label.pack(fill="both", expand=True)


def show(text, bg="#223"):
    label.config(text=text, bg=bg); root.update()


cam = vision.open_camera()
began = time.time()
def ready():
    """A sheet with all four corners in view; and, unless ANY=1 or RESUME=1, a clean one."""
    frame = vision.grab(cam)
    quad = None if frame is None else vision.find_sheet(frame)
    if quad is None:
        return "TIC-TAC-TOE: the camera must see all 4 corners of the sheet"
    if os.environ.get("ANY") == "1" or os.environ.get("RESUME") == "1":
        return None
    marks = int(vision.ink_mask(vision.flatten(frame, vision.homography(quad))).sum())
    return None if marks < 80 else "TIC-TAC-TOE: put in a FRESH sheet (ANY=1 to play on a used one)"


while (why := ready()):
    show(why, "#a00")
    if time.time() - began > 600:
        sys.exit("no sheet in view after 10 minutes; nothing moved")
    time.sleep(0.5)
for left in range(5, 0, -1):
    show(f"TIC-TAC-TOE: the arm draws the grid in {left}\nhands off the page; pad stop key holds the arm", "#a00"); time.sleep(1)

robot = arm.follower()
robot.config.disable_torque_on_disconnect = False
bus = robot.bus
bus.disable_torque("wrist_roll", num_retry=8)
bus.sync_read = (lambda read: lambda *a, **k: read(*a, **{**k, "num_retry": 12}))(bus.sync_read)
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
bus.sync_write("Torque_Limit", {j: 600 for j in JOINTS[:4]}, normalize=False, num_retry=5)
bus.write("Torque_Limit", "gripper", 380, normalize=False, num_retry=8)   # a game lasts minutes: 500 took the claw motor to 58 C
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


def stroke(pts, press=None, speed=SPEED):
    poses = path(pts, press=press)
    # Run-in: approach the start in the air along the direction the stroke leaves in, so the joints' slack is taken up
    # before the pen touches. Without it every circle began with a straight tail (it looked like a 6).
    dx, dy = pts[2][0] - pts[0][0], pts[2][1] - pts[0][1]; n_ = math.hypot(dx, dy) or 1.0
    run = path([(pts[0][0] - 9 * dx / n_, pts[0][1] - 9 * dy / n_), (pts[0][0] - 4 * dx / n_, pts[0][1] - 4 * dy / n_), pts[0]], lift=LIFT)
    move(run[0], 0.6); move(run[1], 0.3); move(run[2], 0.3)
    move(poses[0], 0.35)
    time.sleep(0.2)
    tick = time.perf_counter()
    for p in poses[1:]:
        if halt.is_set():
            raise KeyboardInterrupt
        bus.sync_write("Goal_Position", {j: (roll if j == "wrist_roll" else p[j + ".pos"]) for j in JOINTS})
        time.sleep(max(0.0, 1.2 / speed - (time.perf_counter() - tick))); tick = time.perf_counter()
    time.sleep(0.6)   # the soft motors trail the command: lifting at once cut about 10 mm off the end of every grid line
    move(path(pts[-2:], lift=LIFT)[-1], 0.3)


def away():
    move({**arm.read_pose(robot), **AWAY}, 1.2)
    time.sleep(0.4)


shots = [0]
def look():
    """One photo -> (sheet mapping, flattened page, ink mask), or None if the sheet's corners are hidden (a hand)."""
    frame = vision.grab(cam, 3)
    quad = None if frame is None else vision.find_sheet(frame)
    if quad is None:
        return None
    H = vision.homography(quad)
    flat = vision.flatten(frame, H)
    shots[0] += 1
    if shots[0] % 6 == 1:
        cv2.imwrite(os.path.join(OUT, f"{shots[0]:04d}.jpg"), cv2.resize(frame, (960, 540)))
    return H, flat, vision.ink_mask(flat), vision.ink_mask(flat, dark=20)   # the last one also catches a faint pen


def fit(ref, ink, R, t):
    """Scale, turn and shift taking the arm's plan (mm) onto ink on the sheet (mm), starting near R, t.
    The start decides whether the plan is mirrored on the sheet; that never changes here (a grid looks the
    same mirrored or turned 90 degrees, so only the start can tell which square is which)."""
    s, mirrored = 1.0, np.linalg.det(R) < 0
    for _ in range(25):
        q = s * ref @ R.T + t
        d = np.linalg.norm(ink[None, :, :] - q[:, None, :], axis=2)
        ok = d.min(1) < 12
        a, b = ref[ok], ink[d.argmin(1)][ok]
        ca, cb = a.mean(0), b.mean(0)
        u, sv, vt = np.linalg.svd((a - ca).T @ (b - cb))
        sign = np.sign(np.linalg.det(vt.T @ u.T)) * (-1 if mirrored else 1)
        R = vt.T @ np.diag([1.0, sign]) @ u.T
        s = float((sv * [1.0, sign]).sum() / ((a - ca) ** 2).sum())
        t = cb - s * ca @ R.T
    return s, R, t


board, result = [None] * 9, "stopped"
try:
    away()
    while (seen := look()) is None:
        show("the camera cannot see the whole sheet", "#a00"); time.sleep(0.5)
    resume = os.environ.get("RESUME") == "1"
    before = np.zeros_like(seen[2]) if resume else seen[2]
    if not resume:
        show("drawing the grid")
        for line in GRID_LINES:
            stroke(line, press=GRID_PRESS, speed=25.0)
        away()
    while (seen := look()) is None:
        show("move your hand: the camera cannot see the whole sheet", "#a00"); time.sleep(0.5)
    H0, flat, mask, faint = seen
    new = cv2.subtract(mask, cv2.dilate(before, np.ones((7, 7), np.uint8)))
    ink = vision.points(cv2.morphologyEx(new, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)))
    if len(ink) < 400:
        raise SystemExit(f"the grid left almost no ink ({len(ink)} points): pen cap, pen height or grip?")
    ink = ink[::max(1, len(ink) // 1500)]
    ref = np.array([p for line in GRID_LINES for p in line[::3]])
    R = np.array(prior["R"]); t = ink.mean(0) - ref.mean(0) @ R.T
    # A grid looks almost the same shifted by one square, and the fit once settled exactly one square off (15 Nov:
    # it read an X in the centre as the square beside it and then drew its O on top of that X). So the fit is started
    # from the middle and from one square off in each direction, and the answer kept is the one where every drawn line
    # has a planned line AND every planned line has ink.
    def misfit(s_, R_, t_):
        q = s_ * ref @ R_.T + t_
        d = np.linalg.norm(ink[None, :, :] - q[:, None, :], axis=2)
        return float(np.minimum(d.min(0), 15).mean() + np.minimum(d.min(1), 15).mean())
    R_start, t_start = R, t
    tries = [fit(ref, ink, R_start, t_start + np.array([i, j]) * CELL) for i in (-1, 0, 1) for j in (-1, 0, 1)]
    s, R, t = min(tries, key=lambda f: misfit(*f))
    print("grid fit: misfit of the nine starts (mm)", sorted(round(misfit(*f), 1) for f in tries), flush=True)
    if not 0.7 <= s <= 1.5:
        raise SystemExit(f"could not find the grid on the page (fit says {100 * s:.0f} % of plan size from {len(ink)} ink points): too faint? Not playing.")
    print(f"grid found on the sheet: drawn at {100 * s:.0f} % of plan size, turned {math.degrees(math.atan2(R[1, 0], R[0, 0])):.0f} deg", flush=True)
    to_sheet = lambda p: s * np.array(p) @ R.T + t                              # arm plan mm -> sheet mm (where the grid is)
    cells = [to_sheet(centre(c)) for c in range(9)]
    accepted = mask.copy()                                                      # ink already accounted for
    if resume:                                    # marks already inside squares are read as moves, starting with the person's
        half = int(0.36 * CELL * s * vision.PX)
        for (x, y) in cells:
            x, y = int(x * vision.PX), int(y * vision.PX)
            accepted[max(0, y - half):y + half, max(0, x - half):x + half] = 0

    def cell_ink(mask_now):
        """Ink inside the middle of each square, in pixels. Counted afresh in every photo: comparing photo against photo
        pixel by pixel broke down when the sheet crept a millimetre (every old line then looked new)."""
        half = int(0.30 * CELL * s * vision.PX)
        counts = []
        for (x, y) in cells:
            x, y = int(x * vision.PX), int(y * vision.PX)
            counts.append(int(mask_now[max(0, y - half):y + half, max(0, x - half):x + half].sum()))
        return counts

    preset = os.environ.get("BOARD", ".........")                               # e.g. O...X.... to carry on a game
    board = [ch if ch in "XO" else None for ch in preset]
    base = [n if board[c] else 0 for c, n in enumerate(cell_ink(faint))] if resume else cell_ink(faint)   #                                # what each square holds before the next move
    while True:
        if winner(board) or all(board):
            break
        show("YOUR TURN: draw an X in an empty square, then take your hand away", "#063")
        steady, choice = 0, None
        while steady < 2:                                                       # the same single new X in two photos running
            if halt.is_set():
                raise KeyboardInterrupt
            root.update(); time.sleep(0.5)
            seen = look()
            if seen is None:
                steady = 0; continue
            gain = [max(0, now - was) for now, was in zip(cell_ink(seen[3]), base)]
            top = max(range(9), key=lambda c: gain[c])
            # The square that gained the most ink is the move, if it holds most of the gain. A person's X often spills
            # into its neighbours; a hand over the board adds ink everywhere and is not a move.
            if gain[top] > 220 and not board[top] and gain[top] >= 0.5 * sum(gain):
                steady, choice = (steady + 1 if top == choice else 1), top
            else:
                steady = 0
            if shots[0] % 6 == 0:
                print("  looking: ink gained per square", gain, flush=True)
        board[choice] = "X"; H_now = seen[0]
        print("person played", choice, "| board", "".join(b or "." for b in board), flush=True)
        if winner(board) or all(board):
            break
        mine = best_move(board)
        show("my turn: O")
        # If the sheet has crept since the grid was drawn, aim at where that cell is NOW on the table.
        shift = np.zeros(2)
        px = np.linalg.inv(H_now) @ np.append(cells[mine], 1.0)
        was = H0 @ px; was = was[:2] / was[2]                                   # that spot, in the sheet frame of the grid photo
        shift = (was - cells[mine]) @ R / s                                     # in the arm's plan axes, mm
        if np.linalg.norm(shift) > 15:
            shift = np.zeros(2)
        stroke([(x + shift[0], y + shift[1]) for x, y in circle(mine)])
        board[mine] = "O"
        away()
        while (seen := look()) is None:
            show("move your hand: the camera cannot see the whole sheet", "#a00"); time.sleep(0.5)
        base = cell_ink(seen[3])
        print("arm played", mine, f"(sheet moved {np.linalg.norm(shift):.1f} mm)", "| board", "".join(b or "." for b in board), flush=True)
    w = winner(board)
    result = "the arm wins" if w == "O" else "the person wins" if w == "X" else "a draw"
    if w == "O":
        a, _, c = next(line for line in WINS if all(board[i] == "O" for i in line))
        stroke(dense(centre(a), centre(c)), press=GRID_PRESS)
        away()
    show({"the arm wins": "I WIN. Good game!", "a draw": "A DRAW. Good game!", "the person wins": "YOU WIN?! Well played."}[result], "#063")
    print("RESULT:", result, flush=True)
    cv2.imwrite(os.path.join(OUT, "final.jpg"), vision.grab(cam, 6))
    for _ in range(40):
        root.update(); time.sleep(0.1)
except KeyboardInterrupt:
    print("STOPPED: the arm is holding where it was", flush=True)
finally:
    print("temps", bus.sync_read("Present_Temperature", normalize=False), flush=True)
    bus.write("Torque_Limit", "gripper", 300, normalize=False, num_retry=8)
    robot.disconnect()
    cam.release()
