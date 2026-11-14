"""Replay physical arm taps on a modeled SayoDevice O3C in MuJoCo."""

import argparse
from contextlib import nullcontext
from dataclasses import dataclass
import math
from pathlib import Path
from statistics import mean
import time

import mujoco

from tap_pattern import KeyEvent, command_times, read_pattern

ROOT = Path(__file__).resolve().parent
RELEASED_POSE = {
    "shoulder_pan": 0.0,
    "shoulder_lift": -0.30,
    "elbow_flex": 0.90,
    "wrist_flex": 0.30,
    "wrist_roll": 0.0,
    "gripper": 0.40,
}
WRIST_STROKE = 0.015
WRIST_SPEED = math.radians(270)  # 45 RPM at no load for the 12 V STS3215.


@dataclass(frozen=True)
class O3CSettings:
    actuation_mm: float = 0.70
    reset_mm: float = 0.40
    rapid_trigger: bool = False
    rt_press_mm: float = 0.25
    rt_release_mm: float = 0.40
    rt_top_mm: float = 0.50
    rt_end_mm: float = 3.80

    def validate(self, travel_mm: float) -> None:
        if not 0 <= self.reset_mm < self.actuation_mm <= travel_mm:
            raise ValueError("Key depths must satisfy 0 <= reset < actuation <= key travel")
        if self.rapid_trigger and not (
            0 <= self.rt_top_mm < self.rt_end_mm <= travel_mm
            and 0 < self.rt_press_mm <= travel_mm
            and 0 < self.rt_release_mm <= travel_mm
        ):
            raise ValueError("Rapid Trigger distances and active range must fit within key travel")


class O3CKey:
    """Translate switch travel into key events using an approximate Hall trigger model."""

    def __init__(self, settings: O3CSettings):
        self.settings = settings
        self.is_down = False
        self.extreme_mm = None

    def update(self, depth_mm: float) -> bool:
        settings = self.settings
        next_down = depth_mm > settings.reset_mm if self.is_down else depth_mm >= settings.actuation_mm
        if settings.rapid_trigger:
            if depth_mm < settings.rt_top_mm:
                self.extreme_mm = None
            elif self.is_down:
                bounded = min(depth_mm, settings.rt_end_mm)
                if self.extreme_mm is None or bounded > self.extreme_mm:
                    self.extreme_mm = bounded
                next_down = next_down and self.extreme_mm - depth_mm < settings.rt_release_mm
            elif self.extreme_mm is not None:
                self.extreme_mm = min(depth_mm, self.extreme_mm)
                bounded = min(depth_mm, settings.rt_end_mm)
                next_down = bounded - self.extreme_mm >= settings.rt_press_mm

        changed = next_down != self.is_down
        if changed:
            self.is_down = next_down
            self.extreme_mm = (
                min(depth_mm, settings.rt_end_mm)
                if settings.rapid_trigger and depth_mm >= settings.rt_top_mm
                else None
            )
        return changed


def tap_train(hz: float) -> list[KeyEvent]:
    if not math.isfinite(hz) or hz <= 0:
        raise ValueError("Tap rate must be finite and positive")
    return [KeyEvent(0.25 + edge / (2 * hz), edge % 2 == 0) for edge in range(100)]


