import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file():
    if not ENV_FILE.exists():
        return

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


# Keys come ONLY from the environment. No hardcoded defaults, so secrets
# never ship in source. Without a key the app runs in MOCK_MODE (no real
# API calls are attempted).
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
BRAND_NAME = os.getenv("BRAND_NAME", "My Brand")


MOCK_MODE = not bool(OPENROUTER_API_KEY)
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")

# Optional shared secret for non-localhost use. Empty means "local only", which
# is the supported default; run.py refuses to bind a non-loopback address
# without it.
ACCESS_TOKEN = os.getenv("CONTENT_STUDIO_TOKEN", "").strip()

