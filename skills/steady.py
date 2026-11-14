"""Steady hand: a person steers the follower by moving the leader arm, and the shake of their hand
is taken out on the way. For someone with a tremor: the hand shakes, the arm does not.

    run steady                                  # 60 seconds, shake filtered out
    run steady {"filter": false}                # the same without the filter, to show the difference
    run steady {"shake_hz": 5, "shake_deg": 3}  # adds a pretend tremor to a steady hand, for a demo
    python -m skills.steady                     # self-check on a fake arm and a fake leader, no hardware

How it works. A tremor is fast (about 4 to 12 back-and-forths a second); reaching for something is
slow (under 2). Each joint of the leader goes through a low-pass filter that keeps the slow part.
Then a small hold band keeps the follower perfectly still while the hand only trembles in place,
and a speed limit caps how fast any joint is asked to move while following. The moves before and
after (to home, and the glide out to the leader) are asked for at 40 degrees a second or max_dps,
whichever is lower. These are the speeds commanded, not speeds measured on an arm. The gripper is
filtered the same way.
What it costs: the follower trails the hand by about 2 / (6.28 * cutoff_hz) seconds, 0.2 s at the
default. A lower cutoff_hz removes more shake and trails more.

The leader's motors stay switched off so a hand can move it. Nothing steadies the person's own
hand: the shake is removed from what the follower does.

The two real arms do not share a zero: poses/teleop_offset.json holds follower minus leader for each
joint (written by `steady.py --measure` on daniel/arm-core) and is added to every leader reading. On
the real arm the skill refuses to start without it.

NEVER RUN ON HARDWARE. Written on the mock arm. Not in here yet, and needed on the real follower
(both are in Daniel's standalone steady.py): its elbow stops at about 64 degrees, and its claw
overheats if it is told to squeeze far past where the jaws meet. Before the first real run, with Daniel:
  - the leader on its 5 V supply and its own USB port (LEADER_PORT, default /dev/ttyACM0), attached
    to the machine the dispatcher runs on. This skill opens the leader; the dispatcher keeps the follower.
  - hold the leader up in a clear pose before starting: the follower leaves home and glides to
    wherever the leader is, then follows it. Someone stays on the stop key.
  - stop holds the follower where it is and never moves it. When the time runs out it goes home,
    so put down whatever it is holding first.
It trusts root arm.py's leader() and the leader's get_action(), the same calls `arm.py record` makes.
"""
import json
import math
import os
import time
from pathlib import Path

import core.arm
from core.arm import HZ, JOINTS

NAME = "steady"
DESCRIPTION = "A person steers the arm by hand with the leader arm; the shake of a trembling hand is filtered out"
PARAMS = {"seconds": "float: how long to follow the leader, 1 to 600 (default 60)",
          "filter": "bool: false sends the hand's motion unfiltered, to compare",
          "cutoff_hz": "float: motion slower than this is kept, 0.3 to 5 (default 1.5)",
          "hold_deg": "float: the arm stays still until the hand moves this far, 0 to 3 (default 0.3)",
          "max_dps": "float: fastest any joint may be sent, degrees a second, 10 to 240 (default 120)",
          "shake_hz": "float: add a pretend tremor at this rate, 2 to 12 (needs shake_deg)",
          "shake_deg": "float: size of the pretend tremor, up to 5 (needs shake_hz)"}

DEFAULTS = {"seconds": 60.0, "filter": True, "cutoff_hz": 1.5, "hold_deg": 0.3, "max_dps": 120.0,
            "shake_hz": 0.0, "shake_deg": 0.0}
LIMITS = {"seconds": (1, 600), "cutoff_hz": (0.3, 5), "hold_deg": (0, 3), "max_dps": (10, 240),
          "shake_hz": (2, 12), "shake_deg": (0, 5)}
GRIPPER = JOINTS.index("gripper")
GLIDE_DPS = 40.0   # speed asked for on the way home, on the glide out to the leader, and while catching up with it
LONGEST_MOVE_S = 30.0  # the arm API's own limit on one move
STOPPED = {"ok": False, "reason": "stopped"}
TRACE = Path(__file__).parent.parent / "outputs" / "steady_last.json"
# the pretend tremor is not the same size or in step on every joint, as a real one is not
SHAKE = [(0.6, 0.0), (0.5, 1.3), (0.7, 2.1), (1.0, 0.4), (0.8, 2.9)]  # (share, phase) for the five arm joints

