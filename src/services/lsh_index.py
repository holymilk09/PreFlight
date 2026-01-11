"""LSH Index for O(1) template candidate retrieval.

Uses MinHash signatures with banded LSH for approximate nearest neighbor search.
Index is stored in Redis for persistence across restarts.
"""

import json
import struct
from dataclasses import dataclass
from uuid import UUID

import structlog

from src.models import StructuralFeatures
from src.services.lsh_utils import (
    NUM_HASHES,
    estimate_jaccard_similarity,
    minhash_signature,
    signature_to_bands,
)

logger = structlog.get_logger()

# Redis key prefixes
BAND_KEY_PREFIX = "lsh:band"
SIG_KEY_PREFIX = "lsh:sig"
TEMPLATE_KEY_PREFIX = "lsh:template"

# LSH configuration
NUM_BANDS = 8
ROWS_PER_BAND = NUM_HASHES // NUM_BANDS  # 16 rows per band


@dataclass
class LSHCandidate:
    """A candidate template from LSH lookup."""

    template_id: UUID
    estimated_similarity: float


class MinHashLSH:
    """MinHash LSH index for template similarity search.

    Uses banded MinHash for O(1) candidate retrieval:
    1. Compute MinHash signature for query
    2. Split into bands and look up each band in Redis
    3. Return union of all matching template IDs

    The index is stored in Redis:
    - lsh:band:{band_idx}:{band_hash} -> set of template IDs
    - lsh:sig:{template_id} -> signature bytes
    - lsh:template:{template_id} -> template metadata

    Usage:
        lsh = MinHashLSH()
        await lsh.initialize()

        # Add template
        await lsh.add_template(template_id, tenant_id, features)

        # Query for candidates
        candidates = await lsh.query(features, k=10)
    """

    def __init__(self, num_bands: int = NUM_BANDS):
        """Initialize LSH index.

        Args:
            num_bands: Number of bands for LSH (default 8)
        """
        self.num_bands = num_bands
        self._redis = None
        self._available = False

    async def initialize(self) -> bool:
        """Initialize Redis connection for LSH index.

        Returns:
            True if Redis is available, False otherwise
        """
        try:
            from src.services.rate_limiter import get_redis_client

            self._redis = await get_redis_client()
            await self._redis.ping()
            self._available = True
            logger.info("lsh_index_initialized")
            return True
        except Exception as e:
            logger.warning("lsh_index_unavailable", error=str(e))
            self._available = False
            return False

    @property
    def available(self) -> bool:
        """Check if LSH index is available."""
        return self._available and self._redis is not None

    async def add_template(
        self,
        template_id: UUID,
        tenant_id: UUID,
        features: StructuralFeatures,
    ) -> bool:
        """Add a template to the LSH index.

        Args:
            template_id: Unique template ID
            tenant_id: Tenant ID for isolation
            features: Structural features to index

        Returns:
            True if added successfully, False if unavailable
        """
        if not self.available:
            return False

        try:
            # Compute MinHash signature
            signature = minhash_signature(features)

            # Split into bands
            bands = signature_to_bands(signature, self.num_bands)

            # Store in Redis using pipeline for efficiency
            pipe = self._redis.pipeline()

            # Add to each band bucket
            template_id_str = str(template_id)
            for band_idx, band in enumerate(bands):
                band_hash = _hash_band(band)
                band_key = f"{BAND_KEY_PREFIX}:{band_idx}:{band_hash}"
                pipe.sadd(band_key, template_id_str)

            # Store signature for similarity estimation
            sig_key = f"{SIG_KEY_PREFIX}:{template_id_str}"
            sig_bytes = _signature_to_bytes(signature)
            pipe.set(sig_key, sig_bytes)

            # Store template metadata
            meta_key = f"{TEMPLATE_KEY_PREFIX}:{template_id_str}"
            metadata = {
                "tenant_id": str(tenant_id),
                "features": features.model_dump(),
            }
            pipe.set(meta_key, json.dumps(metadata))

            await pipe.execute()

            logger.debug("lsh_template_added", template_id=str(template_id))
            return True

        except Exception as e:
            logger.error("lsh_add_failed", template_id=str(template_id), error=str(e))
            return False

    async def remove_template(self, template_id: UUID) -> bool:
        """Remove a template from the LSH index.

        Args:
            template_id: Template ID to remove

        Returns:
            True if removed successfully
        """
        if not self.available:
            return False

        try:
            template_id_str = str(template_id)

            # Get stored signature to find band keys
            sig_key = f"{SIG_KEY_PREFIX}:{template_id_str}"
            sig_bytes = await self._redis.get(sig_key)

            if sig_bytes:
                signature = _bytes_to_signature(sig_bytes)
                bands = signature_to_bands(signature, self.num_bands)

                pipe = self._redis.pipeline()

                # Remove from each band bucket
                for band_idx, band in enumerate(bands):
                    band_hash = _hash_band(band)
                    band_key = f"{BAND_KEY_PREFIX}:{band_idx}:{band_hash}"
                    pipe.srem(band_key, template_id_str)

                # Remove signature and metadata
                pipe.delete(sig_key)
                pipe.delete(f"{TEMPLATE_KEY_PREFIX}:{template_id_str}")

                await pipe.execute()

            logger.debug("lsh_template_removed", template_id=str(template_id))
            return True

        except Exception as e:
            logger.error("lsh_remove_failed", template_id=str(template_id), error=str(e))
            return False

    async def query(
        self,
        features: StructuralFeatures,
        k: int = 10,
        tenant_id: UUID | None = None,
    ) -> list[LSHCandidate]:
        """Query for similar template candidates.

        Args:
            features: Query features
            k: Maximum number of candidates to return
            tenant_id: Optional tenant filter

        Returns:
            List of LSHCandidate sorted by estimated similarity
        """
        if not self.available:
            return []

        try:
            # Compute query signature
            query_sig = minhash_signature(features)
            bands = signature_to_bands(query_sig, self.num_bands)

            # Collect candidate IDs from all bands
            candidate_ids: set[str] = set()

            pipe = self._redis.pipeline()
            for band_idx, band in enumerate(bands):
                band_hash = _hash_band(band)
                band_key = f"{BAND_KEY_PREFIX}:{band_idx}:{band_hash}"
                pipe.smembers(band_key)

            results = await pipe.execute()

            for members in results:
                if members:
                    candidate_ids.update(members)

            if not candidate_ids:
                return []

            # Filter by tenant if specified
            if tenant_id:
                tenant_str = str(tenant_id)
                filtered_ids = []
                for cid in candidate_ids:
                    meta_key = f"{TEMPLATE_KEY_PREFIX}:{cid}"
                    meta_json = await self._redis.get(meta_key)
                    if meta_json:
                        meta = json.loads(meta_json)
                        if meta.get("tenant_id") == tenant_str:
                            filtered_ids.append(cid)
                candidate_ids = set(filtered_ids)

            # Estimate similarity for each candidate
            candidates = []
            for cid in candidate_ids:
                sig_key = f"{SIG_KEY_PREFIX}:{cid}"
                sig_bytes = await self._redis.get(sig_key)
                if sig_bytes:
                    cand_sig = _bytes_to_signature(sig_bytes)
                    similarity = estimate_jaccard_similarity(query_sig, cand_sig)
                    candidates.append(
                        LSHCandidate(
                            template_id=UUID(cid),
                            estimated_similarity=similarity,
                        )
                    )

            # Sort by similarity and return top k
            candidates.sort(key=lambda c: c.estimated_similarity, reverse=True)
            return candidates[:k]

        except Exception as e:
            logger.error("lsh_query_failed", error=str(e))
            return []

    async def get_index_stats(self) -> dict:
        """Get statistics about the LSH index.

        Returns:
            Dict with index statistics
        """
        if not self.available:
            return {"available": False}

        try:
            # Count templates
            template_keys = []
            async for key in self._redis.scan_iter(f"{TEMPLATE_KEY_PREFIX}:*"):
                template_keys.append(key)

            # Count band buckets
            band_keys = []
            async for key in self._redis.scan_iter(f"{BAND_KEY_PREFIX}:*"):
                band_keys.append(key)

            return {
                "available": True,
                "num_templates": len(template_keys),
                "num_band_buckets": len(band_keys),
                "num_bands": self.num_bands,
                "rows_per_band": ROWS_PER_BAND,
            }

        except Exception as e:
            return {"available": False, "error": str(e)}

    async def clear(self) -> bool:
        """Clear all LSH index data.

        Returns:
            True if cleared successfully
        """
        if not self.available:
            return False

        try:
            # Delete all LSH keys
            for prefix in [BAND_KEY_PREFIX, SIG_KEY_PREFIX, TEMPLATE_KEY_PREFIX]:
                async for key in self._redis.scan_iter(f"{prefix}:*"):
                    await self._redis.delete(key)

            logger.info("lsh_index_cleared")
            return True

        except Exception as e:
            logger.error("lsh_clear_failed", error=str(e))
            return False


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _hash_band(band: tuple[int, ...]) -> str:
    """Hash a band tuple to a string key."""
    import hashlib

    band_bytes = struct.pack(f"<{len(band)}Q", *band)
    return hashlib.md5(band_bytes, usedforsecurity=False).hexdigest()[:16]


def _signature_to_bytes(signature: tuple[int, ...]) -> bytes:
    """Convert signature tuple to bytes for storage."""
    return struct.pack(f"<{len(signature)}Q", *signature)


def _bytes_to_signature(data: bytes) -> tuple[int, ...]:
    """Convert bytes back to signature tuple."""
    count = len(data) // 8
    return struct.unpack(f"<{count}Q", data)


# -----------------------------------------------------------------------------
# Module-level singleton
# -----------------------------------------------------------------------------

_lsh_index: MinHashLSH | None = None


async def get_lsh_index() -> MinHashLSH:
    """Get the global LSH index instance.

    Initializes on first call.
    """
    global _lsh_index
    if _lsh_index is None:
        _lsh_index = MinHashLSH()
        await _lsh_index.initialize()
    return _lsh_index
