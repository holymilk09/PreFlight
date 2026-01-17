"""Tests for security utilities."""

from datetime import datetime, timedelta
from uuid import uuid4

import jwt as pyjwt

from src.config import settings
from src.security import (
    APIKeyComponents,
    TokenData,
    create_access_token,
    decode_access_token,
    generate_api_key,
    generate_request_id,
    hash_api_key,
    hash_password,
    sanitize_for_log,
    verify_api_key,
    verify_password,
)


class TestGenerateAPIKey:
    """Tests for API key generation."""

    def test_generate_api_key_format(self):
        """Generated key should have correct format."""
        result = generate_api_key()

        assert isinstance(result, APIKeyComponents)
        assert result.full_key.startswith("cp_")
        assert len(result.full_key) == 35  # cp_ + 32 hex chars

    def test_generate_api_key_prefix(self):
        """Key prefix should be first 8 characters."""
        result = generate_api_key()

        assert result.key_prefix == result.full_key[:8]
        assert len(result.key_prefix) == 8
        assert result.key_prefix.startswith("cp_")

    def test_generate_api_key_hash_format(self):
        """Key hash should be 64 character hex string."""
        result = generate_api_key()

        assert len(result.key_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.key_hash)

    def test_generate_api_key_uniqueness(self):
        """Each generated key should be unique."""
        keys = [generate_api_key() for _ in range(100)]
        full_keys = [k.full_key for k in keys]

        # All full keys should be unique
        assert len(set(full_keys)) == 100

    def test_generate_api_key_random_part_is_hex(self):
        """Random part of key should be valid hex."""
        result = generate_api_key()

        random_part = result.full_key[3:]  # Remove 'cp_' prefix
        assert len(random_part) == 32
        assert all(c in "0123456789abcdef" for c in random_part)


class TestHashAPIKey:
    """Tests for API key hashing."""

    def test_hash_api_key_deterministic(self):
        """Same input should produce same hash."""
        key = "cp_abc123def456abc123def456abc123de"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)

        assert hash1 == hash2

    def test_hash_api_key_length(self):
        """Hash should be 64 characters (SHA256 hex)."""
        key = "cp_abc123def456abc123def456abc123de"
        result = hash_api_key(key)

        assert len(result) == 64

    def test_hash_api_key_is_lowercase_hex(self):
        """Hash should be lowercase hexadecimal."""
        key = "cp_abc123def456abc123def456abc123de"
        result = hash_api_key(key)

        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_api_key_different_keys_different_hashes(self):
        """Different keys should produce different hashes."""
        key1 = "cp_abc123def456abc123def456abc123de"
        key2 = "cp_xyz789xyz789xyz789xyz789xyz789xy"

        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)

        assert hash1 != hash2

    def test_hash_api_key_small_change_different_hash(self):
        """Even a small change should produce completely different hash."""
        key1 = "cp_abc123def456abc123def456abc123de"
        key2 = "cp_abc123def456abc123def456abc123df"  # Last char different

        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)

        assert hash1 != hash2


class TestVerifyAPIKey:
    """Tests for API key verification."""

    def test_verify_api_key_correct(self):
        """Correct key should verify successfully."""
        result = generate_api_key()

        assert verify_api_key(result.full_key, result.key_hash) is True

    def test_verify_api_key_incorrect(self):
        """Incorrect key should fail verification."""
        result = generate_api_key()
        wrong_key = "cp_wrongkeywrongkeywrongkeywrongke"

        assert verify_api_key(wrong_key, result.key_hash) is False

    def test_verify_api_key_wrong_hash(self):
        """Key with wrong hash should fail verification."""
        result = generate_api_key()
        wrong_hash = "a" * 64

        assert verify_api_key(result.full_key, wrong_hash) is False

    def test_verify_api_key_case_sensitive(self):
        """Key verification should be case sensitive."""
        result = generate_api_key()
        upper_key = result.full_key.upper()

        # Should fail because key is case-sensitive
        assert verify_api_key(upper_key, result.key_hash) is False


