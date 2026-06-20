import os
from pathlib import Path


def _resolve_data_dir() -> Path:
    override = os.environ.get("BUDGET_DATA_DIR")
    if override:
        return Path(override).resolve()
    # Default: data/ at the project root (4 levels up from this file's package)
    return (Path(__file__).resolve().parent.parent.parent / "data").resolve()


DATA_DIR: Path = _resolve_data_dir()
TRANSACTIONS_DIR: Path = DATA_DIR / "transactions"
USERS_FILE: Path = DATA_DIR / "users.json"
