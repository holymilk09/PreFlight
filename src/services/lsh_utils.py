"""LSH utility functions for MinHash signature generation.

MinHash creates compact signatures that preserve Jaccard similarity,
enabling O(1) approximate nearest neighbor lookup.
"""

import hashlib
import struct
from collections.abc import Sequence

from src.models import StructuralFeatures

# Number of hash functions for MinHash signature
NUM_HASHES = 128

# Large prime for hash computation
PRIME = 2**61 - 1

# Pre-computed random coefficients for hash functions
# Using deterministic seed for reproducibility
_HASH_COEFFS: list[tuple[int, int]] | None = None


def _get_hash_coefficients() -> list[tuple[int, int]]:
    """Get pre-computed hash coefficients (a, b) for MinHash.

    Uses deterministic seeding for reproducibility across restarts.
    """
    global _HASH_COEFFS
    if _HASH_COEFFS is None:
        import random
        rng = random.Random(42)  # Deterministic seed
        _HASH_COEFFS = [
            (rng.randint(1, PRIME - 1), rng.randint(0, PRIME - 1))
            for _ in range(NUM_HASHES)
        ]
    return _HASH_COEFFS


def _murmurhash3_32(data: bytes, seed: int = 0) -> int:
    """Simple MurmurHash3-like hash function.

    Uses hashlib for portability since murmurhash3 isn't in stdlib.
    """
    h = hashlib.md5(data + struct.pack('<I', seed), usedforsecurity=False)
    return struct.unpack('<I', h.digest()[:4])[0]


def features_to_shingles(features: StructuralFeatures) -> set[int]:
    """Convert structural features to a set of shingles (hashed tokens).

    Creates shingles from:
    - Quantized numeric features (bucketed)
    - Boolean features
    - Feature combinations (for locality)

    Args:
        features: Document structural features

    Returns:
        Set of integer shingle hashes
    """
    shingles = set()

    # Quantize numeric features into buckets
    # Element count: buckets of 10
    elem_bucket = features.element_count // 10
    shingles.add(_murmurhash3_32(f"elem:{elem_bucket}".encode()))

    # Table count: exact (usually small)
    shingles.add(_murmurhash3_32(f"tables:{features.table_count}".encode()))

    # Text blocks: buckets of 5
    text_bucket = features.text_block_count // 5
    shingles.add(_murmurhash3_32(f"text:{text_bucket}".encode()))

    # Image count: exact (usually small)
    shingles.add(_murmurhash3_32(f"images:{features.image_count}".encode()))

    # Page count: exact
    shingles.add(_murmurhash3_32(f"pages:{features.page_count}".encode()))

    # Text density: buckets of 0.1
    density_bucket = int(features.text_density * 10)
    shingles.add(_murmurhash3_32(f"density:{density_bucket}".encode()))

    # Layout complexity: buckets of 0.1
    complexity_bucket = int(features.layout_complexity * 10)
    shingles.add(_murmurhash3_32(f"complexity:{complexity_bucket}".encode()))

    # Column count: exact
    shingles.add(_murmurhash3_32(f"columns:{features.column_count}".encode()))

    # Boolean features
    shingles.add(_murmurhash3_32(f"header:{features.has_header}".encode()))
    shingles.add(_murmurhash3_32(f"footer:{features.has_footer}".encode()))

    # Combined features for better locality
    # Document type indicators
    if features.table_count > 0:
        shingles.add(_murmurhash3_32(b"has_tables"))
    if features.image_count > 0:
        shingles.add(_murmurhash3_32(b"has_images"))
    if features.column_count > 1:
        shingles.add(_murmurhash3_32(b"multi_column"))

    # Density + complexity combination
    dc_combo = f"dc:{density_bucket}:{complexity_bucket}"
    shingles.add(_murmurhash3_32(dc_combo.encode()))

    # Structure signature
    struct_sig = f"struct:{features.has_header}:{features.has_footer}:{features.column_count}"
    shingles.add(_murmurhash3_32(struct_sig.encode()))

    return shingles


def compute_minhash_signature(shingles: set[int]) -> tuple[int, ...]:
    """Compute MinHash signature from shingles.

    For each hash function, finds the minimum hash value across all shingles.
    This creates a compact signature that preserves Jaccard similarity.

    Args:
        shingles: Set of shingle hashes

    Returns:
        Tuple of NUM_HASHES minimum hash values
    """
    if not shingles:
        # Return max values for empty set
        return tuple([PRIME] * NUM_HASHES)

    coeffs = _get_hash_coefficients()
    signature = []

    for a, b in coeffs:
        min_hash = PRIME
        for shingle in shingles:
            # Universal hash: h(x) = (ax + b) mod p
            h = (a * shingle + b) % PRIME
            if h < min_hash:
                min_hash = h
        signature.append(min_hash)

    return tuple(signature)


def minhash_signature(features: StructuralFeatures) -> tuple[int, ...]:
    """Compute MinHash signature directly from features.

    Convenience function combining shingle generation and MinHash.

    Args:
        features: Document structural features

    Returns:
        MinHash signature tuple
    """
    shingles = features_to_shingles(features)
    return compute_minhash_signature(shingles)


def estimate_jaccard_similarity(sig1: Sequence[int], sig2: Sequence[int]) -> float:
    """Estimate Jaccard similarity from MinHash signatures.

    The fraction of matching hash values approximates Jaccard similarity.

    Args:
        sig1: First MinHash signature
        sig2: Second MinHash signature

    Returns:
        Estimated Jaccard similarity (0.0 to 1.0)
    """
    if len(sig1) != len(sig2):
        return 0.0

    matches = sum(1 for a, b in zip(sig1, sig2, strict=False) if a == b)
    return matches / len(sig1)


def signature_to_bands(signature: Sequence[int], num_bands: int = 8) -> list[tuple[int, ...]]:
    """Split signature into bands for LSH bucketing.

    Each band becomes a hash key. If any band matches between two signatures,
    they're considered candidates for similarity.

    With b bands and r rows per band:
    - Probability of becoming candidates ≈ 1 - (1 - s^r)^b
    - For b=8, r=16: ~50% at s=0.5, ~99% at s=0.85

    Args:
        signature: MinHash signature
        num_bands: Number of bands to split into

    Returns:
        List of band tuples
    """
    rows_per_band = len(signature) // num_bands
    bands = []

    for i in range(num_bands):
        start = i * rows_per_band
        end = start + rows_per_band
        bands.append(tuple(signature[start:end]))

    return bands
