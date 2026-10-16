"""Project outputs stay beside this checkout; raw archive paths are unchanged."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_file(relative=""):
    return str(ROOT / Path(relative.replace("\\", "/")))
