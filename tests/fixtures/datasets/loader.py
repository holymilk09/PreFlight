"""Base dataset loader for document extraction validation."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from src.models import BoundingBox, StructuralFeatures


@dataclass
class DocumentSample:
    """A single document sample from a dataset.

    Attributes:
        id: Unique identifier for the document
        source_dataset: Name of the source dataset (e.g., "funsd", "cord")
        features: Extracted structural features
        category: Document category/type if available
        metadata: Additional dataset-specific metadata
    """

    id: str
    source_dataset: str
    features: StructuralFeatures
    category: str | None = None
    metadata: dict = field(default_factory=dict)


class DatasetLoader(ABC):
    """Abstract base class for loading document datasets.

    Subclasses implement loading logic for specific datasets
    (FUNSD, CORD, DocLayNet, etc.) and convert annotations
    to our StructuralFeatures model.
    """

    def __init__(self, cache_dir: Path | None = None):
        """Initialize the loader.

        Args:
            cache_dir: Directory to cache downloaded datasets.
                       Defaults to tests/fixtures/datasets/cache/
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def name(self) -> str:
        """Dataset name (e.g., 'funsd', 'cord')."""
        pass

    @property
    @abstractmethod
    def size(self) -> int:
        """Number of documents in the dataset."""
        pass

    @abstractmethod
    def load(self) -> Iterator[DocumentSample]:
        """Load and yield document samples.

        Downloads the dataset if not cached.

        Yields:
            DocumentSample objects with extracted features.
        """
        pass

    @abstractmethod
    def _download(self) -> None:
        """Download the dataset to cache_dir."""
        pass

    def is_cached(self) -> bool:
        """Check if the dataset is already cached."""
        return (self.cache_dir / self.name).exists()

    def clear_cache(self) -> None:
        """Remove cached dataset files."""
        import shutil

        cache_path = self.cache_dir / self.name
        if cache_path.exists():
            shutil.rmtree(cache_path)


def compute_text_density(
    bboxes: list[BoundingBox],
    page_width: int,
    page_height: int,
) -> float:
    """Compute text density as ratio of text area to page area.

    Note: BoundingBox coordinates are normalized (0-1 range), so we
    calculate density directly from the normalized values.

    Args:
        bboxes: List of bounding boxes for text elements (normalized 0-1)
        page_width: Page width in pixels (used only if bboxes are not normalized)
        page_height: Page height in pixels (used only if bboxes are not normalized)

    Returns:
        Float between 0.0 and 1.0 representing text density.
    """
    if not bboxes:
        return 0.0

    # BoundingBox uses normalized coordinates (0-1), so width * height
    # gives us the fraction of page area covered by each box
    text_area = sum((bbox.width or 0) * (bbox.height or 0) for bbox in bboxes)

    # Cap at 1.0 (overlapping boxes can exceed page area)
    return min(text_area, 1.0)


def compute_layout_complexity(
    bboxes: list[BoundingBox],
    page_width: int,
    page_height: int,
) -> float:
    """Compute layout complexity based on element distribution.

    Complexity is higher when:
    - Elements are scattered across the page
    - Elements vary significantly in size
    - Elements overlap or are densely packed

    Args:
        bboxes: List of bounding boxes
        page_width: Page width in pixels
        page_height: Page height in pixels

    Returns:
        Float between 0.0 and 1.0 representing layout complexity.
    """
    if not bboxes or page_width <= 0 or page_height <= 0:
        return 0.0

    # Factor 1: Element count normalized
    count_factor = min(len(bboxes) / 100, 1.0)

    # Factor 2: Size variance
    areas = [(bbox.width or 0) * (bbox.height or 0) for bbox in bboxes]
    if len(areas) > 1:
        mean_area = sum(areas) / len(areas)
        variance = sum((a - mean_area) ** 2 for a in areas) / len(areas)
        max_possible_variance = (page_width * page_height) ** 2
        variance_factor = min(variance / max_possible_variance * 1000, 1.0)
    else:
        variance_factor = 0.0

    # Factor 3: Spatial distribution (using centroid spread)
    if len(bboxes) > 1:
        centroids_x = [(bbox.x + (bbox.width or 0) / 2) / page_width for bbox in bboxes]
        centroids_y = [(bbox.y + (bbox.height or 0) / 2) / page_height for bbox in bboxes]

        spread_x = max(centroids_x) - min(centroids_x) if centroids_x else 0
        spread_y = max(centroids_y) - min(centroids_y) if centroids_y else 0
        spread_factor = (spread_x + spread_y) / 2
    else:
        spread_factor = 0.0

    # Combine factors
    complexity = count_factor * 0.4 + variance_factor * 0.3 + spread_factor * 0.3
    return min(complexity, 1.0)


def detect_columns(bboxes: list[BoundingBox], page_width: int) -> int:
    """Detect number of text columns based on x-coordinate clustering.

    Args:
        bboxes: List of bounding boxes
        page_width: Page width in pixels

    Returns:
        Estimated number of columns (1-4).
    """
    if not bboxes or page_width <= 0:
        return 1

    # Get left edges of all boxes, normalized to page width
    left_edges = sorted([bbox.x / page_width for bbox in bboxes])

    if len(left_edges) < 3:
        return 1

    # Simple column detection: count distinct clusters of left edges
    # Using gap threshold of 20% page width
    gap_threshold = 0.20
    columns = 1

    for i in range(1, len(left_edges)):
        if left_edges[i] - left_edges[i - 1] > gap_threshold:
            columns += 1
            if columns >= 4:
                break

    return min(columns, 4)


def detect_header_footer(
    bboxes: list[BoundingBox],
    page_height: int,
    threshold: float = 0.1,
) -> tuple[bool, bool]:
    """Detect presence of header and footer regions.

    Args:
        bboxes: List of bounding boxes
        page_height: Page height in pixels
        threshold: Fraction of page height to consider as header/footer zone

    Returns:
        Tuple of (has_header, has_footer).
    """
    if not bboxes or page_height <= 0:
        return False, False

    header_zone = page_height * threshold
    footer_zone = page_height * (1 - threshold)

    has_header = any(bbox.y < header_zone for bbox in bboxes)
    has_footer = any(bbox.y + (bbox.height or 0) > footer_zone for bbox in bboxes)

    return has_header, has_footer
