"""SROIE dataset loader for receipt understanding validation.

SROIE (Scanned Receipts OCR and Information Extraction) contains 973 real
scanned receipts from ICDAR 2019 competition with bounding boxes and key fields.

Dataset: https://huggingface.co/datasets/rth/sroie-2019-v2
Competition: https://rrc.cvc.uab.es/?ch=13
"""

from pathlib import Path
from typing import Iterator

from src.models import BoundingBox, StructuralFeatures

from tests.fixtures.datasets.loader import (
    DatasetLoader,
    DocumentSample,
    compute_layout_complexity,
    compute_text_density,
    detect_columns,
    detect_header_footer,
)


class SROIELoader(DatasetLoader):
    """Loader for the SROIE dataset from Hugging Face.

    SROIE contains 973 receipts with annotations including:
    - Word-level bounding boxes (quadrilateral format)
    - Entity extraction: company, date, address, total
    - Word-level text content (not used - we only need structure)

    Example usage:
        loader = SROIELoader()
        for sample in loader.load():
            print(f"Receipt {sample.id}: {sample.features.element_count} elements")
    """

    # Using the cleaned version with Parquet format
    DATASET_ID = "rth/sroie-2019-v2"

    @property
    def name(self) -> str:
        return "sroie"

    @property
    def size(self) -> int:
        return 973  # 626 train + 347 test

    def _download(self) -> None:
        """Download SROIE from Hugging Face datasets."""
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError(
                "The 'datasets' package is required for SROIE loading. "
                "Install with: pip install datasets"
            )

        # Download and cache
        load_dataset(self.DATASET_ID, cache_dir=str(self.cache_dir / self.name))

        # Save a marker file to indicate download complete
        marker = self.cache_dir / self.name / ".downloaded"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

    def is_cached(self) -> bool:
        """Check if SROIE is already downloaded."""
        marker = self.cache_dir / self.name / ".downloaded"
        return marker.exists()

    def load(self) -> Iterator[DocumentSample]:
        """Load SROIE documents and extract structural features.

        Downloads the dataset if not already cached.

        Yields:
            DocumentSample objects for each receipt in SROIE.
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError(
                "The 'datasets' package is required for SROIE loading. "
                "Install with: pip install datasets"
            )

        # Load dataset (auto-downloads if needed)
        dataset = load_dataset(self.DATASET_ID, cache_dir=str(self.cache_dir / self.name))

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
        """Convert a SROIE item to DocumentSample.

        Args:
            item: Raw item from Hugging Face dataset
            split: Dataset split (train/test)
            idx: Index within split

        Returns:
            DocumentSample with extracted structural features.
        """
        # Get image dimensions for normalization
        image = item.get("image")
        if image is not None:
            page_width, page_height = image.size
        else:
            # Fallback dimensions (typical receipt size)
            page_width, page_height = 500, 1000

        # Extract bounding boxes from annotations
        bboxes = self._extract_bboxes(item, page_width, page_height)

        # Count entities
        entity_counts = self._count_entities(item)

        # Compute structural features
        has_header, has_footer = detect_header_footer(bboxes, page_height)

        features = StructuralFeatures(
            element_count=len(bboxes),
            table_count=0,  # SROIE doesn't annotate tables
            text_block_count=len(bboxes),
            image_count=0,  # SROIE is text-only receipts
            page_count=1,
            text_density=compute_text_density(bboxes, page_width, page_height),
            layout_complexity=compute_layout_complexity(bboxes, page_width, page_height),
            column_count=detect_columns(bboxes, page_width),
            has_header=has_header,
            has_footer=has_footer,
            bounding_boxes=bboxes[:50],  # Limit for storage
        )

        # Generate document ID
        doc_id = f"sroie_{split}_{idx:04d}"

        return DocumentSample(
            id=doc_id,
            source_dataset="sroie",
            features=features,
            category="receipt",
            metadata={
                "split": split,
                "index": idx,
                "entity_counts": entity_counts,
                "image_size": (page_width, page_height),
            },
        )

    def _extract_bboxes(
        self, item: dict, page_width: int, page_height: int
    ) -> list[BoundingBox]:
        """Extract bounding boxes from SROIE item.

        SROIE format (rth/sroie-2019-v2):
        - 'objects' dict with 'bbox' list
        - Each bbox is [[x1,x2,x3,x4], [y1,y2,y3,y4]] (quad corners)

        Coordinates are normalized to 0-1 range using image dimensions.

        Args:
            item: Raw item from dataset
            page_width: Image width in pixels
            page_height: Image height in pixels

        Returns:
            List of BoundingBox objects with normalized coordinates.
        """
        bboxes = []

        objects = item.get("objects", {})
        raw_bboxes = objects.get("bbox", [])

        for i, bbox in enumerate(raw_bboxes):
            if len(bbox) != 2:
                continue

            x_coords, y_coords = bbox[0], bbox[1]

            if len(x_coords) < 4 or len(y_coords) < 4:
                continue

            # Get bounding rectangle from quad
            x_min = min(x_coords)
            x_max = max(x_coords)
            y_min = min(y_coords)
            y_max = max(y_coords)

            # Normalize to 0-1 range
            norm_x = max(0.0, min(1.0, x_min / page_width))
            norm_y = max(0.0, min(1.0, y_min / page_height))
            norm_w = max(0.0, min(1.0, (x_max - x_min) / page_width))
            norm_h = max(0.0, min(1.0, (y_max - y_min) / page_height))

            bboxes.append(BoundingBox(
                x=norm_x,
                y=norm_y,
                width=norm_w,
                height=norm_h,
                element_type="text",  # SROIE is all text elements
                confidence=0.95,  # High confidence for ground truth
                reading_order=i,
            ))

        return bboxes

    def _count_entities(self, item: dict) -> dict:
        """Count entity types in SROIE item.

        SROIE entities: company, date, address, total

        Args:
            item: Raw item from dataset

        Returns:
            Dict with entity info.
        """
        objects = item.get("objects", {})
        entities = objects.get("entities", {})
        texts = objects.get("text", [])

        return {
            "company": 1 if entities.get("company") else 0,
            "date": 1 if entities.get("date") else 0,
            "address": 1 if entities.get("address") else 0,
            "total": 1 if entities.get("total") else 0,
            "total_blocks": len(texts),
        }
