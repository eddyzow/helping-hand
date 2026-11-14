"""Turn one typed or spoken sentence into a skill and send it to the dispatcher.

    python voice/route.py "wave at me"     # typed
    python voice/route.py                  # speak: Enter, talk, Enter

With GEMINI_API_KEY (in .env) Gemini picks the skill from each skill's description, and hears the
audio directly. Without a key, typed text is matched on the skill's name. Gemini only chooses the
skill; the motion is the taught skill, so a slow or wrong answer cannot move the arm in a new way.
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
the arm to stop. Use null if no skill fits."""


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
    name = choice.get("skill")
    if name == "stop":
        print(send("stop"))
    elif name in {s["name"] for s in skills}:
        print(name, send(f"run {name} {json.dumps(choice.get('params') or {})}"))
    else:
        print("No skill fits that.")


if __name__ == "__main__":
    main()
