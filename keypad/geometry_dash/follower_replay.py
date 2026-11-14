"""Tap an O3C with an SO-101 follower using taught encoder positions."""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from statistics import median
from threading import Event
from time import perf_counter, sleep

from pynput import keyboard
from scservo_sdk import COMM_SUCCESS, GroupSyncWrite, PacketHandler, PortHandler
from serial.tools import list_ports

from tap_pattern import KeyEvent, command_times, read_pattern


ROOT = Path(__file__).resolve().parent
MOTOR_IDS = tuple(range(1, 7))
WRIST_ID = 4
STS3215_MODEL = 777
PRESENT_POSITION = 56
GOAL_POSITION = 42
TORQUE_ENABLE = 40
GOAL_SPEED = 46
TORQUE_LIMIT = 48
MAX_WRIST_STROKE = 30
POSE_TOLERANCE = 12
TEST_EVENTS = [
    KeyEvent(0.5, True), KeyEvent(0.7, False),
    KeyEvent(1.5, True), KeyEvent(1.7, False),
    KeyEvent(2.5, True), KeyEvent(4.5, False),
]


class ServoBus:
    def __init__(self, port_name: str):
        self.port = PortHandler(port_name)
        self.packet = PacketHandler(0)

    def check(self, result: int, error: int, operation: str):
        if result != COMM_SUCCESS:
            raise RuntimeError(f"{operation}: {self.packet.getTxRxResult(result)}")
        if error:
            raise RuntimeError(f"{operation}: servo status 0x{error:02x}")

    def read(self, motor_id: int, address: int, size: int = 2) -> int:
        read = self.packet.read1ByteTxRx if size == 1 else self.packet.read2ByteTxRx
        value, result, error = read(self.port, motor_id, address)
        self.check(result, error, f"Read motor {motor_id}, register {address}")
        return value

    def write(self, address: int, values: dict[int, int], size: int = 2):
        group = GroupSyncWrite(self.port, self.packet, address, size)
        for motor_id, value in values.items():
            group.addParam(motor_id, list(value.to_bytes(size, "little")))
        self.check(group.txPacket(), 0, f"Write register {address}")

    def pose(self) -> dict[int, int]:
        positions = {motor: self.read(motor, PRESENT_POSITION) for motor in MOTOR_IDS}
        if any(not 0 <= value <= 4095 for value in positions.values()):
            raise ValueError("Expected single-turn encoder positions in 0–4095")
        return positions

    def wrist(self, goal: int):
        self.write(GOAL_POSITION, {WRIST_ID: goal})


@contextmanager
def connect(port_name: str):
    bus = ServoBus(port_name)
    try:
        if not bus.port.openPort():
            raise RuntimeError(f"Could not open {port_name} at 1 Mbps")
        bus.port.ser.write_timeout = 0.1
        for motor in MOTOR_IDS:
            if bus.read(motor, 3) != STS3215_MODEL or bus.read(motor, 33, 1) != 0:
                raise ValueError(f"Motor {motor} must be an STS3215 in position mode")
        yield bus
    finally:
        if bus.port.is_open:
            bus.port.closePort()


def validate_pose(hover: dict[int, int], pressed: int):
    if set(hover) != set(MOTOR_IDS) or any(not 0 <= value <= 4095 for value in hover.values()):
        raise ValueError("Expected a released encoder position for each motor ID 1–6")
    if not 0 <= pressed <= 4095 or not 0 < abs(pressed - hover[WRIST_ID]) <= MAX_WRIST_STROKE:
        raise ValueError(f"Pressed and released wrist positions must be 1–{MAX_WRIST_STROKE} ticks apart")


def teach(bus: ServoBus, path: Path):
    if path.exists():
        raise FileExistsError(f"{path} already exists. Use --pose with a new filename to teach again.")
    if any(bus.read(motor, TORQUE_ENABLE, 1) for motor in MOTOR_IDS):
        raise ValueError("Power-cycle the supported follower before teaching so its joints are free")
    input("Support the arm. Line up the tip just above the middle key, then press Enter to capture release. ")
    hover = bus.pose()
    print(f"Released wrist position: {hover[WRIST_ID]}.")
    input("Move only the wrist just far enough to register Space, then press Enter to capture press. ")
    pressed = bus.pose()
    if any(abs(pressed[motor] - hover[motor]) > POSE_TOLERANCE for motor in MOTOR_IDS if motor != WRIST_ID):
        raise ValueError("Another joint moved during teaching. Support the arm and capture the two poses again.")
    validate_pose(hover, pressed[WRIST_ID])
    with path.open("x", encoding="utf-8") as file:
        json.dump({"released": hover, "pressed_wrist": pressed[WRIST_ID]}, file, indent=2)
        file.write("\n")
    print(f"Saved wrist positions {hover[WRIST_ID]} and {pressed[WRIST_ID]} to {path}.")