clock = time.perf_counter  # the self-check swaps this for a fake clock


class Smoother:
    """Two one-pole low-pass filters in a row on each joint. It cannot overshoot and it is stable
    for any time step, which matters because the loop does not tick perfectly evenly."""

    def __init__(self, start: list[float], cutoff_hz: float):
        self.first, self.second, self.rate = list(start), list(start), 2 * math.pi * cutoff_hz

    def step(self, raw: list[float], dt: float) -> list[float]:
        k = 1 - math.exp(-self.rate * dt)
        self.first = [a + k * (r - a) for a, r in zip(self.first, raw)]
        self.second = [b + k * (a - b) for b, a in zip(self.second, self.first)]
        return list(self.second)


def hold(still: float, wanted: float, band: float) -> float:
    """Stay put until `wanted` is more than `band` away, then follow at that distance."""
    return wanted - band if wanted > still + band else wanted + band if wanted < still - band else still


class Swings:
    """Counts one joint's back-and-forth swings, to report how big and how fast the shake was.
    A swing counts once the joint has turned back by more than `least` from its furthest point."""

    def __init__(self, start: float, least: float = 0.3):
        self.far, self.turn, self.way, self.least, self.sizes = start, start, 0, least, []

    def add(self, value: float) -> None:
        if self.way >= 0 and value > self.far or self.way <= 0 and value < self.far:
            self.way = self.way or (1 if value > self.far else -1)
            self.far = value
        elif abs(value - self.far) > self.least:  # it has turned round
            self.sizes.append(abs(self.far - self.turn))
            self.turn, self.far, self.way = self.far, value, -self.way


def options(params: dict) -> dict:
    """The settings, checked. Raises ValueError before anything is connected or moved."""
    opts = {**DEFAULTS, **params}
    if type(opts["filter"]) is not bool:
        raise ValueError("filter must be true or false")
    shaking = bool(opts["shake_hz"] or opts["shake_deg"])
    for name, (low, high) in LIMITS.items():
        value = opts[name]
        if name.startswith("shake") and not shaking:
            continue
        if type(value) not in (int, float) or not low <= value <= high:  # NaN fails the comparison
            raise ValueError(f"{name} must be {low} to {high}")
    if shaking and not opts["shake_deg"] > 0:
        raise ValueError("shake_hz and shake_deg go together: give both, or neither")
    return opts


def offsets(arm) -> list[float]:
    """Follower minus leader for each joint, from poses/teleop_offset.json. Raises ValueError before
    anything is opened or moved. The mock arm needs no file; the real arm must have one."""
    path = core.arm.POSES / "teleop_offset.json"
    if not path.exists():
        if arm.REAL:
            raise ValueError(f"no {path.name} in poses/: the two arms' zero points differ, so measure the offset first")
        return [0.0] * 6
    try:
        saved = json.loads(path.read_text())
        values = [_number(saved[f"{name}.pos"]) for name in JOINTS]
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise ValueError(f"{path.name} is not six finite numbers, one per joint ({type(err).__name__}: {err})") from None
    if any(abs(v) > 180 for v in values):
        raise ValueError(f"{path.name} holds an offset over 180; measure it again")
    return values


def _same_device(a: str, b: str) -> bool:
    """COM3 and com3, or two names for one /dev entry, are the same port."""
    return os.path.realpath(a).casefold() == os.path.realpath(b).casefold() or a.strip().casefold() == b.strip().casefold()


def open_leader(arm):
    """The real leader arm, or a pretend one beside the mock arm. Opening it moves nothing: the
    leader's motors stay off so a hand can move it. That is also why the port must not be the
    follower's: setting up a leader switches the motors on that port off."""
    if not arm.REAL:
        return PretendLeader(arm.load_pose("home"))
    import arm as root_arm  # the root arm.py

    if _same_device(root_arm.LEADER_PORT, root_arm.FOLLOWER_PORT):
        raise ValueError(f"LEADER_PORT and FOLLOWER_PORT are both {root_arm.FOLLOWER_PORT}; the leader needs its own port")
    return root_arm.leader()


def read(teleop, offset=(0.0,) * 6) -> list[float]:
    """The leader's six joints in the follower's terms, in JOINTS order. Raises if any is missing or
    not a finite number."""
    action = teleop.get_action()
    return [_number(action[f"{name}.pos"]) + shift for name, shift in zip(JOINTS, offset)]


