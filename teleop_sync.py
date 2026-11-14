"""Leader -> follower teleoperation that lines the two arms up first, and can record the session.

    python teleop_sync.py --measure          # once: hold both arms in the SAME pose, press Enter
    python teleop_sync.py                    # teleoperate with the saved offsets
    python teleop_sync.py --record pick      # the same, and save what the follower was told to poses/taught/pick.json

Why: each arm's zero is the middle of the range it was swept through at calibration, and the two
were swept differently (elbow: 157 degrees on the leader, 130 on the follower). Plain
lerobot-teleoperate therefore holds the follower in a different shape from the leader. Recalibrating
would fix that but rewrites the motors' settings and invalidates every taught pose, so this adds a
fixed offset per joint instead: follower = leader + offset.

Ctrl+C stops. The follower's motors switch OFF when this exits, so hold it or let it rest first.
Ports: FOLLOWER_PORT (default COM3) and LEADER_PORT (default COM4).
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
OFFSETS = HERE / "poses" / "teleop_offset.json"
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
HZ = 30
MAX_STEP = 15.0  # the follower never jumps more than this many degrees in one command (LeRobot refuses a whole number here)
EASE_S = 3.0   # at the start the follower takes this long to glide to the leader's pose


def main() -> None:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    measure = "--measure" in sys.argv or not OFFSETS.exists()
    record = sys.argv[sys.argv.index("--record") + 1] if "--record" in sys.argv else None
    follower = SO101Follower(SO101FollowerConfig(
        port=os.environ.get("FOLLOWER_PORT", "COM3"), id="follower", max_relative_target=MAX_STEP))
    leader = SO101Leader(SO101LeaderConfig(port=os.environ.get("LEADER_PORT", "COM4"), id="leader"))
    input("The follower's motors switch off and on while connecting. Hold it or check it is resting, then Enter. ")
    follower.connect()
    leader.connect()
    keys = [f"{j}.pos" for j in JOINTS]
    frames = []
    try:
        if measure:
            input("The follower goes LIMP next. Hold it, then Enter. ")
            follower.bus.disable_torque()
            input("Put BOTH arms in exactly the same pose, side by side (same bend at every joint, "
                  "claws equally open). Hold them still, then Enter. ")
            lead, follow = leader.get_action(), follower.get_observation()
            offset = {k: round(float(follow[k]) - float(lead[k]), 2) for k in keys}
            OFFSETS.write_text(json.dumps(offset, indent=1))
            print("offsets (follower minus leader):", offset)
            follower.bus.enable_torque()
            input("The follower is holding again. Let go of it, keep hold of the leader, then Enter to start. ")
        offset = json.loads(OFFSETS.read_text())
        print("Teleoperating. Ctrl+C to stop." + (f" Recording to poses/taught/{record}.json." if record else ""))
        # The two arms rarely start in the same pose. So the follower first GLIDES to where the leader
        # is, over EASE_S seconds, and only then follows it directly.
        began, start = time.perf_counter(), follower.get_observation()
        while True:
            tick = time.perf_counter()
            lead = leader.get_action()
            command = {k: float(lead[k]) + offset[k] for k in keys}
            command["gripper.pos"] = min(100.0, max(0.0, command["gripper.pos"]))
            share = min(1.0, (tick - began) / EASE_S)
            if share < 1.0:
                command = {k: float(start[k]) + (command[k] - float(start[k])) * share for k in keys}
            follower.send_action(command)
            if record:
                frames.append([round(command[k], 2) for k in keys])
            time.sleep(max(0.0, 1 / HZ - (time.perf_counter() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        if record and frames:
            out = HERE / "poses" / "taught" / f"{record}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"hz": HZ, "joints": JOINTS, "frames": frames}))
            print(f"saved {len(frames) / HZ:.1f} s to {out}")
        input("Stopping: the follower's motors switch OFF next. Hold it or rest it, then Enter. ")
        leader.disconnect()
        follower.disconnect()


if __name__ == "__main__":
    main()
