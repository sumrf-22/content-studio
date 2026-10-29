"""Orin: publish the approved item.

Only the ``mock`` publisher is implemented. It writes a self-contained JSON
package into ``<data>/published/`` and never calls Instagram. Any other
publisher value is refused, so a misconfigured deployment cannot claim an item
was published when nothing left the machine.
"""

import json

from config import PUBLISHER
from core.state import DATA

SUPPORTED_PUBLISHERS = {"mock"}
PUBLISH_DISABLED_MESSAGE = (
    "publisher {mode!r} is not available: real Meta Graph publishing is "
    "disabled until the Instagram account and Meta app are confirmed. "
    "Use CONTENT_STUDIO_PUBLISHER=mock (the default) to save a local package."
)


class PublishError(RuntimeError):
    """Raised when publishing is requested but no supported publisher exists."""


def describe():
    """Return metadata for the configured publisher, or raise PublishError."""
    mode = (PUBLISHER or "mock").strip().lower()
    if mode not in SUPPORTED_PUBLISHERS:
        raise PublishError(PUBLISH_DISABLED_MESSAGE.format(mode=mode))
    return {
        "mode": "mock",
        "target": "local",
        "message": "Saved locally (mock publisher; no Instagram API call).",
    }


def run(item):
    """Write the local publish package for ``item`` into ``<data>/published``.

    The publish metadata is attached to ``item`` before the snapshot is written,
    so the package records how it was published. The caller is responsible for
    saving the returned item to state.
    """
    result = describe()
    item["publish"] = result

    out = DATA / "published"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"item_{item['id']}.json").write_text(
        json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result
