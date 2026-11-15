"""Close or open the follower's claw, nothing else. Talks to the claw motor only, so it works whatever state the
rest of the arm is in (and never touches the faulty wrist-roll motor).

    python drawloop/grip.py            # grip tight (50 % force)
    python drawloop/grip.py 30         # grip at 30 % force (use this when it will hold for a long time: less heat)
    python drawloop/grip.py open       # open fully; whatever it holds will drop
    python drawloop/grip.py off        # motor off: the claw goes limp

Prints where the claw stopped, how hard it is squeezing and the motor's temperature (cut-out is 70 C).
Stop any script that owns the arm first (dispatcher, steady.py, a drawing run): only one program can use COM3.
"""
import os
import sys
import time

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

CLOSED, OPEN = 2005, 3523   # the claw's calibrated range in motor ticks (follower.json): shut, wide open
what = sys.argv[1] if len(sys.argv) > 1 else "50"
bus = FeetechMotorsBus(port=os.environ.get("FOLLOWER_PORT", "COM3"), motors={"gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100)})
bus.connect()
write = lambda name, value: bus.write(name, "gripper", value, normalize=False, num_retry=8)
read = lambda name: bus.read(name, "gripper", normalize=False, num_retry=8)
if what == "off":
    write("Torque_Enable", 0)
elif what == "open":
    write("Torque_Limit", 400); write("Torque_Enable", 1); write("Goal_Position", OPEN)
else:
    force = float(what)
    if not 5 <= force <= 80:
        sys.exit("force is a percentage from 5 to 80")
    write("Torque_Limit", int(force * 10)); write("Torque_Enable", 1); write("Goal_Position", CLOSED + 100)
time.sleep(1.5)
print(f"claw at {100 * (read('Present_Position') - CLOSED) / (OPEN - CLOSED):.0f} (0 shut, 100 open), "
      f"squeezing at {(read('Present_Load') & 0x3FF) / 10:.0f} %, motor {read('Present_Temperature')} C")
bus.disconnect(disable_torque=False)
