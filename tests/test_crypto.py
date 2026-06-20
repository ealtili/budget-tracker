import json
import os

import pytest
from cryptography.fernet import Fernet

# Set a fresh random key before any crypto imports
os.environ["APP_SECRET_KEY"] = Fernet.generate_key().decode()

from budget_tracker.storage.crypto import decrypt_payload, encrypt_payload


def _sample_payload() -> dict:
    return {
        "version": 1,
        "transactions": [
            {"id": "abc", "type": "expense", "amount": 10.0, "category": "Food & Drink"},
        ],
    }


def test_round_trip_preserves_transactions():
    payload = _sample_payload()
    original_txns = list(payload["transactions"])
    ciphertext = encrypt_payload(payload)
    result = decrypt_payload(ciphertext)
    assert result["transactions"] == original_txns


def test_ciphertext_is_not_plaintext():
    payload = _sample_payload()
    ciphertext = encrypt_payload(payload)
    assert b"expense" not in ciphertext


def test_fernet_tamper_raises():
    payload = _sample_payload()
    ciphertext = encrypt_payload(payload)
    # Flip some bytes near the end to break Fernet's auth tag
    tampered = bytearray(ciphertext)
    tampered[-5] ^= 0xFF
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_payload(bytes(tampered))


def test_hmac_corruption_raises():
    payload = _sample_payload()
    ciphertext = encrypt_payload(payload)

    # Decrypt legitimately, corrupt the HMAC, re-encrypt
    f = Fernet(os.environ["APP_SECRET_KEY"].encode())
    inner = json.loads(f.decrypt(ciphertext))
    inner["hmac"] = "deadbeef" * 8  # wrong but right length
    bad_cipher = f.encrypt(json.dumps(inner).encode())

    with pytest.raises(ValueError, match="HMAC"):
        decrypt_payload(bad_cipher)


def test_empty_transactions_round_trip():
    payload = {"version": 1, "transactions": []}
    ciphertext = encrypt_payload(payload)
    result = decrypt_payload(ciphertext)
    assert result["transactions"] == []


def test_missing_key_raises():
    original = os.environ.pop("APP_SECRET_KEY")
    try:
        with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
            encrypt_payload({"version": 1, "transactions": []})
    finally:
        os.environ["APP_SECRET_KEY"] = original
