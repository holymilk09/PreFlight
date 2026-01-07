"""Security utilities for API key hashing and validation."""

import hashlib
import secrets
from typing import NamedTuple

from src.config import settings


class APIKeyComponents(NamedTuple):
    """Components of a generated API key."""

    full_key: str  # The full API key (only shown once at creation)
    key_prefix: str  # First 8 chars for identification
    key_hash: str  # SHA256 hash for storage


def generate_api_key() -> APIKeyComponents:
    """Generate a new API key with prefix and hash.

    The full key is in the format: cp_<random_32_hex>
    - Prefix 'cp_' identifies it as a Control Plane key
    - Random part is 32 hex characters (128 bits of entropy)

    Returns:
        APIKeyComponents with full_key, key_prefix, and key_hash.
        Only full_key should be shown to the user (once).
        key_prefix and key_hash are stored in the database.
    """
    # Generate random bytes and convert to hex
    random_part = secrets.token_hex(16)  # 32 hex chars
    full_key = f"cp_{random_part}"

    # Prefix is first 8 characters for identification (cp_xxxxx)
    key_prefix = full_key[:8]

    # Hash the full key with salt for storage
    key_hash = hash_api_key(full_key)

    return APIKeyComponents(
        full_key=full_key,
        key_prefix=key_prefix,
        key_hash=key_hash,
    )


def hash_api_key(api_key: str) -> str:
    """Hash an API key with salt for secure storage.

    Uses SHA256 with a per-deployment salt to prevent
    rainbow table attacks even if database is compromised.

    Args:
        api_key: The plain API key to hash.

    Returns:
        64-character lowercase hex SHA256 hash.
    """
    # Combine key with salt
    salted = f"{settings.api_key_salt}:{api_key}"

    # SHA256 hash
    hash_bytes = hashlib.sha256(salted.encode("utf-8")).digest()

    return hash_bytes.hex()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        api_key: The plain API key to verify.
        stored_hash: The hash from the database.

    Returns:
        True if the key matches, False otherwise.
    """
    computed_hash = hash_api_key(api_key)
    return secrets.compare_digest(computed_hash, stored_hash)


def generate_request_id() -> str:
    """Generate a unique request ID for tracing.

    Returns:
        UUID-like hex string for request tracking.
    """
    return secrets.token_hex(16)


def sanitize_for_log(data: dict) -> dict:
    """Sanitize sensitive data before logging.

    Removes or masks sensitive fields like API keys,
    passwords, and tokens.

    Args:
        data: Dictionary that may contain sensitive data.

    Returns:
        Copy of data with sensitive values masked.
    """
    sensitive_keys = {
        "password",
        "api_key",
        "api-key",
        "authorization",
        "token",
        "secret",
        "key_hash",
        "jwt",
    }

    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                # Show first 4 chars only
                result[key] = f"{value[:4]}...REDACTED"
            else:
                result[key] = "REDACTED"
        elif isinstance(value, dict):
            result[key] = sanitize_for_log(value)
        else:
            result[key] = value

    return result
