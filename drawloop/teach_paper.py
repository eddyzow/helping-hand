"""Teach a 2 by 2 paper grid by hand, saving each pose with a keypad key instead of Enter.
Arm joints are limp, the claw keeps squeezing the pen. Writes poses/paper.json in the drawing checkout.
The stop key cancels and saves nothing. The motors are left exactly as they are at the end."""
import tkinter as tk
import json, os, queue, socketserver, subprocess, sys, threading, time, winsound

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo root
os.environ.update(FOLLOWER_PORT="COM3", ARM_NO_PROMPT="1")
sys.path.insert(0, WT)
import arm  # Eddy's root arm.py

ARM_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
CORNERS = ["far left", "far right", "near left", "near right"]
keys = queue.Queue()


def say(text):
    print("SAY:", text, flush=True)
    subprocess.Popen(["powershell", "-NoProfile", "-Command",
                      f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"],
                     creationflags=subprocess.CREATE_NO_WINDOW)


class Keys(socketserver.StreamRequestHandler):
    def handle(self):
        for raw in self.rfile:
            line = raw.decode(errors="replace").strip()
            if line in ("key down", "run gesture"):
                keys.put("save")
            elif line == "stop":
                keys.put("stop")
            try:  # never "ok": the listener would then start a Geometry Dash replay
                self.wfile.write(b'{"ok": false, "reason": "teaching the paper"}\n')
            except OSError:
                return


socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.daemon_threads = True
server = socketserver.ThreadingTCPServer(("127.0.0.1", 8765), Keys)
threading.Thread(target=server.serve_forever, daemon=True).start()

robot = arm.follower()
robot.config.disable_torque_on_disconnect = False
bus = robot.bus
bus.sync_read = (lambda read: lambda *a, **k: read(*a, **{**k, "num_retry": 12}))(bus.sync_read)
bus.write("Torque_Limit", "gripper", 300, normalize=False, num_retry=8)
bus.write("Goal_Position", "gripper", 2111, normalize=False, num_retry=8)
bus.disable_torque(ARM_JOINTS, num_retry=8)

root = tk.Tk(); root.title('Teach the paper'); root.attributes('-topmost', True); root.geometry('1000x420+100+100'); root.protocol('WM_DELETE_WINDOW', lambda: None)
label = tk.Label(root, font=('Segoe UI', 44, 'bold'), wraplength=960, fg='white', bg='#223'); label.pack(fill='both', expand=True)
def show(text, bg='#223'):
    label.config(text=text, bg=bg); root.update()
grid, last, began = {"n": 2, "down": [], "up": []}, 0.0, time.time()
prev = [arm.read_pose(robot)[j + ".pos"] for j in ARM_JOINTS[:4]]
try:
    for layer, how in (("down", "pen tip touching the paper"), ("up", "pen lifted two centimetres")):
        for corner in CORNERS:
            step = len(grid['down']) + len(grid['up']) + 1
            say(f"{corner}, {how}. Hold still.")
            show(f"{step} of 8\n{corner.upper()}\n{how}\nhold still 3 seconds, or press a pad key")
            ref, t0, moved = None, 0.0, False
            while True:  # save when the arm has moved to a new place and then stayed still for 2 seconds
                now, p = time.time(), arm.read_pose(robot)
                v = [p[j + '.pos'] for j in ARM_JOINTS[:4]]
                if now - began > 600:
                    raise queue.Empty
                moved = moved or max(abs(a - b) for a, b in zip(v, prev)) > 2.0
                if ref is None or max(abs(a - b) for a, b in zip(v, ref)) > 1.5:
                    ref, t0 = v, now
                elif moved and now - t0 > 3.0:
                    break
                try:
                    event = keys.get_nowait()
                    if event == 'stop':
                        raise KeyboardInterrupt
                    if now - last > 1.0:
                        break
                except queue.Empty:
                    pass
                root.update()
                time.sleep(0.1)
            prev, began = v, time.time()
            pose = arm.read_pose(robot)
            if not all(v == v and abs(v) < 400 for v in pose.values()):
                raise ValueError(f"bad reading {pose}")
            last = time.time()
            grid[layer].append(pose)
            show(f"SAVED {step} of 8", '#070'); winsound.Beep(1200, 150); time.sleep(1.2)
            print(layer, corner, {k[:-4]: round(v, 1) for k, v in pose.items()}, flush=True)
    out = os.path.join(WT, "poses", "paper_2x2.json")
    with open(out, "w") as f:
        json.dump(grid, f, indent=1)
    say("Saved. Keep holding the arm, or rest it."); show('ALL 8 SAVED\nrest the arm', '#070')
    print("SAVED", out, flush=True)
except KeyboardInterrupt:
    say("Cancelled. Nothing saved.")
    print("CANCELLED", flush=True)
except queue.Empty:
    print("TIMEOUT: no key for ten minutes, nothing saved", flush=True)
finally:
    time.sleep(4)
    robot.disconnect()
