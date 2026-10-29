import os
import sys

# Add project to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

# Absolute paths for templates and static folders
BASE_DIR = PROJECT_DIR
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Local by default. Debug (the Werkzeug reloader and interactive debugger) is
# opt-in, because the debugger allows code execution from the browser.
HOST = os.getenv("CONTENT_STUDIO_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.getenv("CONTENT_STUDIO_PORT", "8080"))
DEBUG = os.getenv("CONTENT_STUDIO_DEBUG", "").strip().lower() in {
    "1", "true", "yes", "on",
}

from config import ACCESS_TOKEN  # noqa: E402  (loads .env first)
from dashboard.app import app  # noqa: E402

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def main():
    if HOST not in LOOPBACK_HOSTS and not ACCESS_TOKEN:
        print(
            "Refusing to bind {host}: set CONTENT_STUDIO_TOKEN before exposing "
            "Content Studio beyond localhost.".format(host=HOST),
            file=sys.stderr,
        )
        return 2

    if HOST not in LOOPBACK_HOSTS:
        print(
            "WARNING: serving over plain HTTP on {host}. Use a TLS-terminating "
            "reverse proxy for anything other than a trusted network.".format(
                host=HOST
            ),
            file=sys.stderr,
        )

    print("Template dir = {0}".format(TEMPLATE_DIR))
    print("Static dir   = {0}".format(STATIC_DIR))
    print("Mode         = {0}".format("mock" if app.config.get("MOCK_MODE") else "live LLM"))
    print("Debug        = {0}".format(DEBUG))

    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=DEBUG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
