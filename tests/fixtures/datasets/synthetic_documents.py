"""Synthetic document feature generator for diverse document type testing.

Since many PDF datasets (DocLayNet, RVL-CDIP, PubLayNet) use legacy HuggingFace
loading scripts that are no longer supported, this module generates realistic
synthetic features based on documented characteristics of different document types.

This allows testing of:
- Template matching across document categories
- Drift detection with varying complexity
- Feature extraction for complex layouts (tables, figures, multi-column)
"""

import random
from dataclasses import dataclass
from typing import Iterator

from src.models import BoundingBox, StructuralFeatures

from tests.fixtures.datasets.loader import DocumentSample


@dataclass
class DocumentTypeProfile:
    """Profile defining characteristics of a document type."""

    name: str
    # Element counts (min, max)
    element_range: tuple[int, int]
    table_range: tuple[int, int]
    image_range: tuple[int, int]
    # Layout characteristics
    column_range: tuple[int, int]
    text_density_range: tuple[float, float]
    complexity_range: tuple[float, float]
    # Structure
    has_header_prob: float
    has_footer_prob: float


# Document type profiles based on DocLayNet and RVL-CDIP research
DOCUMENT_PROFILES = {
    "financial_report": DocumentTypeProfile(
        name="financial_report",
        element_range=(30, 80),
        table_range=(1, 5),
        image_range=(0, 3),
        column_range=(1, 2),
        text_density_range=(0.3, 0.6),
        complexity_range=(0.4, 0.7),
        has_header_prob=0.95,
        has_footer_prob=0.90,
    ),
    "scientific_article": DocumentTypeProfile(
        name="scientific_article",
        element_range=(40, 100),
        table_range=(0, 3),
        image_range=(1, 5),
        column_range=(1, 2),
        text_density_range=(0.4, 0.7),
        complexity_range=(0.5, 0.8),
        has_header_prob=0.80,
        has_footer_prob=0.95,
    ),
    "legal_document": DocumentTypeProfile(
        name="legal_document",
        element_range=(50, 120),
        table_range=(0, 1),
        image_range=(0, 0),
        column_range=(1, 1),
        text_density_range=(0.5, 0.8),
        complexity_range=(0.3, 0.5),
        has_header_prob=0.90,
        has_footer_prob=0.95,
    ),
    "manual": DocumentTypeProfile(
        name="manual",
        element_range=(20, 60),
        table_range=(0, 2),
        image_range=(2, 8),
        column_range=(1, 2),
        text_density_range=(0.2, 0.5),
        complexity_range=(0.5, 0.7),
        has_header_prob=0.85,
        has_footer_prob=0.70,
    ),
    "invoice": DocumentTypeProfile(
        name="invoice",
        element_range=(15, 40),
        table_range=(1, 3),
        image_range=(0, 2),
        column_range=(1, 2),
        text_density_range=(0.15, 0.35),
        complexity_range=(0.3, 0.5),
        has_header_prob=0.98,
        has_footer_prob=0.60,
    ),
    "patent": DocumentTypeProfile(
        name="patent",
        element_range=(60, 150),
        table_range=(0, 2),
        image_range=(3, 10),
        column_range=(1, 1),
        text_density_range=(0.4, 0.6),
        complexity_range=(0.6, 0.8),
        has_header_prob=0.95,
        has_footer_prob=0.95,
    ),
}


