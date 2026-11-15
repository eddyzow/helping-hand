# Steady Hand: the contract between the controller and the dashboard (version 2)

Written Sat Nov 14 after the first test with a real hand. Three lanes build against this file at
the same time: the controller (`steady.py`, `core/tremor.py`), the dashboard page
(`steady_dashboard.html`) and the 3D view (`dashboard/arm3d.js`). If a lane needs something that is
not here, it says so in its report; it does not invent a field.

## What the first real test showed (the problems this version fixes)

1. **The arm "died".** The loop stopped after 283 s with hold on. The person did not know hold was on, and nothing on screen said why the arm had stopped following. Every state that stops the arm must be shown in words, large.
2. **The follower does not reach as far as the hand moves.** Partly the follower's elbow limit (about +65 degrees, see `newcontext.md`), partly that people with a tremor move through a small range anyway. Fix: motion scaling ("sensitivity") about a neutral pose, set per user.
3. **The 3D arm went through the table.** The drawing used joint angles without the elbow's 30 degree zero shift, so the drawn arm was in the wrong pose. The real robot meshes and correct poses replace the stick figure.
4. **The grip was all-or-nothing.** The latch needed the trigger's full travel and jumped between fully open and fully shut. Wanted: the claw closes as far as the hand squeezes, **stays there when the hand relaxes**, tightens further on the next small squeeze, and opens when the hand opens wide (or on a spoken or pressed "let go").
5. **It felt slow.** The 2 Hz filter lags about 0.16 s. Wanted: a higher cut-off plus a notch on the measured tremor frequency, so intended movement arrives sooner and the shake is still removed.
6. **The page looked generic.** Wanted: a clinical, medical-device look, the real robot in 3D, per-user calibration from the page, and a clear view of the session's activities and measurements.

## Commands (`GET /cmd?<url-encoded line>` or one text line to TCP port 8765; the reply is JSON with `ok`)

| Line | Effect |
|---|---|
| `filter on` / `filter off` | The with/without comparison. `off` lets the shake through. Never sent by voice. |
| `steady on` / `steady off` | Spoken form: `on` = filter on and follow; `off` = freeze (hold). |
| `hold on` / `hold off`, `stop` | Freeze all six joints / follow again. `stop` always freezes. |
| `cutoff <Hz>` | Filter cut-off, 0.5 to 8. Higher follows sooner, removes less. |
| `gain <x>` | Motion scale ("sensitivity"), 1.0 to 3.0: the arm moves x times as far as the hand, about the neutral pose. |
| `neutral` | The hand's pose now becomes the neutral pose that scaling works about. |
| `grip hold on` / `grip hold off` | Grip-hold mode (on by default): the claw keeps the tightest squeeze until released. Off: the claw copies the trigger. |
| `grip release` | Open the claw (the "let go"). |
| `user <name>` | Switch to (or create) a user profile. Names: letters, digits, space, dash; up to 24 characters. |
| `calibrate` / `calibrate cancel` | Start or cancel the user calibration (below). The arm is held while it runs. |
| `test` | The 10 second hold-still test. |
| `voice {"heard": "...", "said": "..."}` | RobTop's voice script reporting, for the page. |

## User calibration (what `calibrate` does)

1. **Rest, 3 seconds:** the person holds the leader still in a comfortable pose, hand relaxed. This becomes the neutral pose and the trigger's resting position.
2. **Move, 12 seconds:** the person moves every joint as far as is comfortable, squeezes the trigger as far as is comfortable, and opens the hand wide.
3. The controller stores, per user: the neutral pose, each joint's comfortable range, the trigger's rest / squeezed / open positions, and a gain per joint = (the range the robot should cover) / (the range the person covered), limited to 1.0 to 3.0.
4. Profiles are saved in `poses/steady_users.json` and reloaded at start. `default` always exists (gain 1.0, trigger rest 43, squeezed 0, open 100).

## `/state` (polled about ten times a second; every key below may be missing on an older controller, so the page degrades to an empty state)

Existing keys, unchanged: `steady`, `hold`, `cutoff`, `t`, `tremor_mm`, `tremor_hz`, `out_mm`, `removed_pct`, `grip_effort`, `arm_load`, `speed_mm_s`, `leader[6]`, `follower[6]` (measured), `history`, `trend`, `raw_chain`, `out_chain`, `test`, `insights`, `voice`.

