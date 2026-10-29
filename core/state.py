import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
STATE = DATA / "state.json"


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
    fd, tmp_path = tempfile.mkstemp(
        dir=DATA, prefix=".state-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, STATE)
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
    state = load()

    item = {
        "id": len(state["items"]) + 1,
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