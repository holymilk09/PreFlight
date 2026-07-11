"""Upstage Document Parse adapter (analyze response with ``elements``).

Upstage Document Parse returns one ``elements`` array (no per-page nesting);
each element carries a ``category``, a ``page`` number, and a ``coordinates``
polygon whose {x, y} points are ALREADY normalized to [0, 1] relative to the
page — so, unlike Azure/Google absolute vertices, no page-dimension division
is needed (Textract-style), but the polygon still reduces to a bounding box
via min/max (Azure-style).

Document Parse is an LLM-backed parser; it does not expose a per-element
confidence in the standard response, so a fixed default is used.
"""

from typing import Any

from preflight_sdk.features import features_from_boxes, normalized_box

# Upstage's 12 element categories -> PreFlight's 3 spatial channels.
_TABLE = {"table"}
_IMAGE = {"figure", "chart"}
# Everything else (paragraph, header, footer, caption, equation, heading1,
# list, index, footnote, and any future/unknown category) -> text.

# Document Parse does not return per-element confidence; use a fixed default.
_DEFAULT_CONFIDENCE = 0.95


def _classify(category: str) -> str:
    c = category.lower()
    if c in _TABLE:
        return "table"
    if c in _IMAGE:
        return "figure"
    return "text"


def _polygon_to_box(coordinates: list[dict[str, Any]]) -> tuple[float, ...] | None:
    """Reduce a normalized {x,y} polygon to (x, y, width, height)."""
    xs = [float(p.get("x", 0.0)) for p in coordinates]
    ys = [float(p.get("y", 0.0)) for p in coordinates]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def extract_features(response: dict[str, Any]) -> dict[str, Any]:
    """Convert an Upstage Document Parse response dict to structural features.

    Accepts either the full response or its ``elements`` list wrapped as
    ``{"elements": [...]}``.
    """
    elements = response.get("elements", [])

    boxes: list[dict[str, Any]] = []
    pages: set[int] = set()
    for order, element in enumerate(elements):
        page = int(element.get("page", 1) or 1)
        pages.add(page)
        coordinates = element.get("coordinates") or []
        box = _polygon_to_box(coordinates)
        if box is None:
            continue
        x, y, w, h = box
        boxes.append(
            normalized_box(
                x=x,
                y=y,
                width=w,
                height=h,
                element_type=_classify(element.get("category", "")),
                confidence=_DEFAULT_CONFIDENCE,
                reading_order=order,
            )
        )

    # Prefer the reported page count; fall back to the max page seen.
    page_count = int(response.get("usage", {}).get("pages") or 0) or (max(pages) if pages else 1)
    return features_from_boxes(boxes, page_count)