New keys:

```json
{
  "why_still": "holding" | "calibrating" | "easing" | "limit" | "",
  "gain": 1.5,
  "user": {"name": "default", "names": ["default", "Sam"], "calibrated": false,
           "gains": [1.0, 1.0, 1.0, 1.0, 1.0],
           "range_deg": [0, 0, 0, 0, 0],
           "trigger": {"rest": 43.0, "squeezed": 0.0, "open": 100.0}},
  "calibration": {"phase": "idle" | "rest" | "move" | "done", "seconds_left": 0.0,
                  "seen": [0.0, 0.0, 0.0, 0.0, 0.0], "trigger_seen": 0.0, "insufficient": []},
  "grip": {"hold": true, "squeeze_pct": 0, "held_pct": 0, "claw_pct": 60},
  "limits": ["elbow_flex"],
  "table_z": -2.4,
  "robot": [{"mesh": "upper_arm_so101_v1.stl", "body": "upper_arm", "pos": [0, 0, 0], "quat": [1, 0, 0, 0], "rgba": [1, 1, 1, 1]}],
  "hand": [{"mesh": "upper_arm_so101_v1.stl", "body": "upper_arm", "pos": [0, 0, 0], "quat": [1, 0, 0, 0], "rgba": [1, 1, 1, 1]}],
  "activities": [{"id": "hold_still", "title": "Hold still", "unit": "score", "last": 74, "best": 81, "runs": 3,
                  "detail": "10 seconds; 100 means no shake. A display scale, not a clinical measure."}]
}
```

- `why_still`: why the arm is not following right now, or `""`. The page shows it in words.
- `user.gains`, `user.range_deg`, `calibration.seen`: one value per arm joint, in the order shoulder turn, shoulder lift, elbow, wrist bend, wrist roll. `seen` is 0 to 1: how much of a useful range has been covered so far.
- `grip.squeeze_pct`: how far the hand is squeezing now. `held_pct`: the squeeze being kept. `claw_pct`: the follower's measured claw opening, 0 shut to 100 open.
- `calibration.insufficient`: after a calibration, what the person barely moved (under 5 degrees for a joint, under 5 trigger units for the squeeze or the opening); those keep gain 1.0 / the default trigger position. Names as in `limits`, plus `trigger squeeze`, `trigger open`.
- `limits`: joints the follower cannot follow further right now (its own limits), by motor name: `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`.
- `robot` and `hand`: one entry per VISUAL mesh geom of the SO-101 model (geom group 2, 18 of them; the group 4 collision meshes are not sent), with its position (mm) and rotation (unit quaternion w, x, y, z) in the robot's frame: x forward, y to the robot's left, z up. `robot` is the follower as MEASURED (the claw joint included); `hand` is the leader, in the follower's terms. Details:
  1. The pose is the STL file's own frame, not MuJoCo's recentred one: R = geom_xmat · quat2mat(mesh_quat[mesh])ᵀ, pos = geom_xpos − R · mesh_pos[mesh]. The STL files are in metres (the model applies no mesh scale); `pos` is in mm, so the viewer scales the mesh by 1000.
  2. `rgba` is the geom's material colour when it has a material, else the geom's own rgba.
  3. `body` (optional) is the MuJoCo body the mesh belongs to.
  4. The real elbow's zero is 30 degrees off the model's (model elbow = real elbow − 30); the controller applies it, the viewer does not.
- `table_z`: the height of the table top in that frame, mm: −2.4, the underside of the base in the model.
- `GET /meshes/<name>.stl` serves the mesh files (binary STL); `GET /meshes/index.json` lists them.
- `activities`: what was done this session and before, measured. The ids that exist: `hold_still` (the 10 s test), `range` (comfortable range of motion from the last calibration, degrees), `steady_time` (minutes with the filter on this session), `grip_hold` (longest held grip this session, seconds).

## Wording rules (a reviewer checks them)

- A prototype; tested with us shaking the leader arm on purpose, not with patients.
- Grip effort and arm load are the motors' own load readings: estimates, never "force" or "torque".
- It measures and describes. It does not diagnose, treat, or claim that anything improves a tremor.
  "Exercise" may name an activity the person does; it must not come with a claim about its effect.
- Any score is a display scale, not a clinical measure.
