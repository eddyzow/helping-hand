"""Turn one typed or spoken sentence into a skill and send it to the dispatcher.

    python voice/route.py "wave at me"     # typed
    python voice/route.py                  # speak: Enter, talk, Enter

With GEMINI_API_KEY (in .env) Gemini picks the skill from each skill's description, and hears the
audio directly. Without a key, typed text is matched on the skill's name. Gemini only chooses the
skill; the motion is the taught skill, so a slow or wrong answer cannot move the arm in a new way.

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
params.object in their own words (for example "the red brick") and leave u and v out."""


def send(command: str):
    with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s:
        s.sendall((command + "\n").encode())
        return json.loads(s.makefile().readline())


def by_keyword(text: str, skills: list[dict]) -> dict:
    text = text.lower()
    if "stop" in text:
        return {"skill": "stop"}
    for skill in skills:
        if skill["name"].replace("_", " ") in text or skill["name"].split("_")[0] in text.split():
            return {"skill": skill["name"]}
    return {"skill": None}


def by_gemini(text: str | None, audio_path: str | None, skills: list[dict]) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(timeout=20000))
    parts = []
    if audio_path:
        parts.append(types.Part.from_bytes(data=Path(audio_path).read_bytes(), mime_type="audio/wav"))
    request = f'The person said: "{text}"' if text else "The person's spoken request is in the audio."
    parts.append(PROMPT.format(request=request, skills=json.dumps(skills)))
    reply = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"), contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json"))
    return json.loads(reply.text or "null") or {"skill": None}


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
    targets, _, near = pick.locate(frame, command=thing)
    found = [{"object": label, "u": round(u, 3), "v": round(v, 3), "turn": round(turn, 1)}
             for u, v, label, turn in targets]
    if len(found) == 1 and near and len(near) == 1:  # "put it next to the car": add where to put it down
        to_u, to_v = pick.drop_spot(targets[0], near[0])
        found[0].update(to_u=round(to_u, 3), to_v=round(to_v, 3))
    return found, pick.place_problem(near)


def main() -> None:
    text = " ".join(sys.argv[1:]) or None
    skills = send("list")
    env = Path(__file__).parent.parent / ".env"
    if env.exists():  # same file see.py reads
        for line in env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())
    if "GEMINI_API_KEY" in os.environ:
        if text:
            choice = by_gemini(text, None, skills)
        else:
            import see  # the recorder lives there; needs the repo requirements installed

            choice = by_gemini(None, see.record_wav(), skills)
    elif text:
        choice = by_keyword(text, skills)
    else:
        sys.exit("Speaking needs GEMINI_API_KEY in .env. Type the request instead.")
    name, params = choice.get("skill"), choice.get("params") or {}
    if name == "stop":
        print(send("stop"))
        return
    if name not in {s["name"] for s in skills}:
        speak("I don't know how to do that.")
        return
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
        params = found[0]
    result = send(f"run {name} {json.dumps(params)}")
    print(name, params, result)
    if not result.get("ok"):
        speak("I'm busy." if result.get("reason") == "busy" else "I can't do that right now.")
    elif name == "fetch":
        speak(f"Getting {params['object']}.")


if __name__ == "__main__":
    main()
