"""Google Document AI adapter (Document proto as dict / JSON).

Document AI layouts carry boundingPoly with normalizedVertices (already 0-1)
or absolute vertices (divided by page dimension here).
"""

from typing import Any

from preflight_sdk.features import features_from_boxes, normalized_box


def _layout_box(layout: dict[str, Any], page: dict[str, Any]) -> tuple[float, ...] | None:
    poly = layout.get("boundingPoly", {})
    vertices = poly.get("normalizedVertices")
    if vertices:
        xs = [v.get("x", 0.0) for v in vertices]
        ys = [v.get("y", 0.0) for v in vertices]
    else:
        vertices = poly.get("vertices")
        if not vertices:
            return None
        dimension = page.get("dimension", {})
        width = float(dimension.get("width") or 1.0)
        height = float(dimension.get("height") or 1.0)
        xs = [v.get("x", 0.0) / width for v in vertices]
        ys = [v.get("y", 0.0) / height for v in vertices]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def extract_features(document: dict[str, Any]) -> dict[str, Any]:
    """Convert a Document AI document dict to PreFlight structural features.

    Accepts either the document itself or a process response ({"document": ...}).
    """
    document = document.get("document", document)
    pages = document.get("pages", [])

    boxes: list[dict[str, Any]] = []
    order = 0

    def add(items: list[dict], element_type: str, page: dict, default_confidence: float) -> None:
        nonlocal order
        for item in items:
            layout = item.get("layout", item)
            box = _layout_box(layout, page)
            if box is None:
                continue
            x, y, w, h = box
            boxes.append(
                normalized_box(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    element_type=element_type,
                    confidence=layout.get("confidence", default_confidence),
                    reading_order=order,
                )
            )
            order += 1

    for page in pages:
        add(page.get("blocks", []), "text", page, 0.90)
        add(page.get("tables", []), "table", page, 0.95)
        add(page.get("visualElements", []), "figure", page, 0.85)

    return features_from_boxes(boxes, len(pages))