def _number(value) -> float:
    """A plain or numpy number as a float. True, text, None, NaN and infinity are refused."""
    numpy_kind = getattr(getattr(value, "dtype", None), "kind", None)
    if type(value) in (int, float) or numpy_kind in ("f", "i", "u"):
        value = float(value)
        if math.isfinite(value):
            return value
    raise ValueError(f"bad reading {value!r}")


def run(arm, params, stop):
    try:
        opts = options(params)
        opts["offset"] = offsets(arm)
    except ValueError as err:
        return {"ok": False, "reason": str(err)}
    try:
        teleop = open_leader(arm)
    except Exception as err:  # no leader, wrong port, not calibrated: nothing has moved
        return {"ok": False, "reason": f"could not open the leader arm: {type(err).__name__}: {err}"}
    try:
        return _follow(arm, teleop, opts, stop)
    finally:
        try:
            teleop.disconnect()
        except Exception as err:
            print(f"[steady] leader did not disconnect cleanly: {err}", flush=True)


def _follow(arm, teleop, opts, stop):
    def leader_now():
        """A reading, or None after saying why. A leader that stops answering must not move the arm."""
        try:
            return read(teleop, opts["offset"])
        except Exception as err:
            print(f"[steady] leader arm: {type(err).__name__}: {err}", flush=True)
            return None

    lost = {"ok": False, "reason": "the leader arm stopped giving good readings; the arm is holding where it is"}
    gentle = min(GLIDE_DPS, opts["max_dps"])  # the speed asked for on every move that is not following

    def seconds_for(target: list[float], least: float):
        """How long a move from where the arm is to `target` must take to stay under `gentle`, or
        None if that is longer than one move may last."""
        far = max(abs(a - b) for a, b in zip(target, arm.get_joints()))
        if far / gentle > LONGEST_MOVE_S:
            return None
        # a move is made of whole ticks, and the arm rounds its count down: round up here, or a move
        # of 112.5 ticks would be made in 112 and come out a little faster than asked
        return min(LONGEST_MOVE_S, (math.ceil(max(least, far / gentle) * HZ) + 0.5) / HZ)

    first = leader_now()
    if first is None:  # before any motion
        return {"ok": False, "reason": "the leader arm gave no good reading; nothing moved"}
    home = arm.load_pose("home")
    to_home = seconds_for(home, 2.0)
    out = max(abs(a - b) for a, b in zip(first, home)) / gentle
    if to_home is None or out > LONGEST_MOVE_S:  # refuse before moving, not half-way
        return {"ok": False, "reason": f"too far to move at {gentle:g} degrees a second in {LONGEST_MOVE_S:g} s; "
                                       "bring the leader nearer the home pose or raise max_dps. Nothing moved"}
    if not arm.move_joints(home, to_home):
        return STOPPED
    sent = leader_now()  # where the hand is now: glide there, slowly, before following it
    if sent is None:
        return lost
    sent[GRIPPER] = min(max(sent[GRIPPER], 0.0), 100.0)
    glide = seconds_for(sent, 1.0)
    if glide is None:
        return {"ok": False, "reason": "the leader moved too far from home to glide there; the arm is at home"}
    if not arm.move_joints(sent, glide):
        return STOPPED

    raw = leader_now()
    if raw is None:
        return lost
    smoother, still = Smoother(raw, opts["cutoff_hz"]), list(sent)
    hand, arm_path = [0.0] * 6, [0.0] * 6            # how far each joint travelled: the hand, and what was sent
    swings = [Swings(v) for v in raw]
    trace, before, caught_up = [], raw, False
    began = clock()

    def report() -> str:
        return ("" if opts["filter"] else "Filter off, for comparison. ") + _report(hand, arm_path, swings, clock() - began)

    last = began - 1 / HZ
    print(f"[steady] following the leader for {opts['seconds']:.0f} s, "
          f"{'shake filtered out' if opts['filter'] else 'NOT filtered'}. Stop key holds the arm.", flush=True)
    while (now := clock()) - began < opts["seconds"]:
        dt = min(max(now - last, 0.001), 0.1)  # a stalled loop must not turn into one big step
        last = now
        raw = leader_now()
        if raw is None:
            _save(trace)  # this run's trace, so the file never describes an earlier run
            return {**lost, "report": report()}
        if opts["shake_deg"]:
            for joint, (share, phase) in enumerate(SHAKE):
                raw[joint] += opts["shake_deg"] * share * math.sin(2 * math.pi * opts["shake_hz"] * (now - began) + phase)
        smooth = smoother.step(raw, dt)  # always worked out, so the report can say what the filter would remove
        if opts["filter"]:
            still = [hold(s, w, opts["hold_deg"]) for s, w in zip(still, smooth)]
            wanted = still
        else:
            wanted = raw
        # The hand kept moving during the glide, so the arm starts a little behind it. It closes that
        # gap at the glide's gentle speed; only once it has caught up does the full speed limit apply.
        step = (opts["max_dps"] if caught_up else min(opts["max_dps"], GLIDE_DPS)) * dt
        target = [min(max(w, s - step), s + step) for w, s in zip(wanted, sent)]
        target[GRIPPER] = min(max(target[GRIPPER], 0.0), 100.0)
        caught_up = caught_up or all(abs(w - t) < 1.0 for w, t in zip(wanted[:GRIPPER], target[:GRIPPER]))
        for joint in range(6):
            hand[joint] += abs(raw[joint] - before[joint])
            arm_path[joint] += abs(target[joint] - sent[joint])
            swings[joint].add(raw[joint])
        before, sent = raw, target
        if len(trace) < 20000:
            trace.append([round(now - began, 4), [round(v, 3) for v in raw], [round(v, 3) for v in target]])
        if not arm.move_joints(target, 0):  # one write, then a 1/HZ wait that ends at once on stop
            _save(trace)
            return {**STOPPED, "report": report()}
    _save(trace)
    summary = report()
    back = seconds_for(home, 2.0)
    if back is None:
        return {"ok": False, "reason": "too far from home to go back at this speed; the arm is holding", "report": summary}
    return {"ok": True, "reason": "", "report": summary} if arm.move_joints(home, back) else {**STOPPED, "report": summary}