def simulate(
    commands: list[KeyEvent],
    show_viewer: bool,
    settings: O3CSettings = O3CSettings(),
    wrist_stroke: float = WRIST_STROKE,
) -> tuple[list[KeyEvent], float, float]:
    model = mujoco.MjModel.from_xml_path(str(ROOT / "tap_scene.xml"))
    settings.validate(model.joint("key_travel").range[1] * 1000)
    data = mujoco.MjData(model)
    for joint, position in RELEASED_POSE.items():
        data.joint(joint).qpos[0] = position
        data.actuator(joint).ctrl[0] = position

    dt = model.opt.timestep
    wrist = data.actuator("wrist_flex").ctrl
    pressed_wrist = RELEASED_POSE["wrist_flex"] + wrist_stroke
    if not math.isfinite(wrist_stroke) or wrist_stroke <= 0 or pressed_wrist > model.actuator("wrist_flex").ctrlrange[1]:
        raise ValueError("Wrist stroke must be positive and stay within the joint range")
    key_travel = data.joint("key_travel").qpos
    left_travel = data.joint("left_key_travel").qpos
    right_travel = data.joint("right_key_travel").qpos
    key_color = model.geom("keycap").rgba
    up_color = key_color.copy()
    down_color = [0.34, 0.91, 0.44, 1]
    target = wrist[0]
    max_wrist_step = WRIST_SPEED * dt
    for _ in range(round(0.25 / dt)):
        mujoco.mj_step(model, data)

    if show_viewer:
        from mujoco import viewer

        window = viewer.launch_passive(model, data)
    else:
        window = nullcontext()

    actual = []
    command_index = 0
    key = O3CKey(settings)
    peak_depth = 0.0
    peak_neighbor_depth = 0.0
    last_step = math.ceil((commands[-1].at + 0.25) / dt)
    with window as display:
        start = time.perf_counter()
        for step in range(last_step):
            at = step * dt
            while command_index < len(commands) and commands[command_index].at <= at + 1e-9:
                target = pressed_wrist if commands[command_index].down else RELEASED_POSE["wrist_flex"]
                command_index += 1

            wrist[0] += max(-max_wrist_step, min(max_wrist_step, target - wrist[0]))
            mujoco.mj_step(model, data)
            depth = float(key_travel[0])
            peak_depth = max(depth, peak_depth)
            peak_neighbor_depth = max(peak_neighbor_depth, float(left_travel[0]), float(right_travel[0]))
            if key.update(depth * 1000):
                actual.append(KeyEvent((step + 1) * dt, key.is_down))

            if display is not None and step % 16 == 0:
                if not display.is_running():
                    raise InterruptedError("Viewer closed before the pattern finished")
                with display.lock():
                    key_color[:] = down_color if key.is_down else up_color
                display.sync()
                time.sleep(max(0, start + at - time.perf_counter()))

    return actual, peak_depth, peak_neighbor_depth


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    pattern = parser.add_mutually_exclusive_group()
    pattern.add_argument("--pattern", type=Path, help="CSV with time_ms,state columns")
    pattern.add_argument("--hz", type=float, help="Test 50 taps at this many taps per second")
    parser.add_argument("--view", action="store_true", help="Watch the SO-101 in MuJoCo")
    parser.add_argument("--events", action="store_true", help="Print each input's timing")
    parser.add_argument("--press-lead-ms", type=float, default=0)
    parser.add_argument("--release-lead-ms", type=float, default=0)
    parser.add_argument("--max-error-ms", type=float, help="Fail if an input is off by more than this")
    keypad = parser.add_argument_group("O3C key settings")
    keypad.add_argument("--actuation-mm", type=float, default=O3CSettings.actuation_mm)
    keypad.add_argument("--reset-mm", type=float, default=O3CSettings.reset_mm,
                        help="Absolute release depth from the top of the stroke")
    keypad.add_argument("--rapid-trigger", action="store_true")
    keypad.add_argument("--rt-press-mm", type=float, default=O3CSettings.rt_press_mm)
    keypad.add_argument("--rt-release-mm", type=float, default=O3CSettings.rt_release_mm)
    keypad.add_argument("--rt-top-mm", type=float, default=O3CSettings.rt_top_mm)
    keypad.add_argument("--rt-end-mm", type=float, default=O3CSettings.rt_end_mm)
    parser.add_argument("--wrist-stroke-deg", type=float, default=math.degrees(WRIST_STROKE))
    args = parser.parse_args()

    try:
        if args.hz is None:
            desired = read_pattern(args.pattern or ROOT / "demo_taps.csv")
        else:
            desired = tap_train(args.hz)

        if args.max_error_ms is not None and (
            not math.isfinite(args.max_error_ms) or args.max_error_ms < 0
        ):
            raise ValueError("Maximum timing error must be finite and nonnegative")
        commands = command_times(desired, args.press_lead_ms, args.release_lead_ms)
        # Start before the level clock if compensation moves the first command before zero.
        preroll = max(0, -commands[0].at)
        if preroll:
            commands = [KeyEvent(event.at + preroll, event.down) for event in commands]

        settings = O3CSettings(
            actuation_mm=args.actuation_mm,
            reset_mm=args.reset_mm,
            rapid_trigger=args.rapid_trigger,
            rt_press_mm=args.rt_press_mm,
            rt_release_mm=args.rt_release_mm,
            rt_top_mm=args.rt_top_mm,
            rt_end_mm=args.rt_end_mm,
        )
        actual, peak_depth, peak_neighbor = simulate(
            commands, args.view, settings, math.radians(args.wrist_stroke_deg)
        )
    except (OSError, ValueError, InterruptedError) as error:
        print(f"Simulation stopped: {error}")
        return 2

    mode = "Rapid Trigger" if settings.rapid_trigger else "fixed actuation and release"
    print(f"SayoDevice O3C, {mode} (actuation {settings.actuation_mm:g} mm, reset {settings.reset_mm:g} mm).")
    if settings.rapid_trigger:
        print(f"Rapid Trigger distances: press {settings.rt_press_mm:g} mm, release {settings.rt_release_mm:g} mm.")
    print(f"Requested {len(desired) // 2} taps. Detected {len(actual)} of {len(desired)} key edges.")
    print(f"Peak key travel: {peak_depth * 1000:.2f} mm. Adjacent keys: {peak_neighbor * 1000:.2f} mm.")
    if peak_neighbor * 1000 >= settings.actuation_mm:
        print("FAIL: An adjacent key reached the actuation depth.")
        return 1
    if [event.down for event in actual] != [event.down for event in desired]:
        print("FAIL: The simulated key missed or added inputs.")
        return 1

    errors = {True: [], False: []}
    if args.events:
        print("state  target_ms  actual_ms  error_ms")
    for wanted, observed in zip(desired, actual, strict=True):
        actual_ms = (observed.at - preroll) * 1000
        error_ms = actual_ms - wanted.at * 1000
        errors[wanted.down].append(error_ms)
        if args.events:
            state = "down" if wanted.down else "up"
            print(f"{state:5}  {wanted.at * 1000:9.1f}  {actual_ms:9.1f}  {error_ms:+8.1f}")
    for action, values in (("Press", errors[True]), ("Release", errors[False])):
        print(f"{action} timing: mean {mean(values):+.1f} ms, range {min(values):+.1f} to {max(values):+.1f} ms.")
    worst_error = max(abs(error) for values in errors.values() for error in values)
    if args.max_error_ms is not None and worst_error > args.max_error_ms + 1e-9:
        print(f"FAIL: Worst timing error was {worst_error:.1f} ms (limit {args.max_error_ms:g} ms).")
        return 1
    if args.max_error_ms is None:
        print("PASS: The simulated key registered every press and release.")
    else:
        print(f"PASS: Every input registered within {worst_error:.1f} ms of its target.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
