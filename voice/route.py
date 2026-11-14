"""Turn one typed or spoken sentence into a skill and send it to the dispatcher.

    python voice/route.py "wave at me"     # typed
    python voice/route.py                  # speak: Enter, talk, Enter

With ANTHROPIC_API_KEY (in .env) Claude picks the skill from each skill's description; speech is
written down first by OpenAI (OPENAI_API_KEY). The model only chooses the skill and its settings; the motion is the taught skill, so a slow or wrong answer cannot move the arm in a new way.

Fetch ("bring me the red brick") also needs the camera, which this script owns because the
dispatcher runs in WSL and has none. Run this script where the camera and microphone are
(Windows on the arm laptop). It finds the object with see.py, turns the pixel into a position
on the taught grid with pick.py, and passes that to the fetch skill. Set up the grid corners
once with: python pick.py --corners
The arm must be at home when this looks, so home has to leave the table in the camera's view.
"""
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
PORT = int(os.environ.get("BUDDY_PORT", "8765"))

PROMPT = """You route a request to one skill of a desk robot arm.
{request}
Skills: {skills}
Return only JSON: {{"skill": "<name>", "params": {{}}}}. Use "stop" as the skill if the person wants
the arm to stop. Use null if no skill fits. For fetch, put what the person asked for in
params.object in their own words (for example "the red brick") and leave u and v out; if they say how
long to hold it up, put the seconds in params.hold. For draw, put a thing to sketch in params.what ("a cat"), or a word to write in params.text."""


def send(command: str):
    with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s:
        s.sendall((command + "\n").encode())
        return json.loads(s.makefile().readline())


def by_model(text: str, skills: list[dict]) -> dict:
    import see

    reply = see.ask_claude(PROMPT.format(request=f'The person said: "{text}"', skills=json.dumps(skills)),
                           model=os.environ.get("ROUTER_MODEL", "claude-haiku-5-5"), max_tokens=500)
    answer = see.parse_reply(reply)
    return answer if isinstance(answer, dict) else {"skill": None}


def speak(text: str) -> None:
    """Say it out loud with the computer's own voice, and print it."""
    import subprocess

    print(text, flush=True)
    clean = "".join(c for c in text if c.isalnum() or c in " ,.?!")
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["say", clean])
        elif sys.platform == "win32":
            subprocess.Popen(["powershell", "-NoProfile", "-Command",
                              f"(New-Object -ComObject SAPI.SpVoice).Speak('{clean}')"])
    except OSError:
        pass  # no voice on this machine: the printed line is enough


def locate(thing: str) -> tuple[list[dict], str | None]:
    """Camera frame -> (every matching object's position on the taught grid, what is wrong with
    the place to put it, if anything). With one object and one place, the entry says where to put it down."""
    import cv2

    import pick
    import see

    test_image = os.environ.get("TEST_IMAGE")  # a photo instead of the camera, for testing
    frame = cv2.imread(test_image) if test_image else see.grab_frame()
    targets, _, spot, problem, lift = pick.locate(frame, command=thing)
    found = [{"object": label, "u": round(u, 3), "v": round(v, 3), "turn": round(turn, 1)}
             for u, v, label, turn in targets]
    if len(found) == 1 and lift:  # it sits on top of other pieces: grasp it up there
        found[0].update(lift=round(lift, 3))
    if len(found) == 1 and spot:  # "put it on the green brick": add where to put it down
        found[0].update(to_u=round(spot[0], 3), to_v=round(spot[1], 3), to_lift=round(spot[2], 3), to_turn=round(spot[3], 1))
    return found, problem


def main() -> None:
    text = " ".join(sys.argv[1:]) or None
    skills = send("list")
    env = Path(__file__).parent.parent / ".env"
    if env.exists():  # same file see.py reads
        for line in env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ[key.strip()] = value.strip()  # .env wins over a stale key in the shell
    if not text:
        import see  # the recorder lives there; needs the repo requirements installed

        text = see.transcribe(see.record_wav())
        if not text:
            speak("I didn't hear anything.")
            return
        print(f"Heard: {text}")
    choice = by_model(text, skills)  # no keyword matching: the model reads the sentence
    name, params = choice.get("skill"), choice.get("params") or {}
    if name == "stop":
        print(send("stop"))
        return
    if name not in {s["name"] for s in skills}:
        speak("I don't know how to do that.")
        return
    if name == "point":  # find it with the camera, as for fetch, but only its position is needed
        thing = text or params.get("object") or "the object"
        found, _ = locate(thing)
        if not found:
            speak(f"I can't see {thing}.")
            return
        if len(found) > 1:
            speak(f"I see {len(found)} of those. Which one?")
            return
        params = {key: found[0][key] for key in ("object", "u", "v")}
    if name == "fetch":
        thing = text or params.get("object") or "the object"  # the whole sentence, so "next to the car" survives
        found, problem = locate(thing)
        if not found:
            speak(f"I can't see {thing}.")
            return
        if len(found) > 1:  # never pick one silently
            speak(f"I see {len(found)} of those. Which one?")
            return
        if problem:  # asked to put it somewhere, and that place is missing or unclear: do not hand it over instead
            speak(problem)
            return
        params = {**found[0], **({"hold": params["hold"]} if "hold" in params else {})}
    if name == "draw" and params.get("what"):  # a sketch: work out the strokes here, where the model keys are
        import draw

        speak(f"Let me think how to draw {params['what']}.")
        try:
            params = {"strokes": draw.sketch(str(params["what"]))}
        except Exception as err:
            print(f"{type(err).__name__}: {str(err)[:200]}", file=sys.stderr)
            speak("I couldn't work out how to draw that.")
            return
    result = send(f"run {name} {json.dumps(params)}")
    print(name, params, result)
    if not result.get("ok"):
        speak("I'm busy." if result.get("reason") == "busy" else "I can't do that right now.")
    elif name == "fetch":
        speak(f"Getting {params['object']}.")
    elif name == "point":
        speak(f"That's the {params['object']}.")


if __name__ == "__main__":
    main()
