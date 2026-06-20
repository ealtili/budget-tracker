import json
import os
import re
import secrets
import stat
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt

from budget_tracker.config import USERS_FILE

_USERNAME_RE = re.compile(r"^[a-z0-9_\-]{3,32}$")
_MAX_ATTEMPTS = 5
_LOCK_SHORT    = timedelta(minutes=5)
_LOCK_LONG     = timedelta(minutes=30)

_DUMMY_HASH: bytes = bcrypt.hashpw(b"__timing_guard__", bcrypt.gensalt(rounds=12))

_TEMP_PW_CHARS = string.ascii_letters + string.digits


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read_users() -> dict:
    if not USERS_FILE.exists():
        return {"users": []}
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


def _write_users(data: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        os.chmod(USERS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except NotImplementedError:
        pass


def _find_user(users: list[dict], username: str) -> Optional[dict]:
    return next((u for u in users if u["username"] == username), None)


def _is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    return datetime.now(timezone.utc) < datetime.fromisoformat(locked_until)


def _get_admin_username() -> str:
    return os.environ.get("ADMIN_USERNAME", "").lower().strip()


# ── Public auth API ───────────────────────────────────────────────────────────

def is_admin(username: str) -> bool:
    admin = _get_admin_username()
    return bool(admin) and username.lower().strip() == admin


def register(username: str, password: str, display_name: str) -> dict:
    username = username.lower().strip()
    if not _USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 3–32 characters: lowercase letters, numbers, _ or -"
        )
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    data = _read_users()
    if _find_user(data["users"], username):
        raise ValueError("Username is already taken")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    user = {
        "user_id": str(uuid.uuid4()),
        "username": username,
        "hashed_password": hashed.decode("utf-8"),
        "display_name": (display_name.strip()[:50] or username),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "failed_login_attempts": 0,
        "locked_until": None,
        "password_reset_required": False,
    }
    data["users"].append(user)
    _write_users(data)
    return user


def login(username: str, password: str) -> Optional[dict]:
    username = username.lower().strip()
    data = _read_users()
    user = _find_user(data["users"], username)

    check_hash = (
        user["hashed_password"].encode("utf-8") if user else _DUMMY_HASH
    )
    password_ok = bcrypt.checkpw(password.encode("utf-8"), check_hash)

    if not user or not password_ok or _is_locked(user):
        if user and not password_ok and not _is_locked(user):
            user["failed_login_attempts"] = user.get("failed_login_attempts", 0) + 1
            attempts = user["failed_login_attempts"]
            if attempts >= _MAX_ATTEMPTS:
                duration = _LOCK_LONG if attempts > _MAX_ATTEMPTS else _LOCK_SHORT
                user["locked_until"] = (
                    datetime.now(timezone.utc) + duration
                ).isoformat()
            _write_users(data)
        return None

    user["failed_login_attempts"] = 0
    user["locked_until"] = None
    _write_users(data)
    return user


def change_password(user_id: str, current_password: str, new_password: str) -> None:
    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters")

    data = _read_users()
    user = next((u for u in data["users"] if u["user_id"] == user_id), None)
    if not user:
        raise ValueError("User not found")
    if not bcrypt.checkpw(
        current_password.encode("utf-8"), user["hashed_password"].encode("utf-8")
    ):
        raise ValueError("Current password is incorrect")

    user["hashed_password"] = bcrypt.hashpw(
        new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")
    user["password_reset_required"] = False
    _write_users(data)


def set_new_password(user_id: str, new_password: str) -> None:
    """Set a new password without verifying the old one — only for forced-reset flow."""
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters")

    data = _read_users()
    user = next((u for u in data["users"] if u["user_id"] == user_id), None)
    if not user:
        raise ValueError("User not found")

    user["hashed_password"] = bcrypt.hashpw(
        new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")
    user["password_reset_required"] = False
    _write_users(data)


def delete_account(user_id: str, username_confirm: str) -> None:
    data = _read_users()
    user = next((u for u in data["users"] if u["user_id"] == user_id), None)
    if not user:
        raise ValueError("User not found")
    if user["username"] != username_confirm.lower().strip():
        raise ValueError("Username confirmation does not match")
    data["users"] = [u for u in data["users"] if u["user_id"] != user_id]
    _write_users(data)


# ── Admin API ─────────────────────────────────────────────────────────────────

def admin_list_users() -> list[dict]:
    """Return all non-admin users (sensitive fields excluded)."""
    admin_name = _get_admin_username()
    data = _read_users()
    return [
        {
            "user_id":                u["user_id"],
            "username":               u["username"],
            "display_name":           u["display_name"],
            "created_at":             u.get("created_at", ""),
            "failed_login_attempts":  u.get("failed_login_attempts", 0),
            "locked_until":           u.get("locked_until"),
            "password_reset_required": u.get("password_reset_required", False),
        }
        for u in data["users"]
        if u["username"] != admin_name
    ]


def admin_reset_user_password(target_username: str) -> str:
    """Reset a user's password and force a change on next login.

    Returns the one-time temporary password to relay to the user.
    """
    data = _read_users()
    user = _find_user(data["users"], target_username.lower().strip())
    if not user:
        raise ValueError(f"User '{target_username}' not found")

    temp_pw = "".join(secrets.choice(_TEMP_PW_CHARS) for _ in range(12))
    user["hashed_password"] = bcrypt.hashpw(
        temp_pw.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")
    user["password_reset_required"] = True
    user["failed_login_attempts"] = 0
    user["locked_until"] = None
    _write_users(data)
    return temp_pw


def admin_delete_user(target_username: str) -> str:
    """Delete a user. Returns the deleted user's user_id."""
    admin_name = _get_admin_username()
    target = target_username.lower().strip()
    if target == admin_name:
        raise ValueError("Admin cannot delete their own account")

    data = _read_users()
    user = _find_user(data["users"], target)
    if not user:
        raise ValueError(f"User '{target_username}' not found")

    user_id = user["user_id"]
    data["users"] = [u for u in data["users"] if u["username"] != target]
    _write_users(data)
    return user_id
