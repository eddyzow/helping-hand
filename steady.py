"""Steady Hand: the follower copies the leader with the tremor taken out.

    python steady.py                 # teleoperate; the two arms are lined up from their calibration files
    python steady.py --teleop-offset # use the old eye-measured line-up in poses/teleop_offset.json instead
    python steady.py --measure       # redo that eye-measured line-up (and use it)
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
from core.tremor import (ARM, CUTOFF_HZ, GRIP_CUTOFF_HZ, TRIGGER, Calibration, Fingertip, GripHold, HoldStillTest, LowPass,
                         Notch, Session, activities, band_rms_and_peak, insights)

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
# the follower's elbow, degrees. Its range was widened (EEPROM and calibration, 14 Nov: 252..3000 ticks, same middle
# 1626, so stored poses keep their meaning) to about +120.8 at the top. Kept inside that at +118; at the bottom -64,
# because the lower stop was only ever swept to -64.9 and nothing below has been seen working. Folded at rest the
# elbow reads past +118 (3088 ticks): it is then brought inside at the speed cap, never jumped (see the loop).
# The follower's wrist-roll motor is faulty (measured 14 Nov): holding a 7-tick error it draws about 86 units of
# current where the wrist-bend motor draws 1, reaches 68 C within a minute (its cut-out is 70 C) and then garbles
# its replies. Until that motor is replaced the wrist roll does not follow the hand. "--roll" turns it back on.
ROLL_FOLLOWS = "--roll" in sys.argv
LINK_WAIT_S = 20.0   # how long to wait for an arm that stopped answering before giving up
TORQUE_LIMIT = 600 # of 1000: the most each arm joint may push. Lower = gentler and safer; too low and the arm sags
ELBOW_MAX = 118.0
ELBOW_MIN = -64.0
TABLE_Z = -2.4           # mm, the table top in the model's frame: the underside of the base in the model, where it
                         # stands on the table (from the 3D lane; touch readings on the real arm ranged -9 to -27)
# --shake HZ DEG adds a pretend tremor; like a real one it is not the same size or in step on every joint
SHAKE_SHARE = np.array([0.6, 0.5, 0.7, 1.0, 0.8, 0.0])
SHAKE_PHASE = np.array([0.0, 1.3, 2.1, 0.4, 2.9, 0.0])

# the follower's own reach per arm joint (shoulder turn, shoulder lift, elbow, wrist bend, wrist roll), degrees
LIMIT_LOW = np.array([-110.0, -100.0, ELBOW_MIN, -95.0, -150.0])
LIMIT_HIGH = np.array([110.0, 100.0, ELBOW_MAX, 95.0, 150.0])
TICK_DEG = 360.0 / 4095   # one step of the motors' position reading, in degrees
USERS = HERE / "poses" / "steady_users.json"
STILL_WORDS = {"holding": "  ARM STILL: hold is on (say 'steady on' or press the jump key)",
               "calibrating": "  ARM STILL: calibrating", "easing": "  arm gliding to the hand",
               "limit": "  ARM STILL: at the follower's joint limit"}

# re_ease: glide to the new target (gain, neutral or user changed); neutral: take the hand's pose now as neutral
state = {"steady": True, "hold": False, "cutoff": CUTOFF_HZ, "quit": False, "grip_hold": True, "release": False,
         "gain": 1.0, "user": "default", "re_ease": False, "neutral": False}
shared = {"t": 0.0, "tremor_mm": 0.0, "tremor_hz": 0.0, "out_mm": 0.0, "removed_pct": 0.0, "grip_effort": 0.0,
          "arm_load": 0.0, "speed_mm_s": 0.0, "leader": [0.0] * 6, "follower": [0.0] * 6, "raw_tip": [0.0] * 3,
          "smooth_tip": [0.0] * 3, "history": [], "raw_chain": [], "out_chain": [], "robot": [], "hand": [], "table_z": TABLE_Z,
          "test": {"running": False, "seconds_left": 0, "score": None, "tremor_mm": None},
          "why_still": "", "limits": [], "grip": {"hold": True, "squeeze_pct": 0, "held_pct": 0, "claw_pct": 0}, "activities": []}
lock = threading.Lock()
hold_test = HoldStillTest()
calibration = Calibration()


def default_profile():
    return {"calibrated": False, "gains": [1.0] * 5, "range_deg": [0.0] * 5, "trigger": dict(TRIGGER), "neutral": None,
            "calibrations": 0, "best_range": None}


users = {"default": default_profile()}


def valid_name(name):
    return 0 < len(name) <= 24 and all(c.isalnum() or c in " -" for c in name)


def clean_profile(saved):
    """A profile read from the file, checked before it can move the arm. Raises ValueError (or TypeError)
    if anything is missing, not a finite number or out of range: such a profile is not used at all."""
    def numbers(values, count, low, high):
        values = [float(v) for v in values]
        if len(values) != count or not all(math.isfinite(v) and low <= v <= high for v in values):
            raise ValueError(f"not {count} numbers in {low}..{high}: {values}")
        return values
    profile = default_profile()
    if not isinstance(saved.get("calibrated"), bool):
        raise ValueError("calibrated must be true or false")
    profile["calibrated"] = saved["calibrated"]
    profile["gains"] = numbers(saved["gains"], 5, 1.0, 3.0)
    profile["range_deg"] = numbers(saved["range_deg"], 5, 0.0, 360.0)
    rest, squeezed, opened = numbers([saved["trigger"][k] for k in ("rest", "squeezed", "open")], 3, 0.0, 100.0)
    if not squeezed < rest < opened:   # reversed or equal ends would turn a squeeze into an opening
        raise ValueError(f"trigger must be squeezed < rest < open: {squeezed}, {rest}, {opened}")
    profile["trigger"] = {"rest": rest, "squeezed": squeezed, "open": opened}
    if saved.get("neutral") is not None:
        profile["neutral"] = numbers(saved["neutral"], 5, -360.0, 360.0)
    profile["calibrations"] = int(numbers([saved.get("calibrations", 0)], 1, 0, 1e6)[0])
    if saved.get("best_range") is not None:
        profile["best_range"] = numbers([saved["best_range"]], 1, 0.0, 360.0)[0]
    return profile


def load_users(path=None):
    """The saved user profiles, with `default` always there. A profile that fails its checks is left out;
    a file that is not readable JSON is set aside as .bad (so a later save cannot overwrite it) and only
    `default` is used. Never raises: this runs before the arm moves, and a bad file must not stop it."""
    path = path or USERS
    loaded = {"default": default_profile()}
    try:
        saved = json.loads(path.read_text())
        if not isinstance(saved, dict):
            raise ValueError("not a JSON object")
    except FileNotFoundError:
        return loaded
    except OSError as error:   # could not read it: leave it exactly where it is
        print(f"  {path} could not be read ({error}); using the default user", flush=True)
        return loaded
    except ValueError as error:   # read, but not usable: keep it aside rather than lose it to the next save
        print(f"  {path} is not valid ({error}); kept as {path.with_suffix('.bad').name}, using the default user", flush=True)
        try:
            os.replace(path, path.with_suffix(".bad"))
        except OSError:
            pass
        return loaded
    for name, profile in saved.items():
        try:
            if name != "default" and valid_name(name):
                loaded[name] = clean_profile(profile)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            print(f"  user profile {name!r} left out: {error}", flush=True)
    return loaded


def save_users(profiles, path=None):
    """Write through a temp file, so a crash mid-write never leaves half a file. Raises OSError."""
    path = path or USERS
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({k: v for k, v in profiles.items() if k != "default"}, indent=1))
    os.replace(temp, path)


def user_view():
    profile = users[state["user"]]
    return {"name": state["user"], "names": sorted(users), "calibrated": profile["calibrated"], "gains": profile["gains"],
            "range_deg": profile["range_deg"], "trigger": profile["trigger"]}


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


def calibration_offset(leader_cal, follower_cal):
    """Degrees to add to a leader reading to get the follower's reading for the same physical pose.

    LeRobot measures each joint's degrees from the middle of that arm's calibrated range, (range_min +
    range_max) / 2, and the two arms' middles differ. So follower = leader + (mid_leader - mid_follower)
    * 360 / 4095 on the five arm joints. The claw is 0..100 on both arms and gets 0 (the grip maps the
    trigger with its own calibration). leader_cal, follower_cal: {joint name: object with range_min,
    range_max}, as in bus.calibration. Raises ValueError if a joint is missing or not a number."""
    try:
        mid = lambda cal, joint: (float(cal[joint].range_min) + float(cal[joint].range_max)) / 2
        offset = np.array([(mid(leader_cal, j) - mid(follower_cal, j)) * TICK_DEG for j in JOINTS[:5]] + [0.0])
    except (KeyError, AttributeError, TypeError) as error:
        raise ValueError(f"an arm's calibration is missing a joint's range: {error!r}") from error
    if not np.all(np.isfinite(offset)):
        raise ValueError(f"an arm's calibration holds a range that is not a number: {offset}")
    return offset


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
            if state["hold"] or calibration.running():   # a held arm does not move, the claw included
                return {"ok": False, "reason": "the arm is held; say 'steady on' first, then 'let go'"}
            state["release"] = True
        # gain, neutral, user and calibration never touch hold: a held arm stays held, and a change while
        # following glides to the new target (re_ease) instead of jumping
        elif word == "gain":
            try:
                gain = float(rest)
            except ValueError:
                gain = math.nan
            if not math.isfinite(gain):
                return {"ok": False, "reason": "gain needs a number, 1.0 to 3.0"}
            state["gain"], state["re_ease"] = min(3.0, max(1.0, gain)), True
        elif line == "neutral":
            state["neutral"] = state["re_ease"] = True
        elif word == "user":
            if not valid_name(rest):
                return {"ok": False, "reason": "a user name is letters, digits, spaces and dashes, up to 24 characters"}
            if rest not in users:
                users[rest] = default_profile()
                try:
                    save_users(users)
                except OSError as error:   # the profile still works for this run; it is just not on disk yet
                    print(f"  could not write {USERS}: {error}", flush=True)
            calibration.cancel()   # a calibration belongs to the user who started it
            state["user"], state["re_ease"] = rest, True
        elif line == "calibrate":
            if state["user"] == "default":   # default is the fixed fallback (gain 1.0, trigger 43 / 0 / 100)
                return {"ok": False, "reason": "choose a user first: user <name>"}
            calibration.start(time.perf_counter())
        elif line == "calibrate cancel":
            if calibration.running():
                calibration.cancel()
                state["re_ease"] = True
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
            return {"ok": False, "reason": "commands: steady on|off, filter on|off, hold on|off, cutoff <Hz>, gain <x>, neutral, "
                                           "grip hold on|off, grip release, user <name>, calibrate, calibrate cancel, test, status, quit"}
        return {"ok": True, **{k: state[k] for k in ("steady", "hold", "cutoff", "grip_hold", "gain", "user")}, "latch": state["grip_hold"]}


STATIC = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
          ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}


class Dashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/cmd?"):   # the dashboard's buttons: /cmd?steady%20off
            from urllib.parse import unquote
            body, kind = json.dumps(command(unquote(self.path[5:]))).encode(), "application/json"
        elif self.path.startswith("/state"):
            with lock:
                body = json.dumps({**{k: state[k] for k in ("steady", "hold", "cutoff", "gain")}, **shared, "user": user_view(),
                                   "calibration": calibration.view(time.perf_counter())}).encode()
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
        if not self.path.startswith("/meshes/"):   # a browser kept showing the old page after the redesign
            self.send_header("Cache-Control", "no-store")
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
    with lock:   # the saved users, checked, before anything can move
        users.clear()
        users.update(load_users())
        state["user"] = state["user"] if state["user"] in users else "default"
    by_eye = "--teleop-offset" in sys.argv or "--measure" in sys.argv
    measure = "--measure" in sys.argv or (by_eye and not OFFSETS.exists())
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
    # one garbled serial reply must not end the session (it did, on the first real run of v2: "motor 5:
    # Parsing error"): every read retries. A read that still fails stops the loop, motors holding.
    for bus in (b for b in (leader.bus, follower.bus) if hasattr(b, "sync_read")):
        bus.sync_read = (lambda read: lambda *a, **k: read(*a, **{**k, "num_retry": 12}))(bus.sync_read)
        # 12, whatever the caller asks: measured 14 Nov, the follower's wrist roll garbles about 3 replies in 10
        # while the whole arm is powered (none with the motors off), so 3 tries still failed within a second
    # the arm pushes gently: a joint that meets the table or a person gives way instead of stalling at full
    # current (a stall on several joints cut the supply and reset every motor: "motor 1: Operation timed out",
    # 14 Nov). A setting in the motors' memory until power-off, not their stored configuration.
    if hasattr(follower.bus, "sync_write"):
        follower.bus.sync_write("Torque_Limit", {j: TORQUE_LIMIT for j in JOINTS[:5]}, normalize=False, num_retry=5)
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
        if by_eye:
            offset = np.array([float(json.loads(OFFSETS.read_text())[k]) for k in KEYS])
        else:
            offset = calibration_offset(leader.bus.calibration, follower.bus.calibration)
        if not np.all(np.isfinite(offset)):   # checked before anything is sent to the arm
            raise ValueError(f"the line-up offset holds a value that is not a number: {offset}")

        def read_leader():
            """The leader's six joints in the follower's terms. Raises if any is not a finite number:
            a bad reading must never become a command."""
            action = leader.get_action()
            joints = np.array([float(action[k]) for k in KEYS]) + offset
            if not np.all(np.isfinite(joints)):
                raise ValueError(f"the leader sent a reading that is not a number: {joints}")
            return joints

        link = {"lost": False}

        def patient(call, *args):
            """An arm that stops answering (a plug knocked, a power dip: both happened on 14 Nov the moment
            the leader was picked up) does not end the session. Nothing is sent meanwhile; the call is
            tried again for LINK_WAIT_S, and the loop then lines everything up again before it moves."""
            deadline = time.perf_counter() + LINK_WAIT_S   # on the clock, so slow failing calls count too
            while True:
                try:
                    return call(*args)
                except ConnectionError as error:
                    if state["quit"] or time.perf_counter() >= deadline:
                        raise
                    if not link["lost"]:
                        print(f"  an arm stopped answering ({str(error)[-60:]}); waiting for it, nothing is being sent", flush=True)
                    link["lost"] = True
                    with lock:
                        shared["why_still"] = "link"
                    time.sleep(0.25)

        observation = follower.get_observation()
        sent = np.array([float(observation[k]) for k in KEYS])   # what the follower was last told
        if not np.all(np.isfinite(sent)):   # the very first target is the arm's own reading: it must be real too
            raise ValueError(f"the follower sent a reading that is not a number: {sent}")
        roll_seen = float(sent[4])
        smooth, notch = LowPass(read_leader()), Notch()
        grip, grip_was, trigger_args = None, False, {}
        neutral, active_user = None, None   # neutral: the pose scaling works about; None until the start-up glide ends
        steady_s, grip_since, grip_longest, grips, why, limits = 0.0, None, 0.0, 0, "", []
        raw_tips = collections.deque(maxlen=int(WINDOW_S * HZ))
        out_tips = collections.deque(maxlen=int(WINDOW_S * HZ))
        stamps = collections.deque(maxlen=int(WINDOW_S * HZ))
        began = ease_from = time.perf_counter()
        ease_start, was_frozen, last, tick_n, elbow_told = sent.copy(), False, began, 0, False
        print(f"Steady Hand running. Dashboard: http://127.0.0.1:8780  Keys: middle = steady on/off, jump = hold, stop = hold.")
        if not ROLL_FOLLOWS:
            print("  note: the wrist roll does NOT follow the hand and is not held at a fixed target (motor reported faulty).", flush=True)
        shared["roll_follows"] = ROLL_FOLLOWS
        while not state["quit"]:
            now = time.perf_counter()
            if seconds is not None and now - began > seconds:
                break
            if link["lost"]:   # an arm went quiet and is back: start again from where the follower really is
                # Only reads are waited for here; no command is replayed, and a hold or stop given meanwhile stands.
                observation = patient(follower.get_observation)
                here = np.array([float(observation[k]) for k in KEYS])
                restarted = (hasattr(follower.bus, "sync_read") and
                             not all(patient(lambda: follower.bus.sync_read("Torque_Enable", normalize=False)).values()))
                if restarted:
                    # a power dip restarted the motors limp: where the arm was told to be is no longer where
                    # it is. It is powered again where it now lies and HELD; a person must say continue.
                    if not np.all(np.isfinite(here)):
                        raise ValueError(f"the follower sent a reading that is not a number: {here}")
                    sent = here
                    follower.send_action({k: float(v) for k, v in zip(KEYS, sent)})
                    follower.bus.enable_torque()
                    follower.bus.sync_write("Torque_Limit", {j: TORQUE_LIMIT for j in JOINTS[:5]}, normalize=False)
                    with lock:
                        state["hold"] = True
                    grip = None
                    print("  the follower's motors had restarted: the arm is HELD where it lies. Hold off (or Continue) to follow.", flush=True)
                else:   # the targets stand as they were; a held arm keeps exactly its held targets
                    print("  the arms answer again", flush=True)
                smooth, notch = LowPass(patient(read_leader)), Notch()
                link["lost"], state["re_ease"], now = False, True, time.perf_counter()
                last = now - 1.0 / HZ   # the wait is not a time step: the speed cap must not open up
            dt, last = max(1e-3, now - last), now
            raw = patient(read_leader)   # this can block for a moment, so the keys are read AFTER it, not before
            if shake_deg:  # a pretend tremor on top of the hand, for a demo or a test with a steady hand
                raw = raw + shake_deg * SHAKE_SHARE * np.sin(2 * math.pi * shake_hz * (now - began) + SHAKE_PHASE)
            with lock:
                steady, hold, cutoff, grip_on, gain = state["steady"], state["hold"], state["cutoff"], state["grip_hold"], state["gain"]
                release, state["release"] = state["release"] and not hold, False
                redo, state["re_ease"] = state["re_ease"], False
                capture, state["neutral"] = state["neutral"], False
                user_now, profile = state["user"], users[state["user"]]
            if notch.hz is not None and notch.hz * dt >= 0.225:   # a loop too slow for the notch: the low-pass
                cutoff = min(cutoff, 2.0)                         # alone must do the work, at the old 2 Hz
            cut = np.array([cutoff] * 5 + [max(cutoff, GRIP_CUTOFF_HZ)])
            # the notch (a pass-through until a shake is measured) works on the five arm joints only: its step
            # response overshoots a little, and the trigger must never read deeper than the hand squeezed
            filtered = smooth.step(np.append(notch.step(raw[:5], dt), raw[5]), cut, dt)
            with lock:   # the calibration watches the filtered hand; the arm is held while it runs
                calibrating = calibration.running()
                result = calibration.feed(now, filtered, filtered[5]) if calibrating else None
                if result:
                    profile.update(result, calibrations=profile["calibrations"] + 1,
                                   best_range=round(max(float(np.mean(result["range_deg"])), profile["best_range"] or 0.0), 1))
                    active_user = None   # take up the new neutral and trigger below
                    try:
                        save_users(users)
                    except OSError as error:   # the calibration still applies for this run
                        print(f"  could not write {USERS}: {error}", flush=True)
            if user_now != active_user:   # started, switched user, or calibrated: that user's neutral and trigger
                active_user = user_now
                if profile["calibrated"] and profile["neutral"] is not None:
                    neutral = np.array(profile["neutral"], float)
                trigger_args = {"rest": profile["trigger"]["rest"], "squeezed": profile["trigger"]["squeezed"],
                                "opened": profile["trigger"]["open"]}
                grip = None
            if capture:
                neutral = filtered[:5].copy()
            if grip is None or (grip_on and not grip_was):
                # starting, or hold mode just switched on: start from the claw's last target (at start-up the
                # follower's own reading), so nothing held is dropped or squeezed harder by switching
                grip = GripHold(closed_to=GRIP_FLOOR, start=float(sent[5]), **trigger_args)
            grip_was = grip_on
            if release:
                grip.release()
            frozen = hold or calibrating
            if not frozen:   # while held, the target does not change at all: no easing, no stepping
                want = (filtered if steady else raw).copy()
                if neutral is not None:   # motion scaling about the neutral pose, after the filter
                    want[:5] = neutral + gain * np.array(profile["gains"]) * (want[:5] - neutral)
                asked = want[:5].copy()
                want[:5] = np.clip(asked, LIMIT_LOW, LIMIT_HIGH)   # the follower's own reach, whatever the gain
                limits = [ARM[j] for j in range(5) if asked[j] != want[j]]
                if "elbow_flex" in limits and not elbow_told:
                    elbow_told = True
                    print(f"  note: the follower's elbow is at its limit ({ELBOW_MIN:.0f} .. {ELBOW_MAX:.0f} degrees); "
                          "it cannot bend as far as the leader asks")
                # always the filtered trigger: a tremor must neither tighten nor release the grip
                want[5] = grip.step(now, filtered[5]) if grip_on else grip.copy(filtered[5])
                if was_frozen or redo:  # out of a hold, or gain / neutral / user changed: glide, do not jump
                    ease_from, ease_start = now, sent.copy()
                share = min(1.0, (now - ease_from) / EASE_S)
                if share < 1.0:
                    want = ease_start + (want - ease_start) * share
                elif neutral is None:   # the start-up glide is over: the pose now is the default neutral
                    neutral = filtered[:5].copy()
                step = np.clip(want - sent, -MAX_SPEED * dt, MAX_SPEED * dt)   # the speed cap
                moved = sent + step
                # never drive the claw hard into its closed stop (see GRIP_FLOOR), and never take a joint
                # past its limit (the elbow: ELBOW_MIN, ELBOW_MAX). A joint found already past one (the elbow
                # folded at rest reads above ELBOW_MAX) is only ever moved back inside, at the speed cap: a
                # hard clamp would jump it there in one command.
                moved[5] = min(100.0, max(GRIP_FLOOR, moved[5]))
                moved[:5] = np.clip(moved[:5], np.minimum(LIMIT_LOW, sent[:5]), np.maximum(LIMIT_HIGH, sent[:5]))
                with lock:   # a stop (or a calibration) that arrived while this was being worked out still wins
                    frozen = state["hold"] or calibration.running()
                if not frozen and np.all(np.isfinite(moved)):   # a target that is not a number is never sent
                    sent = moved
                pulling = [j for j in range(5) if abs(asked[j] - sent[j]) > 1.0]   # joints the hand wants moved further
                why = "easing" if share < 1.0 else "limit" if pulling and all(ARM[j] in limits for j in pulling) else ""
            with lock:
                hold = state["hold"]
            if frozen:
                why = "holding" if hold else "calibrating"
            was_frozen = frozen
            if steady:
                steady_s += dt
            if grip_on and grip.from_hand and grip.held >= 0.1:   # a grip the person made, kept by grip hold
                if grip_since is None:
                    grip_since, grips = now, grips + 1
                grip_longest = max(grip_longest, now - grip_since)
            else:
                grip_since = None
            order = {k: float(v) for k, v in zip(KEYS, sent)}   # while held: the same target, all six joints
            if not ROLL_FOLLOWS:   # the wrist roll is told to be where it was last measured, so it is asked for no movement
                order[KEYS[4]] = roll_seen
            try:
                follower.send_action(order)
            except ConnectionError as error:   # a command that failed is dropped, never sent again later
                print(f"  the follower stopped answering ({str(error)[-60:]}); nothing is being sent", flush=True)
                link["lost"] = True
                with lock:
                    shared["why_still"] = "link"
                continue

            # the arm's shake is taken from where the follower really IS (its measured joints), not
            # from what it was told: the honest number, since a motor also smooths what it is sent
            observation = patient(follower.get_observation)
            if link["lost"]:
                continue
            seen = np.array([float(observation[k]) for k in KEYS])
            roll_seen = float(seen[4]) if math.isfinite(seen[4]) else roll_seen
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
                notch.track(tremor_mm, tremor_hz)   # the hand's own shake, measured before any filter
                removed = 0.0 if tremor_mm < 0.15 else max(0.0, min(100.0, 100.0 * (1.0 - out_mm / tremor_mm)))
                try:
                    loads = follower.bus.sync_read("Present_Load", normalize=False)
                except ConnectionError:   # a reading for the page only: keep the last one, keep following
                    loads = {name: v * 10 for name, v in effort.items()} if "effort" in dir() else {}
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
                    shared.update(why_still=why, limits=list(limits))
                    if tick_n % 50 == 0:
                        shared["activities"] = activities(session.tests, past, profile, steady_s, grip_longest, grips)
                session.add(now - began, tremor_mm, tremor_hz, out_mm, steady)
                if done:
                    session.tests.append(done)
                if tick_n % 500 == 0:   # every ten seconds, so a crash loses little
                    save_history()
                log.write(f"{now - began:.2f},{int(steady)},{int(hold)},{tremor_mm:.2f},{tremor_hz:.1f},{out_mm:.2f},"
                          f"{removed:.0f},{effort.get('gripper', 0.0):.1f},{shared['arm_load']:.1f}\n")
                if tick_n % 50 == 0:
                    print(f"  {'STEADY' if steady else 'raw   '}{' HOLD' if hold else '     '}  hand shake {tremor_mm:5.1f} mm at "
                          f"{tremor_hz:4.1f} Hz -> arm {out_mm:5.1f} mm ({removed:3.0f}% removed)  grip {effort.get('gripper', 0):4.1f}%"
                          f"{STILL_WORDS.get(why, '')}", flush=True)   # the first real test: the arm "died" and nothing said why
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