def load_pose(path: Path) -> tuple[dict[int, int], int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        hover = {int(motor): position for motor, position in data["released"].items()}
        pressed = data["pressed_wrist"]
        if any(type(value) is not int for value in (*hover.values(), pressed)):
            raise ValueError("Encoder positions must be integers")
        validate_pose(hover, pressed)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid pose file. Capture the released and pressed positions with teach.") from error
    return hover, pressed


def hold_current_pose(bus: ServoBus, hover: dict[int, int], pressed: int, speed_rpm: float):
    current = bus.pose()
    if any(abs(hover[motor] - current[motor]) > POSE_TOLERANCE for motor in MOTOR_IDS):
        raise ValueError("Manually place the supported follower back at the taught released pose")
    low = bus.read(WRIST_ID, 9)
    high = bus.read(WRIST_ID, 11)
    if not (low <= min(current[WRIST_ID], hover[WRIST_ID], pressed)
            <= max(current[WRIST_ID], hover[WRIST_ID], pressed) <= high):
        raise ValueError("Taught wrist positions are outside the servo's position limits")

    phase = bus.read(WRIST_ID, 18, 1)
    speed_units = 0.0146 if phase & 4 else 0.732
    for address, value in (
        (TORQUE_LIMIT, min(300, bus.read(WRIST_ID, TORQUE_LIMIT))),
        (GOAL_SPEED, max(1, round(speed_rpm / speed_units))),
    ):
        bus.write(address, {WRIST_ID: value})
        if bus.read(WRIST_ID, address) != value:
            raise RuntimeError(f"Wrist did not accept register {address}")

    # Set the current positions before enabling hold on all six joints.
    bus.write(GOAL_POSITION, current)
    bus.write(TORQUE_ENABLE, dict.fromkeys(MOTOR_IDS, 1), size=1)


class KeyboardRun:
    def __init__(self, restart: str, watch_taps: bool, jump: str = "space"):
        self.restart = restart
        self.watch_taps = watch_taps
        self.jump = jump
        self.started = Event()
        self.stopped = Event()
        self.epoch = None
        self.space_down = False
        self.edges = []
        self.restart_down = False

    def is_jump(self, key):
        if self.jump == "space":
            return key == keyboard.Key.space
        if self.jump == "up":
            return key == keyboard.Key.up
        return getattr(key, "char", None) == self.jump

    def on_press(self, key):
        now = perf_counter()
        if key == keyboard.Key.f8 or getattr(key, "char", None) == "z":
            self.stopped.set()
        elif getattr(key, "char", None) == self.restart and not self.restart_down:
            self.restart_down = True
            if self.epoch is None:
                self.epoch = now
                self.started.set()
            else:
                self.stopped.set()
        elif self.watch_taps and self.is_jump(key) and not self.space_down:
            self.space_down = True
            self.edges.append(KeyEvent(now, True))

    def on_release(self, key):
        if getattr(key, "char", None) == self.restart:
            self.restart_down = False
        elif self.watch_taps and self.is_jump(key) and self.space_down:
            self.space_down = False
            self.edges.append(KeyEvent(perf_counter(), False))


def send_events(bus: ServoBus, run: KeyboardRun, epoch: float, events: list[KeyEvent], up: int, down: int):
    dispatches = []
    for event in events:
        deadline = epoch + event.at
        if run.stopped.wait(max(0.0, deadline - perf_counter())):
            break
        sent_at = perf_counter()
        if sent_at - deadline > 0.050:
            raise RuntimeError("A wrist command ran more than 50 ms late. Replay stopped.")
        bus.wrist(down if event.down else up)
        dispatches.append(KeyEvent(sent_at, event.down))
    return dispatches


def report_test(commands: list[KeyEvent], edges: list[KeyEvent], jump: str) -> int:
    if len(commands) != len(TEST_EVENTS):
        print("Tap test stopped.")
        return 1
    if [event.down for event in edges] != [event.down for event in commands]:
        print(f"Expected 6 {jump} events, detected {len(edges)}. Check the key mapping and wrist positions.")
        return 1
    delays = {True: [], False: []}
    for sent, observed in zip(commands, edges, strict=True):
        if observed.at < sent.at:
            print(f"{jump} changed before its corresponding command. Check for early releases or extra input.")
            return 1
        delays[sent.down].append((observed.at - sent.at) * 1000)
    print("Detected all 3 physical taps, including the 2-second hold.")
    print(f"Median delay: press {median(delays[True]):.1f} ms, release {median(delays[False]):.1f} ms.")
    return 0


def run_motion(bus: ServoBus, args, hover: dict[int, int], pressed: int, events: list[KeyEvent]) -> int:
    testing = args.action == "test"
    run = KeyboardRun(args.restart, testing, args.jump if testing else "space")
    parked = False
    try:
        hold_current_pose(bus, hover, pressed, args.speed_rpm)
        parked = True
        bus.wrist(hover[WRIST_ID])
        sleep(0.3)
        if abs(bus.pose()[WRIST_ID] - hover[WRIST_ID]) > 4:
            raise RuntimeError("Wrist did not settle at the released position")
        with keyboard.Listener(on_press=run.on_press, on_release=run.on_release) as listener:
            listener.wait()
            if testing:
                print("Keep your hands clear. The follower will tap three times. Z or F8 stops motion.", flush=True)
                epoch = perf_counter() + 0.5
            else:
                print(f"Focus Geometry Dash and press {args.restart.upper()} to restart and replay. Z or F8 stops.", flush=True)
                while not run.stopped.is_set() and not run.started.wait(0.05):
                    pass
                if run.stopped.is_set():
                    return 1
                epoch = run.epoch
            dispatches = send_events(bus, run, epoch, events, hover[WRIST_ID], pressed)
            if testing:
                run.stopped.wait(0.3)
                return report_test(dispatches, run.edges.copy(), args.jump)
    finally:
        if parked:
            try:
                bus.wrist(hover[WRIST_ID])
            except (OSError, RuntimeError):
                print("Could not command wrist release. Support the arm and switch off follower power.")
                raise
            print("Follower is holding the released pose. Support the arm before switching off power.")
    print(f"Sent {len(dispatches)} of {len(events)} wrist commands.")
    return int(len(dispatches) != len(events))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("ports", help="List serial ports without opening them")
    for action in ("teach", "test", "replay"):
        sub = actions.add_parser(action)
        sub.add_argument("--port", required=True, help="USB serial port for the SO-101 follower")
        sub.add_argument("--pose", type=Path, default=ROOT / "follower_pose.json")
        if action in ("test", "replay"):
            sub.add_argument("--speed-rpm", type=float, default=12)
            sub.set_defaults(restart="r")
        if action == "test":
            sub.add_argument("--jump", default="space", help="Key the O3C sends (space, up, or a lowercase letter)")
        if action == "replay":
            sub.add_argument("--pattern", type=Path, default=ROOT / "stereo_madness.csv")
            sub.add_argument("--first-taps", type=int, help="Replay only the first N complete taps")
            sub.add_argument("--restart", default="r")
            sub.add_argument("--press-lead-ms", type=float, default=0)
            sub.add_argument("--release-lead-ms", type=float, default=0)
    args = parser.parse_args()

    if args.action == "ports":
        ports = sorted(list_ports.comports())
        for port in ports:
            print(f"{port.device:12} {port.description}")
        if not any(port.vid is not None for port in ports):
            print("No USB serial adapter detected. Connect the follower's USB cable and check again.")
        return 0

    try:
        if args.action == "teach":
            with connect(args.port) as bus:
                teach(bus, args.pose)
            return 0
        if not 0 < args.speed_rpm <= 30:
            raise ValueError("Use a wrist speed above 0 and at most 30 RPM for this key tap")
        if args.action == "test" and args.jump not in ("space", "up") and (
            len(args.jump) != 1 or args.jump not in "abcdefghijklmnopqrstuvwxy"
        ):
            raise ValueError("--jump must be space, up, or a lowercase letter other than z (stop)")
        hover, pressed = load_pose(args.pose)
        events = TEST_EVENTS
        if args.action == "replay":
            if len(args.restart) != 1 or args.restart not in "abcdefghijklmnopqrstuvwxy":
                raise ValueError("--restart must be a lowercase letter other than z (stop)")
            events = read_pattern(args.pattern)
            if args.first_taps is not None:
                if args.first_taps < 1:
                    raise ValueError("--first-taps must be at least 1")
                events = events[:args.first_taps * 2]
            events = command_times(events, args.press_lead_ms, args.release_lead_ms)
            if events[0].at < 0:
                raise ValueError("The first wrist command must be at or after the restart key")
        print(f"The SO-101 follower on {args.port} will hold its current pose and tap with wrist flex.")
        with connect(args.port) as bus:
            return run_motion(bus, args, hover, pressed, events)
    except (OSError, EOFError, RuntimeError, ValueError) as error:
        print(f"Stopped: {error}")
        return 1
    except KeyboardInterrupt:
        print("Stopped by user.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
