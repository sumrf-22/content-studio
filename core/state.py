import contextlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

DATA = Path(
    os.environ.get("CONTENT_STUDIO_DATA_DIR")
    or (Path(__file__).resolve().parent.parent / "data")
).resolve()
DATA.mkdir(parents=True, exist_ok=True)
STATE = DATA / "state.json"

# Flask's development server is threaded, so a save can race a concurrent
# read. On Windows os.replace fails with PermissionError while another thread
# holds the destination file open, so writes retry briefly instead of 500ing.
# An RLock lets a route hold the lock across load -> mutate -> save.
_SAVE_LOCK = threading.RLock()
_REPLACE_ATTEMPTS = 20
_REPLACE_DELAY = 0.05


@contextlib.contextmanager
def locked():
    """Serialize a read-modify-write cycle against other requests."""
    with _SAVE_LOCK:
        yield


def next_id(state):
    """Return an id that cannot collide with an existing item."""
    return max((item.get("id", 0) for item in state.get("items", [])), default=0) + 1


def _now():
    return datetime.now(timezone.utc).isoformat()


def load():
    if not STATE.exists():
        return {"items": [], "activity": []}

    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        # Empty or corrupt state file (e.g. interrupted/partial write): fall
        # back to an empty store so the Flask app never crashes on state.json.
        return {"items": [], "activity": []}

    # Guard against valid JSON that is not the expected shape (e.g. a stray
    # list or string left behind by an earlier bug).
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("items"), list)
        or not isinstance(data.get("activity"), list)
    ):
        return {"items": [], "activity": []}

    return data


def save(state):
    DATA.mkdir(exist_ok=True)
    with _SAVE_LOCK:
        fd, tmp_path = tempfile.mkstemp(
            dir=DATA, prefix=".state-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())

            for attempt in range(_REPLACE_ATTEMPTS):
                try:
                    os.replace(tmp_path, STATE)
                    break
                except PermissionError:
                    if attempt == _REPLACE_ATTEMPTS - 1:
                        raise
                    time.sleep(_REPLACE_DELAY)
        except BaseException:
            # Remove the partial temp file on failure, then propagate the error.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def add_activity(state, message):
    state["activity"].insert(
        0,
        {
            "time": _now(),
            "message": message
        }
    )
    state["activity"] = state["activity"][:100]


def create_item(topic):
    with _SAVE_LOCK:
        return _create_item(topic)


def _create_item(topic):
    state = load()

    item = {
        "id": next_id(state),
        "topic": topic,
        "stage": "idea",
        "status": "pending_approval",
        "ideas": [],
        "copy": None,
        "design": None,
        "format": None,
        "published": False,
        "created_at": _now()
    }

    state["items"].insert(0, item)

    add_activity(
        state,
        f"Atlas created idea: {topic}"
    )

    save(state)

    return item