"""Azure Document Intelligence adapter (prebuilt-layout analyzeResult).

Azure polygons are in PAGE UNITS (inches for PDFs, pixels for images) — not
normalized. Coordinates are divided by the owning page's width/height here;
skipping that step (as naive integrations do) breaks header/footer detection
and cross-vendor comparability entirely.
"""

from typing import Any

from preflight_sdk.features import features_from_boxes, normalized_box


def _page_dims(result: dict[str, Any]) -> dict[int, tuple[float, float]]:
    dims: dict[int, tuple[float, float]] = {}
    for page in result.get("pages", []):
        number = page.get("pageNumber", 1)
        dims[number] = (float(page.get("width") or 1.0), float(page.get("height") or 1.0))
    return dims


def _polygon_to_box(polygon: list[float], width: float, height: float) -> tuple[float, ...]:
    xs = [polygon[i] / width for i in range(0, len(polygon), 2)]
    ys = [polygon[i] / height for i in range(1, len(polygon), 2)]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def extract_features(result: dict[str, Any]) -> dict[str, Any]:
    """Convert an Azure DI analyzeResult dict to PreFlight structural features.

    Accepts either the analyzeResult object itself or the full response
    envelope ({"analyzeResult": {...}}).
    """
    result = result.get("analyzeResult", result)
    dims = _page_dims(result)
    page_count = len(result.get("pages", []))

    boxes: list[dict[str, Any]] = []
    order = 0

    def add_regions(items: list[dict], element_type: str, default_confidence: float) -> None:
        nonlocal order
        for item in items:
            for region in item.get("boundingRegions", []):
                polygon = region.get("polygon", [])
                if len(polygon) < 4:
                    continue
                width, height = dims.get(region.get("pageNumber", 1), (1.0, 1.0))
                x, y, w, h = _polygon_to_box(polygon, width, height)
                boxes.append(
                    normalized_box(
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        element_type=element_type,
                        confidence=item.get("confidence", default_confidence),
                        reading_order=order,
                    )
                )
                order += 1

    add_regions(result.get("paragraphs", []), "text", 0.90)
    add_regions(result.get("tables", []), "table", 0.95)
    add_regions(result.get("figures", []), "figure", 0.90)

    return features_from_boxes(boxes, page_count)
