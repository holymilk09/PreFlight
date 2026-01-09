"""Fixtures for validation tests using real document datasets."""

import pytest
from pathlib import Path

# Mark all tests in this directory as validation tests (skip in CI)
def pytest_collection_modifyitems(config, items):
    """Add 'validation' marker to all tests in this directory."""
    for item in items:
        if "validation" in str(item.fspath):
            item.add_marker(pytest.mark.validation)


@pytest.fixture(scope="session")
def funsd_loader():
    """Get FUNSD dataset loader (downloads on first use)."""
    try:
        from tests.fixtures.datasets import FUNSDLoader
        return FUNSDLoader()
    except ImportError as e:
        pytest.skip(f"FUNSD loader not available: {e}")


@pytest.fixture(scope="session")
def funsd_samples(funsd_loader):
    """Load all FUNSD samples (cached after first load).

    Returns list of DocumentSample objects.
    """
    try:
        samples = list(funsd_loader.load())
        if not samples:
            pytest.skip("FUNSD dataset is empty")
        return samples
    except ImportError:
        pytest.skip("datasets package not installed. Install with: pip install datasets")
    except Exception as e:
        pytest.skip(f"Failed to load FUNSD: {e}")


@pytest.fixture(scope="session")
def funsd_train_samples(funsd_samples):
    """Get only training samples from FUNSD."""
    return [s for s in funsd_samples if s.metadata.get("split") == "train"]


@pytest.fixture(scope="session")
def funsd_test_samples(funsd_samples):
    """Get only test samples from FUNSD."""
    return [s for s in funsd_samples if s.metadata.get("split") == "test"]


@pytest.fixture(scope="session")
def sroie_loader():
    """Get SROIE dataset loader (downloads on first use)."""
    try:
        from tests.fixtures.datasets.sroie_loader import SROIELoader
        return SROIELoader()
    except ImportError as e:
        pytest.skip(f"SROIE loader not available: {e}")


@pytest.fixture(scope="session")
def sroie_samples(sroie_loader):
    """Load all SROIE samples (cached after first load).

    Returns list of DocumentSample objects.
    """
    try:
        samples = list(sroie_loader.load())
        if not samples:
            pytest.skip("SROIE dataset is empty")
        return samples
    except ImportError:
        pytest.skip("datasets package not installed. Install with: pip install datasets")
    except Exception as e:
        pytest.skip(f"Failed to load SROIE: {e}")


@pytest.fixture(scope="session")
def sample_pairs(funsd_samples):
    """Generate pairs of samples for similarity testing.

    Returns list of (sample_a, sample_b, is_same_category) tuples.
    """
    import random
    random.seed(42)  # Reproducible

    pairs = []

    # Same-category pairs (all forms, so these should be similar)
    for i in range(min(50, len(funsd_samples) - 1)):
        j = random.randint(i + 1, len(funsd_samples) - 1)
        pairs.append((funsd_samples[i], funsd_samples[j], True))

    return pairs


@pytest.fixture(scope="session")
def cross_dataset_pairs(funsd_samples, sroie_samples):
    """Generate pairs across datasets for cross-type similarity testing.

    Returns list of (funsd_sample, sroie_sample) tuples.
    Forms should NOT match receipts (similarity < 0.50).
    """
    import random
    random.seed(42)

    pairs = []

    # Cross-dataset pairs (forms vs receipts - should be dissimilar)
    n_pairs = min(50, len(funsd_samples), len(sroie_samples))
    funsd_subset = random.sample(funsd_samples, n_pairs)
    sroie_subset = random.sample(sroie_samples, n_pairs)

    for f_sample, s_sample in zip(funsd_subset, sroie_subset):
        pairs.append((f_sample, s_sample))

    return pairs
