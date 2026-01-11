"""FUNSD dataset loader for form understanding validation.

FUNSD (Form Understanding in Noisy Scanned Documents) contains 199 real,
fully annotated, scanned forms with bounding boxes and entity labels.

Dataset: https://huggingface.co/datasets/nielsr/funsd
Paper: https://arxiv.org/abs/1905.13538
"""

import hashlib
from collections.abc import Iterator

from src.models import BoundingBox, StructuralFeatures
from tests.fixtures.datasets.loader import (
    DatasetLoader,
    DocumentSample,
    compute_layout_complexity,
    compute_text_density,
    detect_columns,
    detect_header_footer,
)


class FUNSDLoader(DatasetLoader):
    """Loader for the FUNSD dataset from Hugging Face.

    FUNSD contains 199 forms with annotations including:
    - Bounding boxes for text regions
    - Entity labels: question, answer, header, other
    - Word-level text content (not used - we only need structure)

    Example usage:
        loader = FUNSDLoader()
        for sample in loader.load():
            print(f"Document {sample.id}: {sample.features.element_count} elements")
    """

    # Standard page dimensions for FUNSD (scanned at ~150 DPI)
    DEFAULT_PAGE_WIDTH = 762
    DEFAULT_PAGE_HEIGHT = 1000

    @property
    def name(self) -> str:
        return "funsd"

    @property
    def size(self) -> int:
        return 199  # 149 train + 50 test

    def _download(self) -> None:
        """Download FUNSD from Hugging Face datasets."""
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError(
                "The 'datasets' package is required for FUNSD loading. "
                "Install with: pip install datasets"
            )

        # Download and cache
        dataset = load_dataset("nielsr/funsd", cache_dir=str(self.cache_dir / self.name))

        # Save a marker file to indicate download complete
        marker = self.cache_dir / self.name / ".downloaded"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

    def is_cached(self) -> bool:
        """Check if FUNSD is already downloaded."""
        marker = self.cache_dir / self.name / ".downloaded"
        return marker.exists()

    def load(self) -> Iterator[DocumentSample]:
        """Load FUNSD documents and extract structural features.

        Downloads the dataset if not already cached.

        Yields:
            DocumentSample objects for each form in FUNSD.
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError(
                "The 'datasets' package is required for FUNSD loading. "
                "Install with: pip install datasets"
            )

        # Load dataset (auto-downloads if needed)
        dataset = load_dataset("nielsr/funsd", cache_dir=str(self.cache_dir / self.name))

        # Mark as downloaded
        marker = self.cache_dir / self.name / ".downloaded"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

        # Process train and test splits
        for split in ["train", "test"]:
            if split not in dataset:
                continue

            for idx, item in enumerate(dataset[split]):
                yield self._process_item(item, split, idx)

    def _process_item(self, item: dict, split: str, idx: int) -> DocumentSample:
        """Convert a FUNSD item to DocumentSample.

        Args:
            item: Raw item from Hugging Face dataset
            split: Dataset split (train/test)
            idx: Index within split

        Returns:
            DocumentSample with extracted structural features.
        """
        # Extract bounding boxes from annotations
        bboxes = self._extract_bboxes(item)

        # Count entity types
        entity_counts = self._count_entities(item)

        # Compute structural features
        has_header, has_footer = detect_header_footer(bboxes, self.DEFAULT_PAGE_HEIGHT)

        features = StructuralFeatures(
            element_count=len(bboxes),
            table_count=0,  # FUNSD doesn't annotate tables
            text_block_count=entity_counts.get("total_blocks", len(bboxes)),
            image_count=0,  # FUNSD is text-only forms
            page_count=1,
            text_density=compute_text_density(
                bboxes, self.DEFAULT_PAGE_WIDTH, self.DEFAULT_PAGE_HEIGHT
            ),
            layout_complexity=compute_layout_complexity(
                bboxes, self.DEFAULT_PAGE_WIDTH, self.DEFAULT_PAGE_HEIGHT
            ),
            column_count=detect_columns(bboxes, self.DEFAULT_PAGE_WIDTH),
            has_header=has_header,
            has_footer=has_footer,
            bounding_boxes=bboxes[:50],  # Limit for storage
        )

        # Generate document ID
        doc_id = f"funsd_{split}_{idx:04d}"

        return DocumentSample(
            id=doc_id,
            source_dataset="funsd",
            features=features,
            category="form",
            metadata={
                "split": split,
                "index": idx,
                "entity_counts": entity_counts,
            },
        )

    def _extract_bboxes(self, item: dict) -> list[BoundingBox]:
        """Extract bounding boxes from FUNSD item.

        FUNSD stores bboxes in different formats depending on the
        Hugging Face dataset version. This handles both formats.
        Coordinates are normalized to 0-1 range.

        Args:
            item: Raw item from dataset

        Returns:
            List of BoundingBox objects with normalized coordinates.
        """
        raw_bboxes = []

        # Format 1: item has 'bboxes' key directly
        if "bboxes" in item:
            for bbox in item["bboxes"]:
                if len(bbox) >= 4:
                    raw_bboxes.append(bbox)

        # Format 2: item has 'ner_tags' with nested structure
        elif "ner_tags" in item and "boxes" in item:
            for bbox in item["boxes"]:
                if len(bbox) >= 4:
                    raw_bboxes.append(bbox)

        # Format 3: Nested 'form' structure (original FUNSD format)
        elif "form" in item:
            for block in item["form"]:
                if "box" in block:
                    bbox = block["box"]
                    if len(bbox) >= 4:
                        raw_bboxes.append(bbox)

        # Normalize coordinates to 0-1 range
        bboxes = []
        for i, bbox in enumerate(raw_bboxes):
            x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]

            # Normalize using page dimensions
            norm_x = max(0.0, min(1.0, x1 / self.DEFAULT_PAGE_WIDTH))
            norm_y = max(0.0, min(1.0, y1 / self.DEFAULT_PAGE_HEIGHT))
            norm_w = max(0.0, min(1.0, (x2 - x1) / self.DEFAULT_PAGE_WIDTH))
            norm_h = max(0.0, min(1.0, (y2 - y1) / self.DEFAULT_PAGE_HEIGHT))

            bboxes.append(
                BoundingBox(
                    x=norm_x,
                    y=norm_y,
                    width=norm_w,
                    height=norm_h,
                    element_type="text",  # FUNSD is all text elements
                    confidence=0.95,  # Assumed high confidence for ground truth
                    reading_order=i,
                )
            )

        return bboxes

    def _count_entities(self, item: dict) -> dict:
        """Count entity types in FUNSD item.

        FUNSD entities: question, answer, header, other

        Args:
            item: Raw item from dataset

        Returns:
            Dict with entity type counts.
        """
        counts = {
            "question": 0,
            "answer": 0,
            "header": 0,
            "other": 0,
            "total_blocks": 0,
        }

        # Format with 'form' structure
        if "form" in item:
            for block in item["form"]:
                counts["total_blocks"] += 1
                label = block.get("label", "other").lower()
                if label in counts:
                    counts[label] += 1
                else:
                    counts["other"] += 1

        # Format with 'ner_tags'
        elif "ner_tags" in item:
            # NER tags are typically: 0=other, 1=question, 2=answer, 3=header
            tag_map = {0: "other", 1: "question", 2: "answer", 3: "header"}
            for tag in item["ner_tags"]:
                label = tag_map.get(tag, "other")
                counts[label] += 1
            counts["total_blocks"] = len(item["ner_tags"])

        return counts


def get_funsd_fingerprint(features: StructuralFeatures) -> str:
    """Generate a fingerprint for FUNSD-derived features.

    Args:
        features: Structural features extracted from FUNSD

    Returns:
        SHA256 fingerprint of the features.
    """
    features_json = features.model_dump_json()
    return hashlib.sha256(features_json.encode()).hexdigest()
