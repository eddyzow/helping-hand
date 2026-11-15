# RobTop · Geometry Dash

MuJoCo models the SO-101 pressing the middle key of the three-key SayoDevice O3C v1. It reads a CSV of desired key-down and key-up times, then reports when each input registered and how far the middle and adjacent keys moved. Playback is timed from a level restart.

## Set up on Windows

Run these in PowerShell from the repository root with Python 3.12. Use an existing virtual environment if you already have one for this checkout.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
cd keypad\geometry_dash
```

The supplied `stereo_madness.csv` has 74 presses and releases, including holds, captured from the restart key. To test on hardware, go to [Test the follower on Windows](#test-the-follower-on-windows).

## Replay the browser clear

`stereo_madness_browser.csv` contains the 73 presses and releases from the browser recording, timed to the start of the soundtrack. With a **12 ms delay** after that cue, MuJoCo's simulated O3C inputs completed Stereo Madness in RobTop's browser demo. The first replay with a zero offset reached 63%.

```powershell
& $python -m playwright install chromium
& $python fetch_so101_model.py
& $python geo_browser_replay.py --visible
```

The replay releases Space at a crash and starts from the first event on the next attempt. It retries once by default. Check the printed path to `end-screen.png` for **Level Complete**. If it crashes, check `crash-1.png` in the new run folder under `outputs` and adjust `--offset-ms` if needed. Browser timing can vary across machines and runs.

To capture another browser run, use `& $python geo_browser_record.py`. Click Play, use Space, then release Space and press F8 on the Level Complete screen. Failed attempts are discarded automatically. Replay the result with `& $python geo_browser_replay.py --visible --pattern outputs/my_stereo_madness_browser.csv`. The follower's R-triggered desktop replay uses `stereo_madness.csv`.

## Run the simulation

Download the SO-101 model once for the simulation; the hardware test can run without it.

```powershell
& $python fetch_so101_model.py
& $python simulate.py --pattern stereo_madness.csv --press-lead-ms 12 --release-lead-ms 19 --max-error-ms 5
& $python simulate.py --view --events
& $python simulate.py --hz 4
```

The default CSV is a sample with short taps and longer holds. To check the sample with timing compensation and a 5 ms tolerance, run:

```powershell
& $python simulate.py --events --press-lead-ms 12 --release-lead-ms 19 --max-error-ms 5
```

## O3C setup

The model uses a 65 × 50 mm footprint and 20 mm key spacing. The Gateron KS-20 White switch option has 4.1 mm nominal travel and a 30 gf nominal initial force. The scene uses a linear approximation to the force curve and estimated damping, keycap height, and moving mass.

The simulation starts with fixed actuation at 0.70 mm and reset at 0.40 mm. These are test settings. Use `--actuation-mm` and `--reset-mm` to try other absolute depths. If you are testing Rapid Trigger, `--rt-press-mm` and `--rt-release-mm` set relative movement distances in the range defined by `--rt-top-mm` and `--rt-end-mm`. This is a simplified model of Rapid Trigger. Device firmware, USB timing, and the settings saved on your keypad need physical verification.

```powershell
& $python simulate.py --rapid-trigger --events --max-error-ms 5
& $python simulate.py --rapid-trigger --rt-release-mm 0.8 --events --press-lead-ms 12 --release-lead-ms 10 --max-error-ms 5
```

The first Rapid Trigger run uses a 0.40 mm upward release movement and shows early releases during holds. The second tries a larger release movement. Use the timing tolerance to catch short holds even when the event count matches.

## Record Stereo Madness

1. Use **Space** on your keyboard or a SayoDevice key mapped to Space. Check that your Geometry Dash restart key is **R**. If the game uses another letter, pass it to the recorder with `--restart`.
2. Start the recorder, focus the game, and press the restart key. Each restart key press starts a fresh recording. If you crash, press the restart key before trying again so the recording starts from a consistent cue.
3. Play using Space. Release it and press **F8** after the attempt you want to keep. The recorder saves the key-down and key-up events from that attempt, including the length of each hold.

```powershell
& $python record.py my_stereo_madness.csv
& $python simulate.py --pattern my_stereo_madness.csv --events --press-lead-ms 12 --release-lead-ms 19
```

The CSV can also be edited by hand. Its header is `time_ms,state`. Each timestamp is measured from the restart key press, and states alternate between `down` and `up`.

## Test the follower on Windows

Connect the SO-101 Pro follower's USB data cable and its 12 V supply. Plug the O3C into the same PC and secure it to the table so the wrist can press the middle key with a small movement. For the first test, turn Rapid Trigger off.

This standalone script opens the serial port from Windows. Close the team dispatcher, LeRobot, and any other arm controller first. If the adapter is attached to WSL, detach it with `usbipd detach --busid <BUSID>` so it appears as a Windows COM port. The leader can stay unplugged.

From PowerShell in this folder, list the serial ports. If the adapter is unclear, compare the list before and after plugging in the follower USB cable.

```powershell
& $python follower_replay.py ports
```

Set `$armPort` to the follower's actual port. In `teach`, support the arm and position the tip just above the middle key. Press Enter to save that position. Move only the wrist just far enough for the key to register, then press Enter again. Bring the wrist back to the released position while keeping the rest of the arm in place.

```powershell
$armPort = 'COM7'  # Replace with the USB serial port from the listing.
& $python follower_replay.py teach --port $armPort
& $python follower_replay.py test --port $armPort --jump c
```

The team's O3C middle key sends **C**, so the command above listens for C. If your middle key already sends Space, use `--jump space`. The powered test moves only the wrist, checks two short taps and one two-second hold, and prints the median press and release delays. Keep your hands clear and press **Z** on the O3C or **F8** on the keyboard to stop. The arm holds the released pose afterward. Support it before switching off power.

For the game run, make sure the O3C middle key makes the cube jump. If C is still the keypad output, bind C to jump in Geometry Dash if your version supports it, or remap the O3C middle key to Space. Start with the first five taps and enter the measured press and release delays in milliseconds. Once the script is ready, focus Stereo Madness and press the same **R** restart key used to record. **Z**, **F8**, or a second restart stops the replay.

```powershell
$pressMs = Read-Host 'Measured press delay in ms'
$releaseMs = Read-Host 'Measured release delay in ms'
& $python follower_replay.py replay --port $armPort --first-taps 5 --press-lead-ms $pressMs --release-lead-ms $releaseMs
```

Once the opening is repeatable, remove `--first-taps 5` to replay the whole CSV. The simulated timing offsets are specific to MuJoCo. The physical replay uses the measured delays and the same wrist speed as the powered test.

The arm model is from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/370c43965323c0944b433b202aac5058b5f907a9/robotstudio_so101). The 12 V servo's rated no-load speed is from [Feetech](https://files.seeedstudio.com/products/Feetech/108090003_FEETECH_ST-3215-C047-Datasheet.pdf).

The textured O3C meshes are adapted from [miniblack0662's SayoDevice Visualizer](https://github.com/mini062/SayoDevice-Visualizer/tree/11d43f3932f0cec20c3b839b2b0c2764621f1098) under the MIT license. The original O3C footprint is from the [O3C manual](https://ae01.alicdn.com/kf/S3a399b6701fe4cfd82a4514a54f08d25o.pdf), the key spacing is from a [measured O3C enclosure project](https://github.com/lucasovbetts-tech/SayoDevice-O3C-case-model/blob/main/sayodevice_case.py), and the switch specifications are from [Gateron's KS-20 White datasheet](https://gateron.com/u_file/2311/10/file/GATERONMagneticWhiteSwitch-KS-20TF10B045NW-X72.pdf).

The hardware script uses [Feetech Servo SDK](https://pypi.org/project/feetech-servo-sdk/) for the motor bus and [pynput](https://pypi.org/project/pynput/) to observe the restart, jump, and stop keys.

The browser test uses [Playwright](https://playwright.dev/python/) to run [RobTop's official Stereo Madness demo](https://geometrydash.com/game/index.html).