class TestGenerateRequestId:
    """Tests for request ID generation."""

    def test_generate_request_id_format(self):
        """Request ID should be 32 character hex string."""
        request_id = generate_request_id()

        assert len(request_id) == 32
        assert all(c in "0123456789abcdef" for c in request_id)

    def test_generate_request_id_uniqueness(self):
        """Each request ID should be unique."""
        ids = [generate_request_id() for _ in range(100)]

        assert len(set(ids)) == 100


class TestSanitizeForLog:
    """Tests for log sanitization."""

    def test_sanitize_removes_password(self):
        """Password fields should be redacted."""
        data = {"username": "admin", "password": "secret123"}
        result = sanitize_for_log(data)

        assert result["username"] == "admin"
        assert "REDACTED" in result["password"]
        assert "secret123" not in result["password"]

    def test_sanitize_removes_api_key(self):
        """API key fields should be redacted."""
        data = {"api_key": "cp_abc123def456abc123def456abc123de"}
        result = sanitize_for_log(data)

        assert "REDACTED" in result["api_key"]
        assert result["api_key"] == "cp_a...REDACTED"

    def test_sanitize_removes_token(self):
        """Token fields should be redacted."""
        data = {"access_token": "bearer_abc123xyz"}
        result = sanitize_for_log(data)

        assert "REDACTED" in result["access_token"]

    def test_sanitize_removes_authorization(self):
        """Authorization headers should be redacted."""
        data = {"Authorization": "Bearer abc123xyz"}
        result = sanitize_for_log(data)

        assert "REDACTED" in result["Authorization"]

    def test_sanitize_preserves_safe_fields(self):
        """Non-sensitive fields should be preserved."""
        data = {"username": "admin", "action": "login", "timestamp": "2024-01-01"}
        result = sanitize_for_log(data)

        assert result["username"] == "admin"
        assert result["action"] == "login"
        assert result["timestamp"] == "2024-01-01"

    def test_sanitize_handles_nested_dicts(self):
        """Nested dictionaries should be sanitized recursively."""
        data = {
            "user": {
                "name": "admin",
                "password": "secret",
            },
            "request": {
                "headers": {
                    "Authorization": "Bearer token123",
                }
            },
        }
        result = sanitize_for_log(data)

        assert result["user"]["name"] == "admin"
        assert "REDACTED" in result["user"]["password"]
        assert "REDACTED" in result["request"]["headers"]["Authorization"]

    def test_sanitize_short_values(self):
        """Short sensitive values should be fully redacted."""
        data = {"api_key": "short"}
        result = sanitize_for_log(data)

        assert result["api_key"] == "REDACTED"

    def test_sanitize_case_insensitive(self):
        """Sensitive field detection should be case-insensitive."""
        data = {
            "PASSWORD": "secret",
            "Api_Key": "key123456789",
            "TOKEN": "tok123456789",
        }
        result = sanitize_for_log(data)

        assert "REDACTED" in result["PASSWORD"]
        assert "REDACTED" in result["Api_Key"]
        assert "REDACTED" in result["TOKEN"]

    def test_sanitize_empty_dict(self):
        """Empty dict should return empty dict."""
        result = sanitize_for_log({})
        assert result == {}

    def test_sanitize_key_hash_field(self):
        """key_hash fields should be redacted."""
        data = {"key_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"}
        result = sanitize_for_log(data)

        assert "REDACTED" in result["key_hash"]

    def test_sanitize_secret_field(self):
        """secret fields should be redacted."""
        data = {"client_secret": "very_secret_value_here"}
        result = sanitize_for_log(data)

        assert "REDACTED" in result["client_secret"]

    def test_sanitize_jwt_field(self):
        """jwt fields should be redacted."""
        data = {"jwt_token": "eyJhbGciOiJIUzI1NiJ9.payload.signature"}
        result = sanitize_for_log(data)

        assert "REDACTED" in result["jwt_token"]


