"""Dataset loaders for validation testing with real document data."""

from tests.fixtures.datasets.funsd_loader import FUNSDLoader
from tests.fixtures.datasets.loader import DatasetLoader, DocumentSample

__all__ = ["DatasetLoader", "DocumentSample", "FUNSDLoader"]
