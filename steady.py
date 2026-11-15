"""Steady Hand: the follower copies the leader with the tremor taken out.

    python steady.py                 # teleoperate; first run asks you to line the two arms up
    python steady.py --measure       # redo the line-up
    python steady.py --yes           # no Enter prompts (the arm must already be resting)

A person holds the leader arm. Deliberate movement is slow (below about 2 Hz); tremor is fast
(roughly 4 to 12 Hz). A low-pass filter between the two arms lets the first through and holds the
second back, so the follower moves where the hand means to go without the shake.

While it runs it also MEASURES the hand: how big the shake is at the fingertip (mm), how fast
(Hz), and how much of it the filter removed. That is written to outputs/steady/ as one CSV per
session and served to the dashboard at http://127.0.0.1:8780/state; one summary per session goes
to outputs/steady/sessions.json, served at /sessions.

Keys (the keypad listener and typed commands both arrive on port 8765, like the dispatcher's):
    middle key  -> steady mode on/off (the A/B that shows what the filter does)
    jump key    -> hold: the follower freezes and keeps holding, the person can let go and rest
    stop key    -> hold, at once
    typed: filter on|off (the A/B: off lets the shake through), hold on|off, cutoff <Hz>,
           test (10 s hold-still score), status, quit
    spoken: "steady on" = filter on and follow; "steady off" = FREEZE (hold). A spoken "off" never
            makes the arm copy the shake.

Limits, stated plainly: this is a prototype, tested only with a person shaking the leader on
purpose. The arm holds light things (well under 200 g). Grip effort and arm load are the motors'
own load readings, an estimate, not a measured force. The follower's speed is capped.
"""
import collections
import json
import math
import os
import socketserver
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np

from core import tremor
from core.tremor import (CUTOFF_HZ, GRIP_CUTOFF_HZ, TRIGGER, Fingertip, GripHold, HoldStillTest, LowPass, Session,
                         band_rms_and_peak, insights)

HERE = Path(__file__).parent
OFFSETS = HERE / "poses" / "teleop_offset.json"
OUT = HERE / "outputs" / "steady"
SESSIONS = OUT / "sessions.json"
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
KEYS = [f"{j}.pos" for j in JOINTS]
HZ = 50
MAX_SPEED = 120.0        # degrees per second: the follower never moves faster than this, whatever the hand does
MAX_STEP = 15.0          # LeRobot's own per-command limit, in degrees
EASE_S = 3.0             # at the start and after a hold the follower glides to the leader over this long
WINDOW_S = 4.0           # how much history the tremor measurement looks at
GRIP_FLOOR = 7.0         # the follower's claw is never commanded tighter than this (0 to 100). Its jaws meet at
                         # about 5.3 (measured closing on nothing), so anything lower pushes them together at full
                         # effort for as long as the leader's claw is shut: 98 % load in the first three real runs.
ELBOW_MAX = 64.0         # degrees: the follower's elbow cannot go past this until that joint is recalibrated
TABLE_Z = -12.0          # mm, the table top in the model's frame: measured by touch, between -9 and -27 across the reach
# --shake HZ DEG adds a pretend tremor; like a real one it is not the same size or in step on every joint
SHAKE_SHARE = np.array([0.6, 0.5, 0.7, 1.0, 0.8, 0.0])
SHAKE_PHASE = np.array([0.0, 1.3, 2.1, 0.4, 2.9, 0.0])

state = {"steady": True, "hold": False, "cutoff": CUTOFF_HZ, "quit": False, "grip_hold": True, "release": False}
shared = {"t": 0.0, "tremor_mm": 0.0, "tremor_hz": 0.0, "out_mm": 0.0, "removed_pct": 0.0, "grip_effort": 0.0,
          "arm_load": 0.0, "speed_mm_s": 0.0, "leader": [0.0] * 6, "follower": [0.0] * 6, "raw_tip": [0.0] * 3,
          "smooth_tip": [0.0] * 3, "history": [], "raw_chain": [], "out_chain": [], "robot": [], "hand": [], "table_z": TABLE_Z,
          "test": {"running": False, "seconds_left": 0, "score": None, "tremor_mm": None}}
lock = threading.Lock()
hold_test = HoldStillTest()


