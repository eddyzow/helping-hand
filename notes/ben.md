# Ben (agent: Claude Code)

Updated Sat Nov 14, 12:30 AM ET.

## Working on now

Nothing claimed yet. Ben has no person number in `newcontext.md`. Persons 3 (keypad and games) and 4 (drawing, personality, demo) are unassigned; tell Ben which one you want him on.

So far this agent has only read the repo on `main`. It has no arm, camera or keypad attached and has run nothing except `python grid.py` (prints `grid ok`).

## Done and how it was tested

Code read of the root scripts at `6eb8253`. Everything below is from reading, not from running on hardware.

## Needs from others

- Daniel: `daniel/arm-core` (`9d5081e`, `e03beaa`) is not on GitHub; only `main` exists there. Nobody else can develop against `MockArm`, the dispatcher or the skill interface until it is pushed. Your note already asks your Claude to publish it; this is a second request.
- Daniel: whoever takes Person 3 or 4 needs `core/skill.py` and `MockArm` to start. If the full branch is not ready, pushing just those two files would unblock them.
- Eddy: `arm.py teach` and `arm.py pose` call `bus.disable_torque()` right after connecting. The arm will go limp and fall unless someone is already holding it. Worth a line in the prompt text before the torque goes off.
- Eddy: `draw.py --go` replays `gripper.pos` as it was read while the arm was limp, so the gripper is commanded to exactly the pen's width and may not squeeze it. Suggest overriding `gripper.pos` with a closed value during drawing, the way `pick.py` does with `GRIP_CLOSED`.
- Eddy: `pick.py` maps the pixel through a flat-table homography. A grasp point on top of a tall object is off by roughly (object height / camera height) times its distance from the point under the camera. Fine for a lanyard, worth checking on a Duplo stack or a mouse near the grid edge.
- Eddy: `grid.py` blends joint angles, so between taught points the gripper height is not guaranteed. Before the first real grasp, send the arm to the four cell midpoints of the `up` grid and then the `down` grid and look for dips into the table.
- Eddy and Daniel: `pick.py --go` needs the arm, camera and microphone in one process, and the arm is under WSL. Daniel's note says the WSL camera is untested. If it does not open, `pick.py --corners x,y ...` and `--image` already let the camera side run on Windows; the missing piece would be passing the frame across.
- Everyone: `newcontext.md` drops the accessibility framing and `PLAN.md` still recommends Best Accessibility Hack. The track has to be one or the other by the Saturday night submission.

## Answers to questions other notes asked

None addressed to Ben yet.
