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


# Legacy provider variables. Since the BYOK settings page landed, the live path
# reads `data/settings/providers.json` and these are ignored by generation.
# They are still loaded so an old `.env` keeps working instead of crashing.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
BRAND_NAME = os.getenv("BRAND_NAME", "My Brand")


MOCK_MODE = not bool(OPENROUTER_API_KEY)
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")

# Optional shared secret for non-localhost use. Empty means "local only", which
# is the supported default; run.py refuses to bind a non-loopback address
# without it.
ACCESS_TOKEN = os.getenv("CONTENT_STUDIO_TOKEN", "").strip()

# Publishing target. Only "mock" is implemented: it writes a local package into
# `<data>/published/`. Any other value is refused at publish time until the
# Instagram account and Meta app are confirmed and a real integration exists.
PUBLISHER = (os.getenv("CONTENT_STUDIO_PUBLISHER", "mock") or "mock").strip().lower()

