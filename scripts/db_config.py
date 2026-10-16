"""Database connection settings, read from environment variables or a local .env file."""

import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path):
    """Minimal .env reader -- avoids adding python-dotenv as a dependency."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def _require_password():
    try:
        return os.environ["GL_DB_PASSWORD"]
    except KeyError:
        raise RuntimeError(
            "GL_DB_PASSWORD is not set.\n"
            "  Set it in your environment, or copy .env.example to .env and fill it in."
        ) from None


DB_PARAMS = dict(
    dbname=os.environ.get("GL_DB_NAME", "google_local"),
    user=os.environ.get("GL_DB_USER", "postgres"),
    password=_require_password(),
    host=os.environ.get("GL_DB_HOST", "localhost"),
    port=int(os.environ.get("GL_DB_PORT", "5432")),
)

# The raw-data loaders still use literal D: paths; DATA_ROOT is not wired in yet.
PROJECT_ROOT = _PROJECT_ROOT
DATA_ROOT = os.environ.get("GL_DATA_ROOT", r"D:\google local project")