def read_sessions(path=SESSIONS):
    """The saved session summaries, or [] if the file is missing or unreadable."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return []


def save_sessions(sessions, path=SESSIONS):
    """Write through a temp file, so a crash mid-write never leaves half a file."""
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(sessions, indent=1))
    os.replace(temp, path)


class Commands(socketserver.StreamRequestHandler):
    def handle(self):
        for raw in self.rfile:
            line = raw.decode(errors="replace").strip()
            self.wfile.write((json.dumps(command(line)) + "\n").encode())


def command(line: str) -> dict:
    word, _, rest = line.partition(" ")
    rest = rest.strip()
    with lock:
        # Two different things, kept apart on purpose (review, 14 Nov):
        #   filter on|off  = the A/B for the demo: off lets the hand's shake THROUGH to the arm. Only the
        #                    middle key, the dashboard button and a typed "filter off" can do that.
        #   steady on|off  = what a person SAYS. "Steady off" must never mean "now copy my shake", so it
        #                    freezes the arm (hold). "Steady on" releases the hold and turns the filter on.
        if line in ("run gesture", "run wave") or (word == "filter" and rest in ("", "toggle")):  # the middle key
            state["steady"] = not state["steady"]
        elif word == "filter" and rest in ("on", "off"):
            state["steady"] = rest == "on"
        elif word == "steady" and rest == "off":
            state["hold"] = True
        elif word == "steady" and rest == "on":
            state["steady"], state["hold"] = True, False
        elif line == "key down" or (word == "hold" and rest in ("", "toggle")):                 # the jump key
            state["hold"] = not state["hold"]
        elif word == "hold" and rest in ("on", "off"):
            state["hold"] = rest == "on"
        elif word == "stop":
            state["hold"] = True
        elif word == "cutoff":
            try:
                state["cutoff"] = min(8.0, max(0.5, float(rest)))
            except ValueError:
                return {"ok": False, "reason": "cutoff needs a number of Hz, 0.5 to 8"}
        elif word == "test":   # the ten-second hold-still test; the main loop feeds it and ends it
            hold_test.start(time.perf_counter())
            shared["test"] = hold_test.view(time.perf_counter())
        elif word == "quit":
            state["quit"] = True
        elif (word == "grip" and rest in ("hold on", "hold off")) or (word == "latch" and rest in ("on", "off", "", "toggle")):
            # grip hold: see core.tremor.GripHold. "latch" is the old name, kept so older callers still work
            on = rest.split()[-1] if rest else "toggle"
            state["grip_hold"] = (not state["grip_hold"]) if on == "toggle" else on == "on"
        elif line == "grip release":
            if state["hold"]:   # a held arm does not move, the claw included
                return {"ok": False, "reason": "the arm is held; say 'steady on' first, then 'let go'"}
            state["release"] = True
        elif word == "voice":   # RobTop's voice script reports what it heard and said, for the dashboard
            try:
                said = json.loads(rest)
                shared["voice"] = {"heard": str(said.get("heard", ""))[:200], "said": str(said.get("said", ""))[:200],
                                   "at": shared["t"]}
            except (ValueError, AttributeError):
                return {"ok": False, "reason": 'voice needs JSON: {"heard": "...", "said": "..."}'}
        elif word in ("status", "key", "clock", "ready", "remote", "cue", "home"):
            pass  # the keypad listener's other reports: nothing to do here
        else:
            return {"ok": False, "reason": "commands: steady on|off, filter on|off, hold on|off, cutoff <Hz>, grip hold on|off, "
                                           "grip release, test, status, quit"}
        return {"ok": True, **{k: state[k] for k in ("steady", "hold", "cutoff", "grip_hold")}, "latch": state["grip_hold"]}


STATIC = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
          ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}


class Dashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/cmd?"):   # the dashboard's buttons: /cmd?steady%20off
            from urllib.parse import unquote
            body, kind = json.dumps(command(unquote(self.path[5:]))).encode(), "application/json"
        elif self.path.startswith("/state"):
            with lock:
                body = json.dumps({**{k: state[k] for k in ("steady", "hold", "cutoff")}, **shared}).encode()
            kind = "application/json"
        elif self.path.startswith("/sessions"):
            body, kind = json.dumps(read_sessions()).encode(), "application/json"
        elif self.path.startswith("/dashboard/"):   # the dashboard's own scripts and styles, from the dashboard/ folder
            root = (HERE / "dashboard").resolve()
            file = (root / self.path[len("/dashboard/"):].split("?")[0]).resolve()
            if root not in file.parents or not file.is_file() or file.suffix not in STATIC:
                self.send_error(404)
                return
            body, kind = file.read_bytes(), STATIC[file.suffix]
        elif self.path.startswith("/meshes/"):   # the robot's STL files for the 3D view, only from the model's assets folder
            root = (tremor.ROOT / tremor.MODEL / "assets").resolve()
            name = self.path[len("/meshes/"):].split("?")[0]
            if name == "index.json":
                body, kind = json.dumps(sorted(f.name for f in root.glob("*.stl"))).encode(), "application/json"
            else:
                file = (root / name).resolve()
                if root not in file.parents or not file.is_file() or file.suffix != ".stl":
                    self.send_error(404)
                    return
                body, kind = file.read_bytes(), "model/stl"
        else:
            page = HERE / "steady_dashboard.html"
            body = page.read_bytes() if page.exists() else b"steady_dashboard.html is not written yet; /state has the numbers"
            kind = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main() -> None:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    import logging
    logging.getLogger("lerobot.robots.utils").setLevel(logging.ERROR)  # its per-command "clamped" warning floods the screen
    ask = (lambda text: None) if "--yes" in sys.argv else input
    shake_hz, shake_deg = (float(v) for v in sys.argv[sys.argv.index("--shake") + 1:][:2]) if "--shake" in sys.argv else (0.0, 0.0)
    seconds = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else None
    state["grip_hold"] = "--no-latch" not in sys.argv   # grip hold is on unless asked otherwise
    measure = "--measure" in sys.argv or not OFFSETS.exists()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    keys = socketserver.ThreadingTCPServer(("127.0.0.1", int(os.environ.get("BUDDY_PORT", "8765"))), Commands)
    threading.Thread(target=keys.serve_forever, daemon=True).start()
    web = HTTPServer(("127.0.0.1", 8780), Dashboard)
    threading.Thread(target=web.serve_forever, daemon=True).start()

    follower = SO101Follower(SO101FollowerConfig(
        port=os.environ.get("FOLLOWER_PORT", "COM3"), id="follower", max_relative_target=MAX_STEP))
    leader = SO101Leader(SO101LeaderConfig(port=os.environ.get("LEADER_PORT", "COM4"), id="leader"))
    # An arm that holds is safer than an arm that drops. So on ANY exit the follower's motors stay on,
    # unless a person at the keyboard confirms they are holding it (the prompt in the clean shutdown).
    follower.config.disable_torque_on_disconnect = False
    clean = False
    ask("The follower's motors switch off and on while connecting. Hold it or check it is resting, then Enter. ")
    follower.connect()
    leader.connect()
    tip = Fingertip()
    OUT.mkdir(parents=True, exist_ok=True)
    log = (OUT / f"session_{time.strftime('%Y%m%d_%H%M%S')}.csv").open("w")
    log.write("t_s,steady,hold,tremor_mm,tremor_hz,arm_shake_mm,removed_pct,grip_effort,arm_load\n")
    session, past, warned = Session(datetime.now().isoformat(timespec="seconds")), read_sessions(), []

    def save_history():   # never raises into the control loop
        if not session.n:
            return
        try:
            save_sessions(past + [session.summary()])
        except OSError as error:
            if not warned:
                warned.append(True)
                print(f"  could not write {SESSIONS}: {error}", flush=True)

    try:
        if measure:
            ask("The follower goes LIMP next. Hold it, then Enter. ")
            follower.bus.disable_torque()
            ask("Fold BOTH arms fully against their end stops, claws closed, both pointing straight ahead. Then Enter. ")
            lead, follow = leader.get_action(), follower.get_observation()
            OFFSETS.write_text(json.dumps({k: round(float(follow[k]) - float(lead[k]), 2) for k in KEYS}, indent=1))
            follower.bus.enable_torque()
            ask("The follower is holding again. Let go of it, take the leader, then Enter to start. ")
        offset = np.array([float(json.loads(OFFSETS.read_text())[k]) for k in KEYS])
        if not np.all(np.isfinite(offset)):   # checked before anything is sent to the arm
            raise ValueError(f"{OFFSETS} holds a value that is not a number; run steady.py --measure again")

        def read_leader():
            """The leader's six joints in the follower's terms. Raises if any is not a finite number:
            a bad reading must never become a command."""
            action = leader.get_action()
            joints = np.array([float(action[k]) for k in KEYS]) + offset
            if not np.all(np.isfinite(joints)):
                raise ValueError(f"the leader sent a reading that is not a number: {joints}")
            return joints

        observation = follower.get_observation()
        sent = np.array([float(observation[k]) for k in KEYS])   # what the follower was last told
        if not np.all(np.isfinite(sent)):   # the very first target is the arm's own reading: it must be real too
            raise ValueError(f"the follower sent a reading that is not a number: {sent}")
        smooth = LowPass(read_leader())
        grip, grip_was, trigger_args = None, False, {"rest": TRIGGER["rest"], "squeezed": TRIGGER["squeezed"], "opened": TRIGGER["open"]}
        raw_tips = collections.deque(maxlen=int(WINDOW_S * HZ))
        out_tips = collections.deque(maxlen=int(WINDOW_S * HZ))
        stamps = collections.deque(maxlen=int(WINDOW_S * HZ))
        began = ease_from = time.perf_counter()
        ease_start, was_hold, last, tick_n, elbow_told = sent.copy(), False, began, 0, False
        print(f"Steady Hand running. Dashboard: http://127.0.0.1:8780  Keys: middle = steady on/off, jump = hold, stop = hold.")
        while not state["quit"]:
            now = time.perf_counter()
            if seconds is not None and now - began > seconds:
                break
            dt, last = max(1e-3, now - last), now
            raw = read_leader()   # this can block for a moment, so the keys are read AFTER it, not before
            if shake_deg:  # a pretend tremor on top of the hand, for a demo or a test with a steady hand
                raw = raw + shake_deg * SHAKE_SHARE * np.sin(2 * math.pi * shake_hz * (now - began) + SHAKE_PHASE)
            with lock:
                steady, hold, cutoff, grip_on = state["steady"], state["hold"], state["cutoff"], state["grip_hold"]
                release, state["release"] = state["release"] and not hold, False
            cut = np.array([cutoff] * 5 + [max(cutoff, GRIP_CUTOFF_HZ)])
            filtered = smooth.step(raw, cut, dt)
            if grip is None or (grip_on and not grip_was):
                # starting, or hold mode just switched on: start from the claw's last target (at start-up the
                # follower's own reading), so nothing held is dropped or squeezed harder by switching
                grip = GripHold(closed_to=GRIP_FLOOR, start=float(sent[5]), **trigger_args)
            grip_was = grip_on
            if release:
                grip.release()
            if not hold:   # while held, the target does not change at all: no easing, no stepping
                want = (filtered if steady else raw).copy()
                # always the filtered trigger: a tremor must neither tighten nor release the grip
                want[5] = grip.step(now, filtered[5]) if grip_on else grip.copy(filtered[5])
                if was_hold:  # coming out of a hold: glide back to the hand, do not jump
                    ease_from, ease_start = now, sent.copy()
                share = min(1.0, (now - ease_from) / EASE_S)
                if share < 1.0:
                    want = ease_start + (want - ease_start) * share
                step = np.clip(want - sent, -MAX_SPEED * dt, MAX_SPEED * dt)   # the speed cap
                moved = sent + step
                # never drive the claw hard into its closed stop (see GRIP_FLOOR), and never ask the
                # elbow for more than it can do (see ELBOW_MAX)
                moved[5] = min(100.0, max(GRIP_FLOOR, moved[5]))
                if moved[2] > ELBOW_MAX:
                    moved[2] = ELBOW_MAX
                    if not elbow_told:
                        elbow_told = True
                        print(f"  note: the follower's elbow is at its limit ({ELBOW_MAX:.0f} degrees); it cannot bend as far as the leader")
                with lock:   # a stop that arrived while this was being worked out still wins
                    hold = state["hold"]
                if not hold and np.all(np.isfinite(moved)):   # a target that is not a number is never sent
                    sent = moved
            was_hold = hold
            follower.send_action({k: float(v) for k, v in zip(KEYS, sent)})   # while held: the same target, all six joints

            # the arm's shake is taken from where the follower really IS (its measured joints), not
            # from what it was told: the honest number, since a motor also smooths what it is sent
            observation = follower.get_observation()
            seen = np.array([float(observation[k]) for k in KEYS])
            raw_tip, out_tip = tip.mm(raw), tip.mm(seen)
            raw_tips.append(raw_tip.copy())
            out_tips.append(out_tip.copy())
            stamps.append(now)
            tick_n += 1
            if tick_n % 5 == 0:   # ten times a second: measure, publish, log
                # the real sample rate, from the clock: two serial buses may not keep up with HZ, and
                # a wrong rate would put the tremor at the wrong frequency
                span = stamps[-1] - stamps[0]
                if span >= 1.0:   # under a second of data says nothing about a 4 Hz shake: report none, not a guess
                    rate = (len(stamps) - 1) / span
                    tremor_mm, tremor_hz = band_rms_and_peak(raw_tips, rate)
                    out_mm, _ = band_rms_and_peak(out_tips, rate)
                else:
                    tremor_mm = tremor_hz = out_mm = 0.0
                removed = 0.0 if tremor_mm < 0.15 else max(0.0, min(100.0, 100.0 * (1.0 - out_mm / tremor_mm)))
                loads = follower.bus.sync_read("Present_Load", normalize=False)
                effort = {name: (int(v) & 0x3FF) / 10.0 for name, v in loads.items()}   # percent of the motor's maximum
                speed = float(np.linalg.norm(out_tips[-1] - out_tips[-6]) / (5 * dt)) if len(out_tips) > 6 else 0.0
                with lock:
                    shared.update(t=round(now - began, 2), tremor_mm=round(tremor_mm, 2), tremor_hz=round(tremor_hz, 1),
                                  out_mm=round(out_mm, 2), removed_pct=round(removed), grip_effort=effort.get("gripper", 0.0),
                                  arm_load=round(max(effort.get(j, 0.0) for j in JOINTS[1:4]), 1), speed_mm_s=round(speed),
                                  leader=[round(float(v), 1) for v in raw], follower=[round(float(v), 1) for v in seen],
                                  raw_tip=[round(float(v), 1) for v in raw_tip], smooth_tip=[round(float(v), 1) for v in out_tip],
                                  raw_chain=tip.chain(raw), out_chain=tip.chain(seen),   # the follower as MEASURED, not as told
                                  robot=tip.geoms(seen), hand=tip.geoms(raw))
                    shared["history"] = (shared["history"] + [[round(now - began, 2), round(float(raw_tip[2]), 1),
                                                               round(float(out_tip[2]), 1)]])[-300:]
                    # one point a second for the slower graphs: [seconds, hand shake mm, arm shake mm, grip effort %]
                    if tick_n % 50 == 0:
                        shared["trend"] = (shared.get("trend", []) + [[round(now - began, 1), round(tremor_mm, 2), round(out_mm, 2),
                                                                      effort.get("gripper", 0.0), round(tremor_hz, 1)]])[-600:]
                        shared["insights"] = insights(shared["trend"], hold_test.view(now))
                    done = hold_test.feed(now, tremor_mm)
                    shared["test"] = hold_test.view(now)
                    shared["grip"] = {"hold": grip_on, "squeeze_pct": round(100 * grip.squeeze),
                                      "held_pct": round(100 * max(0.0, grip.held)) if grip_on else 0,
                                      "claw_pct": round(float(seen[5]))}   # measured, not commanded
                session.add(now - began, tremor_mm, tremor_hz, out_mm, steady)
                if done:
                    session.tests.append(done)
                if tick_n % 500 == 0:   # every ten seconds, so a crash loses little
                    save_history()
                log.write(f"{now - began:.2f},{int(steady)},{int(hold)},{tremor_mm:.2f},{tremor_hz:.1f},{out_mm:.2f},"
                          f"{removed:.0f},{effort.get('gripper', 0.0):.1f},{shared['arm_load']:.1f}\n")
                if tick_n % 50 == 0:
                    print(f"  {'STEADY' if steady else 'raw   '}{' HOLD' if hold else '     '}  hand shake {tremor_mm:5.1f} mm at "
                          f"{tremor_hz:4.1f} Hz -> arm {out_mm:5.1f} mm ({removed:3.0f}% removed)  grip {effort.get('gripper', 0):4.1f}%",
                          flush=True)
            time.sleep(max(0.0, 1.0 / HZ - (time.perf_counter() - now)))
        clean = True
    except KeyboardInterrupt:
        clean = True
    finally:
        try:      # whatever goes wrong with the files, the arms are still dealt with below
            log.close()
            save_history()
        finally:
            # The motors are switched off ONLY after a normal stop AND a person at the keyboard saying
            # they have the arm. After a fault, or with --yes (nobody there), they stay on and holding.
            if clean and "--yes" not in sys.argv:
                try:
                    input("Stopping: the follower's motors switch OFF next. Hold it or rest it, then Enter. ")
                    follower.config.disable_torque_on_disconnect = True
                except (EOFError, KeyboardInterrupt):
                    pass
            if not follower.config.disable_torque_on_disconnect:
                print("The follower's motors stay ON and holding. Hold the arm and cut its power, or start steady.py again.", flush=True)
            try:
                leader.disconnect()
            finally:
                follower.disconnect()


if __name__ == "__main__":
    main()
