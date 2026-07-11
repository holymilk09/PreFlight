"""Shared feature computation: normalized boxes -> PreFlight structural features.

Every vendor adapter reduces its raw response to a list of normalized boxes
(coordinates in [0, 1] page fractions) plus a page count, then calls
``features_from_boxes``. Centralizing this is what makes features comparable
across vendors — and across PreFlight tenants.
"""

import hashlib
import json
from typing import Any

# Field order must mirror the server's StructuralFeatures / BoundingBox model
# declarations exactly: the server fingerprints a template as
# sha256(model.model_dump_json()), so byte-identical serialization is required
# for the exact-match fast path to fire.
_FEATURE_FIELD_ORDER = (
    "element_count",
    "table_count",
    "text_block_count",
    "image_count",
    "page_count",
    "text_density",
    "layout_complexity",
    "column_count",
    "has_header",
    "has_footer",
    "bounding_boxes",
)
_BOX_FIELD_ORDER = (
    "x",
    "y",
    "width",
    "height",
    "element_type",
    "confidence",
    "reading_order",
)

MAX_BOXES = 100


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalized_box(
    x: float,
    y: float,
    width: float,
    height: float,
    element_type: str,
    confidence: float,
    reading_order: int,
) -> dict[str, Any]:
    """Build a normalized bounding box dict (all coordinates clamped to [0,1])."""
    return {
        "x": round(_clamp(x), 4),
        "y": round(_clamp(y), 4),
        "width": round(_clamp(width), 4),
        "height": round(_clamp(height), 4),
        "element_type": element_type,
        "confidence": round(_clamp(confidence), 4),
        "reading_order": reading_order,
    }


def features_from_boxes(
    boxes: list[dict[str, Any]],
    page_count: int,
    text_types: tuple[str, ...] = ("text",),
) -> dict[str, Any]:
    """Reduce normalized boxes to the PreFlight structural feature schema.

    Args:
        boxes: normalized_box() dicts across ALL pages.
        page_count: number of pages in the document.
        text_types: element_type values counted as text for density.
    """
    page_count = max(1, page_count)
    tables = [b for b in boxes if b["element_type"] == "table"]
    images = [b for b in boxes if b["element_type"] in ("image", "figure")]
    texts = [b for b in boxes if b["element_type"] in text_types]

    # Density: fraction of a page covered by text, averaged over pages.
    text_area = sum(b["width"] * b["height"] for b in texts)
    text_density = round(_clamp(text_area / page_count), 4)

    # Complexity: bounded area x count proxy (parity with server-side synthetic
    # profiles; replace with entropy when the server does).
    total_area = sum(b["width"] * b["height"] for b in boxes)
    layout_complexity = round(_clamp(total_area * len(boxes) / 100), 4)

    # Columns: distinct left edges, coarsely bucketed.
    column_count = min(len({round(b["x"], 1) for b in boxes}), 4) if boxes else 1

    return {
        "element_count": len(boxes),
        "table_count": len(tables),
        "text_block_count": len(texts),
        "image_count": len(images),
        "page_count": page_count,
        "text_density": text_density,
        "layout_complexity": layout_complexity,
        "column_count": max(1, column_count),
        "has_header": any(b["y"] < 0.1 for b in boxes),
        "has_footer": any(b["y"] + b["height"] > 0.9 for b in boxes),
        "bounding_boxes": boxes[:MAX_BOXES],
    }


def compute_fingerprint(features: dict[str, Any]) -> str:
    """Fingerprint features exactly as the server does at template creation.

    The server computes sha256(StructuralFeatures.model_dump_json()): compact
    separators, model field order. Replicating it byte-for-byte lets an
    evaluate call hit the exact-match fast path against a template registered
    with the same features.
    """
    ordered: dict[str, Any] = {}
    for field in _FEATURE_FIELD_ORDER:
        value = features[field]
        if field == "bounding_boxes":
            value = [{k: box[k] for k in _BOX_FIELD_ORDER} for box in value]
        ordered[field] = value
    canonical = json.dumps(ordered, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
