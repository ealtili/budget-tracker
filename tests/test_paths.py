import os
import pytest

os.environ.setdefault("BUDGET_DATA_DIR", "/tmp/bt_test_data")

from budget_tracker.storage.paths import safe_path


def test_valid_uuid4_returns_path():
    path = safe_path("f47ac10b-58cc-4372-a567-0e02b2c3d479")
    assert path.name == "f47ac10b-58cc-4372-a567-0e02b2c3d479.json.enc"


def test_rejects_path_traversal_dotdot():
    with pytest.raises(ValueError):
        safe_path("../../etc/passwd")


def test_rejects_encoded_traversal():
    with pytest.raises(ValueError):
        safe_path("%2e%2e%2fetc%2fpasswd")


def test_rejects_null_byte():
    with pytest.raises(ValueError):
        safe_path("f47ac10b-58cc-4372-a567-0e02b2c3d479\x00evil")


def test_rejects_empty_string():
    with pytest.raises(ValueError):
        safe_path("")


def test_rejects_whitespace():
    with pytest.raises(ValueError):
        safe_path("   ")


def test_rejects_uuid_v1():
    # UUID v1 — version nibble is 1, not 4
    with pytest.raises(ValueError):
        safe_path("550e8400-e29b-11d4-a716-446655440000")


def test_rejects_uppercase_uuid():
    # Our regex requires lowercase hex
    with pytest.raises(ValueError):
        safe_path("F47AC10B-58CC-4372-A567-0E02B2C3D479")


def test_rejects_non_string():
    with pytest.raises(ValueError):
        safe_path(None)  # type: ignore[arg-type]


def test_path_is_inside_transactions_dir():
    from budget_tracker.config import TRANSACTIONS_DIR
    path = safe_path("f47ac10b-58cc-4372-a567-0e02b2c3d479")
    assert str(path).startswith(str(TRANSACTIONS_DIR.resolve()))
