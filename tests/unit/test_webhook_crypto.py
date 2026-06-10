"""Unit tests for webhook secret encryption at rest (src/security.py)."""

import hmac

from src.security import (
    _WEBHOOK_ENC_PREFIX,
    decrypt_secret,
    encrypt_secret,
)
from src.services.alerting import sign_payload


class TestWebhookSecretEncryption:
    def test_round_trip(self):
        plaintext = "s3cr3t-" + "a" * 32
        stored = encrypt_secret(plaintext)
        assert stored.startswith(_WEBHOOK_ENC_PREFIX)
        assert stored != plaintext  # not stored in the clear
        assert decrypt_secret(stored) == plaintext

    def test_ciphertext_is_nondeterministic(self):
        # Fernet includes a random IV/timestamp, so two encryptions differ.
        assert encrypt_secret("same") != encrypt_secret("same")

    def test_legacy_plaintext_passthrough(self):
        # Rows written before encryption (no prefix) must still be readable.
        assert decrypt_secret("legacy_plaintext_secret") == "legacy_plaintext_secret"

    def test_signing_works_through_encryption(self):
        # The HMAC computed from the decrypted secret matches one computed from
        # the original plaintext — i.e. delivery signatures stay valid.
        plaintext = "whk_" + "b" * 40
        stored = encrypt_secret(plaintext)
        body = b'{"event":"x"}'
        ts = "1700000000"
        sig_via_store = sign_payload(decrypt_secret(stored), body, ts)
        sig_via_plain = sign_payload(plaintext, body, ts)
        assert hmac.compare_digest(sig_via_store, sig_via_plain)