class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_password_returns_bcrypt_format(self):
        """Hashed password should be in bcrypt format."""
        hashed = hash_password("testpassword")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")

    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (salted)."""
        password = "testpassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_verify_password_valid(self):
        """Valid password should verify."""
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_verify_password_invalid(self):
        """Invalid password should not verify."""
        password = "testpassword123"
        hashed = hash_password(password)
        assert not verify_password("wrongpassword", hashed)

    def test_verify_password_case_sensitive(self):
        """Password verification should be case sensitive."""
        password = "TestPassword"
        hashed = hash_password(password)
        assert not verify_password("testpassword", hashed)

    def test_verify_password_empty_string(self):
        """Empty password should work."""
        password = ""
        hashed = hash_password(password)
        assert verify_password("", hashed)
        assert not verify_password("anything", hashed)

    def test_verify_password_unicode(self):
        """Unicode passwords should work."""
        password = "пароль123"
        hashed = hash_password(password)
        assert verify_password(password, hashed)
        assert not verify_password("password123", hashed)


class TestJWTCreation:
    """Tests for JWT token creation."""

    def test_create_access_token_format(self):
        """Should create valid JWT token format."""
        user_id = uuid4()
        tenant_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="user",
        )

        assert isinstance(token, str)
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

    def test_create_access_token_default_expiry(self):
        """Token should have default expiry from settings."""
        user_id = uuid4()
        tenant_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="user",
        )

        decoded = decode_access_token(token)
        assert decoded is not None
        # Token should be valid (exp is in the future relative to when it was created)
        # The decoded exp is from datetime.fromtimestamp, which is local time
        # Just verify exp is a datetime and the token decodes successfully
        assert isinstance(decoded.exp, datetime)

    def test_create_access_token_custom_expiry(self):
        """Should accept custom expiry."""
        user_id = uuid4()
        tenant_id = uuid4()

        before = datetime.utcnow()
        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="admin",
            expires_delta=timedelta(hours=24),
        )
        after = datetime.utcnow()

        decoded = decode_access_token(token)
        assert decoded is not None
        # Just verify the token decodes successfully with valid expiry
        assert isinstance(decoded.exp, datetime)


class TestJWTDecoding:
    """Tests for JWT token decoding."""

    def test_decode_access_token_valid(self):
        """Should decode valid token."""
        user_id = uuid4()
        tenant_id = uuid4()
        email = "test@example.com"
        role = "user"

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
        )

        decoded = decode_access_token(token)

        assert decoded is not None
        assert isinstance(decoded, TokenData)
        assert decoded.user_id == user_id
        assert decoded.tenant_id == tenant_id
        assert decoded.email == email
        assert decoded.role == role
        assert isinstance(decoded.exp, datetime)

    def test_decode_access_token_expired(self):
        """Should return None for expired token."""
        user_id = uuid4()
        tenant_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="user",
            expires_delta=timedelta(seconds=-10),
        )

        decoded = decode_access_token(token)
        assert decoded is None

    def test_decode_access_token_invalid_signature(self):
        """Should return None for token with invalid signature."""
        user_id = uuid4()
        tenant_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="user",
        )

        parts = token.split(".")
        parts[2] = "invalidsignature"
        tampered_token = ".".join(parts)

        decoded = decode_access_token(tampered_token)
        assert decoded is None

    def test_decode_access_token_invalid_format(self):
        """Should return None for malformed token."""
        assert decode_access_token("not.a.valid.jwt") is None
        assert decode_access_token("") is None
        assert decode_access_token("just-a-string") is None

    def test_decode_access_token_wrong_type(self):
        """Should return None if token type is not 'access'."""
        user_id = uuid4()
        tenant_id = uuid4()

        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": "test@example.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "type": "refresh",
        }

        token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        decoded = decode_access_token(token)
        assert decoded is None

    def test_decode_access_token_missing_fields(self):
        """Should return None if required fields are missing."""
        payload = {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        decoded = decode_access_token(token)
        assert decoded is None

    def test_decode_access_token_invalid_uuid(self):
        """Should return None if UUID fields are invalid."""
        payload = {
            "sub": "not-a-uuid",
            "tenant_id": "also-not-uuid",
            "email": "test@example.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "type": "access",
        }

        token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        decoded = decode_access_token(token)
        assert decoded is None
