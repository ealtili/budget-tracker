import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

from budget_tracker.config import TRANSACTIONS_DIR
from budget_tracker.storage.crypto import decrypt_payload, encrypt_payload
from budget_tracker.storage.paths import safe_path

SCHEMA_VERSION = 1


def _ensure_dir() -> None:
    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _read_store(user_id: str) -> dict:
    path = safe_path(user_id)
    if not path.exists():
        return {"version": SCHEMA_VERSION, "transactions": []}
    return decrypt_payload(path.read_bytes())


def _write_store(user_id: str, payload: dict) -> None:
    _ensure_dir()
    path = safe_path(user_id)
    ciphertext = encrypt_payload(payload)
    path.write_bytes(ciphertext)
    # Restrict to owner read/write only (ignored gracefully on Windows)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except NotImplementedError:
        pass


def get_transactions(user_id: str) -> list[dict]:
    return _read_store(user_id).get("transactions", [])


def add_transaction(user_id: str, txn: dict) -> dict:
    payload = _read_store(user_id)
    txn = dict(txn)
    txn["id"] = str(uuid.uuid4())
    txn["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["transactions"].append(txn)
    _write_store(user_id, payload)
    return txn


def add_transactions_bulk(user_id: str, txns: list[dict]) -> int:
    payload = _read_store(user_id)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for txn in txns:
        txn = dict(txn)
        txn["id"] = str(uuid.uuid4())
        txn["created_at"] = now
        payload["transactions"].append(txn)
    _write_store(user_id, payload)
    return len(txns)


def delete_user_store(user_id: str) -> None:
    path = safe_path(user_id)
    if path.exists():
        path.unlink()