def _report(hand, arm_path, swings, seconds) -> str:
    """One line for the screen: how much shake there was, and how much less the arm moved than the hand."""
    body = range(GRIPPER)
    busiest = max(body, key=lambda j: (len(swings[j].sizes), sum(swings[j].sizes)))  # ties: the biggest shake
    sizes = swings[busiest].sizes[1:]  # the first swing starts from wherever the hand happened to be
    rate = len(swings[busiest].sizes) / 2 / seconds if seconds > 0 else 0.0
    shake = (f"{JOINTS[busiest]} shook about {sum(sizes) / len(sizes) / 2:.1f} degrees each way, {rate:.1f} times a second"
             if sizes and rate >= 2.5 else "no steady shake seen")
    moved, sent = sum(hand[j] for j in body), sum(arm_path[j] for j in body)
    less = f" ({100 * (1 - sent / moved):.0f}% less)" if sent < 0.95 * moved else ""
    return (f"{shake}. Over the five arm joints the hand travelled {moved:.0f} degrees and the arm was sent "
            f"{sent:.0f}{less}.")


def _save(trace) -> None:
    """The raw record of the last run (time, leader joints, joints sent), for a plot. Never stops a run."""
    try:
        TRACE.parent.mkdir(exist_ok=True)
        TRACE.write_text(json.dumps({"joints": JOINTS, "rows": trace}))
    except OSError as err:
        print(f"[steady] could not save the trace: {err}", flush=True)


class PretendLeader:
    """Stands in for the leader beside the mock arm: a slow reach with a 5.5 Hz tremor on top."""

    def __init__(self, home: list[float]):
        self.base = [h + d for h, d in zip(home, (0, 30, -40, 30, 0, 0))]
        self.began, self.disconnected = clock(), 0

    def get_action(self) -> dict:
        t = clock() - self.began
        slow = (25 * math.sin(2 * math.pi * 0.2 * t), 0, 10 * math.sin(2 * math.pi * 0.15 * t), 0, 0, 0)
        joints = [b + s for b, s in zip(self.base, slow)]
        for joint, (share, phase) in enumerate(SHAKE):
            joints[joint] += 3 * share * math.sin(2 * math.pi * 5.5 * t + phase)
        joints[GRIPPER] = 50 + 40 * math.sin(2 * math.pi * 0.1 * t)
        return {f"{name}.pos": value for name, value in zip(JOINTS, joints)}

    def disconnect(self) -> None:
        self.disconnected += 1


