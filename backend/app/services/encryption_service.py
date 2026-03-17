"""Encryption service for securely storing sensitive data like GitHub tokens."""

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_encryption_key() -> bytes:
    """
    Derive encryption key from SECRET_KEY in settings.

    Returns:
        Fernet-compatible encryption key
    """
    # Use first 32 bytes of SECRET_KEY (Fernet requires 32 URL-safe base64-encoded bytes)
    # In production, SECRET_KEY should be at least 32 characters
    key = settings.SECRET_KEY.encode('utf-8')

    # Pad or truncate to 32 bytes, then base64 encode
    if len(key) < 32:
        key = key.ljust(32, b'0')
    else:
        key = key[:32]

    # Convert to Fernet-compatible format (URL-safe base64)
    import base64
    return base64.urlsafe_b64encode(key)


def encrypt_token(token: str) -> str:
    """
    Encrypt a token (like GitHub personal access token) for secure storage.

    Args:
        token: Plain text token to encrypt

    Returns:
        Encrypted token as string (base64 encoded)
    """
    if not token:
        return ""

    key = _get_encryption_key()
    fernet = Fernet(key)
    encrypted_bytes = fernet.encrypt(token.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an encrypted token back to plain text.

    Args:
        encrypted_token: Encrypted token string (base64 encoded)

    Returns:
        Decrypted plain text token

    Raises:
        Exception: If decryption fails (invalid token or wrong key)
    """
    if not encrypted_token:
        return ""

    key = _get_encryption_key()
    fernet = Fernet(key)
    decrypted_bytes = fernet.decrypt(encrypted_token.encode('utf-8'))
    return decrypted_bytes.decode('utf-8')