class SyntheticDocumentGenerator:
    """Generate synthetic document samples with realistic feature distributions.

    Example usage:
        gen = SyntheticDocumentGenerator(seed=42)

        # Generate samples for a specific document type
        for sample in gen.generate("financial_report", count=100):
            print(f"{sample.id}: {sample.features.element_count} elements")

        # Generate mixed samples across all types
        for sample in gen.generate_mixed(count=600):
            print(f"{sample.category}: {sample.features.table_count} tables")
    """

    def __init__(self, seed: int | None = 42):
        """Initialize generator with optional seed for reproducibility."""
        self.rng = random.Random(seed)

    def generate(
        self,
        doc_type: str,
        count: int = 100
    ) -> Iterator[DocumentSample]:
        """Generate synthetic samples for a specific document type.

        Args:
            doc_type: Document type name (must be in DOCUMENT_PROFILES)
            count: Number of samples to generate

        Yields:
            DocumentSample with synthetic features.
        """
        if doc_type not in DOCUMENT_PROFILES:
            raise ValueError(f"Unknown document type: {doc_type}")

        profile = DOCUMENT_PROFILES[doc_type]

        for i in range(count):
            features = self._generate_features(profile)

            yield DocumentSample(
                id=f"synthetic_{doc_type}_{i:04d}",
                source_dataset="synthetic",
                features=features,
                category=doc_type,
                metadata={
                    "profile": doc_type,
                    "index": i,
                    "generator_version": "1.0",
                },
            )

    def generate_mixed(
        self,
        count: int = 600,
        types: list[str] | None = None
    ) -> Iterator[DocumentSample]:
        """Generate mixed samples across document types.

        Args:
            count: Total samples (divided evenly across types)
            types: Document types to include (default: all)

        Yields:
            DocumentSample with synthetic features.
        """
        if types is None:
            types = list(DOCUMENT_PROFILES.keys())

        per_type = count // len(types)

        for doc_type in types:
            yield from self.generate(doc_type, per_type)

    def _generate_features(self, profile: DocumentTypeProfile) -> StructuralFeatures:
        """Generate StructuralFeatures based on document profile."""

        # Generate counts
        element_count = self.rng.randint(*profile.element_range)
        table_count = self.rng.randint(*profile.table_range)
        image_count = self.rng.randint(*profile.image_range)

        # Text blocks = elements - tables - images (roughly)
        text_block_count = max(1, element_count - table_count - image_count)

        # Layout
        column_count = self.rng.randint(*profile.column_range)
        text_density = self.rng.uniform(*profile.text_density_range)
        complexity = self.rng.uniform(*profile.complexity_range)

        # Structure
        has_header = self.rng.random() < profile.has_header_prob
        has_footer = self.rng.random() < profile.has_footer_prob

        # Generate bounding boxes
        bboxes = self._generate_bboxes(
            element_count,
            table_count,
            image_count,
            column_count
        )

        return StructuralFeatures(
            element_count=element_count,
            table_count=table_count,
            text_block_count=text_block_count,
            image_count=image_count,
            page_count=1,
            text_density=text_density,
            layout_complexity=complexity,
            column_count=column_count,
            has_header=has_header,
            has_footer=has_footer,
            bounding_boxes=bboxes[:50],  # Limit stored boxes
        )

    def _generate_bboxes(
        self,
        total: int,
        tables: int,
        images: int,
        columns: int
    ) -> list[BoundingBox]:
        """Generate synthetic bounding boxes."""
        bboxes = []

        col_width = 1.0 / columns

        for i in range(min(total, 100)):  # Cap at 100 boxes
            # Determine element type
            if i < tables:
                elem_type = "table"
                # Tables are wider and taller
                width = self.rng.uniform(0.4, 0.8)
                height = self.rng.uniform(0.1, 0.3)
            elif i < tables + images:
                elem_type = "figure"
                width = self.rng.uniform(0.2, 0.5)
                height = self.rng.uniform(0.15, 0.35)
            else:
                elem_type = "text"
                width = self.rng.uniform(0.3, col_width * 0.9)
                height = self.rng.uniform(0.02, 0.08)

            # Position (ensure within bounds)
            col = i % columns
            x = col * col_width + self.rng.uniform(0.01, 0.05)
            x = min(x, 1.0 - width)
            y = self.rng.uniform(0.05, 0.9)
            y = min(y, 1.0 - height)

            bboxes.append(BoundingBox(
                x=x,
                y=y,
                width=width,
                height=height,
                element_type=elem_type,
                confidence=self.rng.uniform(0.85, 0.99),
                reading_order=i,
            ))

        return bboxes


def get_document_type_names() -> list[str]:
    """Get list of available document type names."""
    return list(DOCUMENT_PROFILES.keys())
