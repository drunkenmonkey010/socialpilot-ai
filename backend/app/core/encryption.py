from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import settings


def get_token_cipher() -> Fernet:
    """
    Return the Fernet cipher used for OAuth token encryption.

    The encryption key is loaded from TOKEN_ENCRYPTION_KEY.
    """

    try:
        return Fernet(
            settings.token_encryption_key.encode("utf-8")
        )
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is invalid. "
            "Generate a valid Fernet key with "
            "Fernet.generate_key()."
        ) from exc


def encrypt_token(token: str | None) -> str | None:
    """Encrypt an OAuth token before persistence."""

    if token is None:
        return None

    if not token:
        return token

    cipher = get_token_cipher()

    return cipher.encrypt(
        token.encode("utf-8")
    ).decode("utf-8")


def decrypt_token(token: str | None) -> str | None:
    """
    Decrypt a persisted OAuth token.

    Existing plaintext tokens are returned unchanged so that
    already-connected accounts continue to work during the
    encryption migration. Newly written values are encrypted.
    """

    if token is None:
        return None

    if not token:
        return token

    cipher = get_token_cipher()

    try:
        return cipher.decrypt(
            token.encode("utf-8")
        ).decode("utf-8")
    except InvalidToken:
        # Backwards compatibility for tokens that were stored
        # before encryption was introduced.
        return token


class EncryptedToken(TypeDecorator[str]):
    """
    SQLAlchemy type that transparently encrypts OAuth tokens
    before database writes and decrypts them after reads.

    The database therefore stores ciphertext while application
    code continues to work with normal plaintext token strings.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: str | None,
        dialect,
    ) -> str | None:
        return encrypt_token(value)

    def process_result_value(
        self,
        value: str | None,
        dialect,
    ) -> str | None:
        return decrypt_token(value)