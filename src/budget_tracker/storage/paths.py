import re
from pathlib import Path

from budget_tracker.config import TRANSACTIONS_DIR

# Strict UUID4 pattern — structurally rejects "../", null bytes, whitespace, etc.
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def safe_path(user_id: str) -> Path:
    """Return the encrypted transaction file path for *user_id* after strict validation.

    Raises ValueError for any input that is not a well-formed UUID4, preventing
    path traversal attacks before the filesystem is ever touched.
    """
    if not isinstance(user_id, str) or not _UUID4_RE.match(user_id):
        raise ValueError(f"Invalid user_id: {user_id!r}")

    base = TRANSACTIONS_DIR.resolve()
    candidate = (base / f"{user_id}.json.enc").resolve()

    # Second-layer defence: resolved path must remain inside TRANSACTIONS_DIR.
    # Path.relative_to() raises ValueError if candidate escapes base.
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError("Path traversal attempt detected")

    return candidate