def _selfcheck() -> None:
    """No hardware. A fake clock drives everything, so 60 seconds of following takes milliseconds."""
    import random
    import shutil
    import sys
    import tempfile

    from core.arm import MockArm

    module = sys.modules[__name__]
    real_clock, real_open, real_poses, real_root = module.clock, module.open_leader, core.arm.POSES, sys.modules.get("arm")
    poses = Path(tempfile.mkdtemp())  # a poses folder of its own: only home, and whatever offset a check writes
    shutil.copy(real_poses / "home.json", poses / "home.json")
    core.arm.POSES = poses

    class Time:  # the fake clock; waiting on the stop flag is what makes it advance
        now = 100.0

    class Flag:
        def __init__(self):
            self.on = False

        def is_set(self):
            return self.on

        def set(self):
            self.on = True

        def clear(self):
            self.on = False

        def wait(self, seconds=0.0):
            if not self.on:
                Time.now += seconds
            return self.on

    class Spy(MockArm):
        def __init__(self):
            super().__init__()
            self.halt, self.writes = Flag(), []
            self._joints = self.load_pose("home")

        def _write(self, joints):
            self.writes.append((Time.now, list(joints)))
            super()._write(joints)

    class Script:
        """A leader that plays joints(t). `bad` maps a reading number to what to do instead."""

        def __init__(self, joints, bad=None, on_read=None):
            self.joints, self.bad, self.on_read, self.reads, self.disconnected = joints, bad or {}, on_read, 0, 0
            self.began = Time.now

        def get_action(self):
            self.reads += 1
            if self.on_read:
                self.on_read(self.reads)
            action = {f"{name}.pos": v for name, v in zip(JOINTS, self.joints(Time.now - self.began))}
            fault = self.bad.get(self.reads)
            if fault == "raise":
                raise ConnectionError("unplugged")
            if fault == "nan":
                action["elbow_flex.pos"] = float("nan")
            if fault == "missing":
                del action["wrist_roll.pos"]
            if fault == "text":
                action["gripper.pos"] = "open"
            return action

        def disconnect(self):
            self.disconnected += 1

    def amplitude(times, values, hz, after):
        """Size and delay of the `hz` part of a signal, by fitting a sine and cosine to it."""
        pts = [(math.sin(2 * math.pi * hz * t), math.cos(2 * math.pi * hz * t), v)
               for t, v in zip(times, values) if t >= after]
        ss, cc, sc = (sum(p[i] * p[j] for p in pts) for i, j in ((0, 0), (1, 1), (0, 1)))
        sv, cv = sum(p[0] * p[2] for p in pts), sum(p[1] * p[2] for p in pts)
        s = (sv * cc - cv * sc) / (ss * cc - sc * sc)  # least squares, so uneven time steps do not skew it
        c = (cv * ss - sv * sc) / (ss * cc - sc * sc)
        return math.hypot(s, c), -math.atan2(c, s) / (2 * math.pi * hz)

    try:
        module.clock = lambda: Time.now

        # 1. the filter: a 5 Hz, 3 degree shake on a slow 20 degree reach, at even and uneven time steps
        rng = random.Random(7)
        for steps in ([1 / 30] * 360, [rng.uniform(0.02, 0.05) for _ in range(360)]):
            times, t = [], 0.0
            for dt in steps:
                t += dt
                times.append(t)
            for hz, size, least, most in ((5.0, 3.0, 0.0, 0.35), (0.25, 20.0, 19.0, 20.0)):
                smoother, out = Smoother([0.0], 1.5), []
                for dt, t in zip(steps, times):
                    out.append(smoother.step([size * math.sin(2 * math.pi * hz * t)], dt)[0])
                got, delay = amplitude(times, out, hz, after=4.0)
                assert least <= got <= most, (hz, got)
                assert hz > 1 or 0.1 < delay < 0.3, delay  # the slow reach trails the hand by about 0.2 s
        # it never overshoots a sudden move
        smoother = Smoother([0.0], 1.5)
        assert max(smoother.step([10.0], 1 / 30)[0] for _ in range(300)) <= 10.0

        # 2. the hold band: a hand trembling in place leaves the output perfectly still
        smoother, still, outs = Smoother([40.0], 1.5), 40.0, []
        for i in range(1, 301):
            still = hold(still, smoother.step([40 + 3 * math.sin(2 * math.pi * 5 * i / 30)], 1 / 30)[0], 0.3)
            outs.append(still)
        assert max(outs[60:]) - min(outs[60:]) < 1e-6, "the hold band let a tremor through"
        assert hold(0, 5, 1) == 4 and hold(0, -5, 1) == -4 and hold(0, 0.5, 1) == 0

        # 3. the swing counter measures a known shake
        swings = Swings(0.0)
        for i in range(1, 301):
            swings.add(3 * math.sin(2 * math.pi * 5 * i / 30))
        assert 95 <= len(swings.sizes) <= 100 and 5.0 < sum(swings.sizes[1:]) / len(swings.sizes[1:]) <= 6.0

        home = MockArm().load_pose("home")

        def away(arm):  # the arm is still out where it was following, not back at home
            return max(abs(a - b) for a, b in zip(arm._joints, home)) > 5
        ready = [h + d for h, d in zip(home, (0, 30, -40, 30, 0, 0))]

        def shaky(t):  # a slow reach with a 5 Hz, 3 degree tremor on every arm joint, gripper sweeping past its ends
            joints = [ready[0] + 25 * math.sin(2 * math.pi * 0.2 * t), ready[1], ready[2], ready[3], ready[4], 0]
            for joint, (share, phase) in enumerate(SHAKE):
                joints[joint] += 3 * share * math.sin(2 * math.pi * 5 * t + phase)
            joints[GRIPPER] = 50 + 60 * math.sin(2 * math.pi * 0.1 * t)
            return joints

        def go(params, leader=None, opener=None):
            arm = Spy()
            leader = leader or Script(shaky)
            module.open_leader = opener or (lambda _arm: leader)
            return arm, leader, run(arm, params, arm.halt)

        class Float64(float):  # stands in for a numpy number, which LeRobot may hand back
            dtype = type("dtype", (), {"kind": "f"})

        assert _number(Float64(2.5)) == 2.5 and type(_number(Float64(2.5))) is float and _number(3) == 3.0
        for bad in (True, "3", None, float("nan"), float("inf"), Float64("nan"), [1.0]):
            try:
                _number(bad)
            except ValueError:
                continue
            raise AssertionError(f"accepted {bad!r}")

        # 4. a full run: home, glide, follow with the shake removed, home again
        arm, leader, result = go({"seconds": 20})
        assert result["ok"] and "5.0 times a second" in result["report"], result
        assert all(abs(a - b) < 1e-9 for a, b in zip(arm._joints, home)), "did not finish at home"
        assert leader.disconnected == 1
        assert all(len(j) == 6 and all(math.isfinite(v) for v in j) and 0 <= j[GRIPPER] <= 100 for _, j in arm.writes)
        steps = [max(abs(a - b) for a, b in zip(arm.writes[i][1], arm.writes[i - 1][1])) for i in range(1, len(arm.writes))]
        assert max(steps) <= 120 / HZ + 1e-6, f"a joint was sent {max(steps):.2f} in one step"
        rows = json.loads(TRACE.read_text())["rows"]
        assert 550 < len(rows) <= 601 and rows[-1][0] <= 20
        hand = sum(abs(rows[i][1][3] - rows[i - 1][1][3]) for i in range(1, len(rows)))
        sent = sum(abs(rows[i][2][3] - rows[i - 1][2][3]) for i in range(1, len(rows)))
        assert sent < 0.02 * hand, (hand, sent)  # wrist_flex only trembles in place: the arm barely moves it
        pan = [row[2][0] for row in rows if row[0] > 4]
        assert max(pan) - min(pan) > 0.9 * 50, "the slow reach was filtered away with the shake"

        # a hand that moved a long way during the glide is caught up with gently, never in one lunge
        arm, leader, result = go({"seconds": 6}, Script(lambda t: [ready[0] + 60 * math.sin(2 * math.pi * 0.25 * t)] + ready[1:5] + [30]))
        rows = json.loads(TRACE.read_text())["rows"]
        early = [abs(rows[i][2][0] - rows[i - 1][2][0]) for i in range(1, 10)]
        assert result["ok"] and abs(rows[0][1][0] - rows[0][2][0]) > 10 and max(early) <= GLIDE_DPS / HZ + 0.002, early  # the trace is rounded

        # 5. the same run unfiltered follows the shake, so the comparison is real
        arm, leader, result = go({"seconds": 20, "filter": False})
        rows = json.loads(TRACE.read_text())["rows"]
        hand = sum(abs(rows[i][1][3] - rows[i - 1][1][3]) for i in range(1, len(rows)))
        sent = sum(abs(rows[i][2][3] - rows[i - 1][2][3]) for i in range(1, len(rows)))
        assert result["ok"] and sent > 0.95 * hand > 1000, (hand, sent)

        # 6. a pretend tremor on a steady hand is reported and removed
        arm, leader, result = go({"seconds": 10, "shake_hz": 6, "shake_deg": 4}, Script(lambda t: list(ready[:5]) + [30]))
        assert result["ok"] and "6.0 times a second" in result["report"], result
        rows = json.loads(TRACE.read_text())["rows"]
        assert max(row[2][3] for row in rows[90:]) - min(row[2][3] for row in rows[90:]) < 0.05

        # 7. bad settings: refused before the leader is opened or anything moves
        nan = float("nan")
        for bad in ({"seconds": 0}, {"seconds": 601}, {"seconds": True}, {"seconds": "10"}, {"cutoff_hz": nan},
                    {"cutoff_hz": 0}, {"cutoff_hz": float("inf")}, {"filter": "no"}, {"filter": 0},
                    {"hold_deg": -1}, {"hold_deg": nan}, {"max_dps": 1000}, {"max_dps": None},
                    {"shake_hz": 5}, {"shake_deg": 3}, {"shake_hz": 1, "shake_deg": 3},
                    {"shake_hz": 5, "shake_deg": 9}, {"shake_hz": nan, "shake_deg": 3}):
            opened = []
            arm, leader, result = go(bad, opener=lambda _arm: opened.append(1))
            assert not result["ok"] and not arm.writes and not opened, (bad, result)

        # 8. no leader, or a leader that reads badly from the start: nothing moves
        def no_leader(_arm):
            raise ConnectionError("no such port")

        arm, leader, result = go({}, opener=no_leader)
        assert not result["ok"] and not arm.writes and "leader" in result["reason"]
        for fault in ("raise", "nan", "missing", "text"):
            arm, leader, result = go({}, Script(shaky, bad={1: fault}))
            assert not result["ok"] and not arm.writes and leader.disconnected == 1, fault

        # 9. the leader fails part-way: the arm holds where it is, with no further move and no trip home
        for fault in ("raise", "nan", "missing"):
            arm, leader, result = go({"seconds": 20}, Script(shaky, bad={150: fault}))
            assert not result["ok"] and "holding" in result["reason"] and leader.disconnected == 1, (fault, result)
            assert away(arm) and leader.reads == 150 and arm.writes[-1][1] == arm._joints
            rows = json.loads(TRACE.read_text())["rows"]
            assert len(rows) == 146 and rows[-1][2] == [round(v, 3) for v in arm._joints], "the trace is not this run's"

        # 10. stop part-way: nothing is sent after it, the arm is not sent home, the leader is let go
        arm, at_stop = Spy(), []

        def press_stop(count):
            if count == 150:
                arm.halt.set()
                at_stop.append(len(arm.writes))

        leader = Script(shaky, on_read=press_stop)
        module.open_leader = lambda _arm: leader
        result = run(arm, {"seconds": 20}, arm.halt)
        assert result["reason"] == "stopped" and not result["ok"] and leader.disconnected == 1
        assert away(arm) and leader.reads == 150 and len(arm.writes) == at_stop[0], "something was sent after stop"

        # 11. every move is asked for gently, not only the following: the trip home, the glide out, the trip back
        def biggest_step(arm):
            return max(max(abs(a - b) for a, b in zip(arm.writes[i][1], arm.writes[i - 1][1])) for i in range(1, len(arm.writes)))

        far_hand = Script(lambda t: [home[0] + 150] + ready[1:5] + [30])
        arm = Spy()
        arm._joints[1] += 80  # the arm does not start at home either
        arm.writes.append((Time.now, list(arm._joints)))
        module.open_leader = lambda _arm: far_hand
        result = run(arm, {"seconds": 5, "max_dps": 10}, arm.halt)
        assert result["ok"] and biggest_step(arm) <= 10 / HZ + 1e-6, (result, biggest_step(arm) * HZ)
        arm, leader, result = go({"seconds": 5}, Script(lambda t: [home[0] + 150] + ready[1:5] + [30]))
        assert result["ok"] and biggest_step(arm) <= GLIDE_DPS / HZ + 1e-6, biggest_step(arm) * HZ
        # a move that cannot be made that gently in one go is refused before anything moves
        arm, leader, result = go({"max_dps": 10}, Script(lambda t: [home[0] + 400] + ready[1:5] + [30]))
        assert not result["ok"] and not arm.writes and "Nothing moved" in result["reason"], result

        # 12. the offset between the two arms' zero points is added to every leader reading
        shift = [10.0, -20.0, 5.0, 0.0, 30.0, 2.0]
        (poses / "teleop_offset.json").write_text(json.dumps({f"{n}.pos": v for n, v in zip(JOINTS, shift)}))
        steady_hand = [h + d for h, d in zip(home, (20, 20, -20, 10, 0, 40))]
        arm, leader, result = go({"seconds": 4}, Script(lambda t: list(steady_hand)))
        rows = json.loads(TRACE.read_text())["rows"]
        assert result["ok"] and all(abs(r - (h + o)) < 1e-3 for r, h, o in zip(rows[-1][1], steady_hand, shift)), rows[-1][1]
        assert all(abs(c - (h + o)) < 0.31 for c, h, o in zip(rows[-1][2], steady_hand, shift)), rows[-1][2]
        for bad in ({**{f"{n}.pos": 0.0 for n in JOINTS}, "elbow_flex.pos": float("nan")},
                    {f"{n}.pos": 0.0 for n in JOINTS[:5]}, {**{f"{n}.pos": 0.0 for n in JOINTS}, "gripper.pos": "2"},
                    {**{f"{n}.pos": 0.0 for n in JOINTS}, "shoulder_pan.pos": 500.0}, [0.0] * 6, "not json"):
            (poses / "teleop_offset.json").write_text(bad if type(bad) is str else json.dumps(bad))
            opened = []
            arm, leader, result = go({}, opener=lambda _arm: opened.append(1))
            assert not result["ok"] and not arm.writes and not opened and "teleop_offset" in result["reason"], (bad, result)
        (poses / "teleop_offset.json").unlink()

        # 13. on the real arm: no offset file, or a leader on the follower's own port, and nothing is opened or moved
        class RealSpy(Spy):
            REAL = True

        class Root:  # stands in for the root arm.py
            FOLLOWER_PORT, LEADER_PORT, opened = "COM3", "COM4", 0

            @classmethod
            def leader(cls):
                cls.opened += 1
                return Script(shaky)

        sys.modules["arm"] = Root
        module.open_leader = real_open
        arm = RealSpy()
        result = run(arm, {"seconds": 3}, arm.halt)
        assert not result["ok"] and not arm.writes and not Root.opened and "offset" in result["reason"], result
        (poses / "teleop_offset.json").write_text(json.dumps({f"{n}.pos": 0.0 for n in JOINTS}))
        for follower_port, leader_port in (("COM3", "COM3"), ("COM3", "com3 "), ("/dev/ttyACM1", "/dev/./ttyACM1")):
            Root.FOLLOWER_PORT, Root.LEADER_PORT = follower_port, leader_port
            arm = RealSpy()
            result = run(arm, {"seconds": 3}, arm.halt)
            assert not result["ok"] and not arm.writes and not Root.opened and "own port" in result["reason"], result
        Root.FOLLOWER_PORT, Root.LEADER_PORT = "COM3", "COM4"
        arm = RealSpy()
        result = run(arm, {"seconds": 3}, arm.halt)
        assert result["ok"] and Root.opened == 1, result
        (poses / "teleop_offset.json").unlink()

        # 14. the pretend leader beside the mock arm runs end to end
        module.open_leader = real_open
        arm = Spy()
        result = run(arm, {"seconds": 5}, arm.halt)
        assert result["ok"] and "5.5 times a second" in result["report"], result
    finally:
        module.clock, module.open_leader, core.arm.POSES = real_clock, real_open, real_poses
        sys.modules.pop("arm", None)
        if real_root is not None:
            sys.modules["arm"] = real_root
        shutil.rmtree(poses, ignore_errors=True)
    print("steady ok")


if __name__ == "__main__":
    _selfcheck()
