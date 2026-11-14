"""Fetch the pinned SO-101 model from MuJoCo Menagerie for the optional simulation."""

from pathlib import Path, PurePosixPath
from urllib.request import urlopen
from xml.etree import ElementTree


REVISION = "370c43965323c0944b433b202aac5058b5f907a9"
BASE_URL = f"https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{REVISION}/robotstudio_so101/"
MODEL_DIR = Path(__file__).resolve().with_name("robotstudio_so101")


def download(name: str) -> bytes:
    with urlopen(BASE_URL + name, timeout=30) as response:
        return response.read()


def main():
    xml = download("so101.xml")
    meshes = [mesh.attrib["file"] for mesh in ElementTree.fromstring(xml).findall("./asset/mesh")]
    for filename in meshes:
        path = PurePosixPath(filename)
        if path.name != filename or path.suffix != ".stl":
            raise ValueError(f"Unexpected mesh filename: {filename}")
    files = ["LICENSE", "README.md", *[f"assets/{name}" for name in meshes]]
    for name in files:
        path = MODEL_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(download(name))
    (MODEL_DIR / "so101.xml").write_bytes(xml)
    print(f"SO-101 simulation model downloaded to {MODEL_DIR}")


if __name__ == "__main__":
    main()
