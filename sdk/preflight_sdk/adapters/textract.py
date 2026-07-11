"""AWS Textract adapter (analyze_document / detect_document_text responses).

Textract geometry is already normalized to [0, 1] page fractions.
"""

from typing import Any

from preflight_sdk.features import features_from_boxes, normalized_box

# BlockType -> PreFlight element_type. SELECTION_ELEMENT (checkboxes) is NOT
# an image; LAYOUT_FIGURE (from the Layout feature) is.
_TYPE_MAP = {
    "LINE": "text",
    "TABLE": "table",
    "LAYOUT_FIGURE": "figure",
    "LAYOUT_HEADER": "text",
    "LAYOUT_FOOTER": "text",
    "LAYOUT_SECTION_HEADER": "text",
    "LAYOUT_TEXT": "text",
    "KEY_VALUE_SET": "text",
}


def extract_features(response: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw Textract response dict to PreFlight structural features."""
    blocks = response.get("Blocks", [])

    page_count = sum(1 for b in blocks if b.get("BlockType") == "PAGE")

    boxes: list[dict[str, Any]] = []
    order = 0
    for block in blocks:
        element_type = _TYPE_MAP.get(block.get("BlockType", ""))
        if element_type is None:
            continue
        geometry = block.get("Geometry", {}).get("BoundingBox")
        if not geometry:
            continue
        boxes.append(
            normalized_box(
                x=geometry.get("Left", 0.0),
                y=geometry.get("Top", 0.0),
                width=geometry.get("Width", 0.0),
                height=geometry.get("Height", 0.0),
                element_type=element_type,
                confidence=block.get("Confidence", 90.0) / 100.0,
                reading_order=order,
            )
        )
        order += 1

    return features_from_boxes(boxes, page_count)
