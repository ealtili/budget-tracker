import hashlib
import hmac
import json
import os

from cryptography.fernet import Fernet, InvalidToken


def _get_key() -> bytes:
    raw = os.environ.get("APP_SECRET_KEY", "")
    if not raw:
        raise RuntimeError(
            "APP_SECRET_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return raw.encode() if isinstance(raw, str) else raw


def _get_fernet() -> Fernet:
    try:
        return Fernet(_get_key())
    except Exception as exc:
        raise RuntimeError(f"Invalid APP_SECRET_KEY: {exc}") from exc


def _compute_hmac(transactions: list, secret: bytes) -> str:
    canonical = json.dumps(transactions, sort_keys=True, ensure_ascii=False)
    return hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def encrypt_payload(payload: dict) -> bytes:
    """Sign and encrypt the payload dict. Mutates payload to embed the HMAC."""
    secret = _get_key()
    payload["hmac"] = _compute_hmac(payload.get("transactions", []), secret)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _get_fernet().encrypt(plaintext)


def decrypt_payload(ciphertext: bytes) -> dict:
    """Decrypt and verify integrity of a stored payload. Raises ValueError on failure."""
    try:
        plaintext = _get_fernet().decrypt(ciphertext)
    except InvalidToken as exc:
        raise ValueError(
            "Decryption failed — file may be corrupt or the encryption key changed."
        ) from exc

    payload = json.loads(plaintext.decode("utf-8"))
    secret = _get_key()
    stored = payload.get("hmac", "")
    expected = _compute_hmac(payload.get("transactions", []), secret)

    if not hmac.compare_digest(stored, expected):
        raise ValueError(
            "HMAC integrity check failed — transaction data may have been tampered with."
        )

    return payload
