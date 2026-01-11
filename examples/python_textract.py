"""
PreFlight + AWS Textract Integration Example

This example shows how to:
1. Extract a document using AWS Textract
2. Convert the response to PreFlight structural features
3. Send metadata to PreFlight for governance evaluation
4. Handle the response and apply correction rules

Requirements:
    pip install boto3 httpx

Usage:
    export AWS_ACCESS_KEY_ID=your-key
    export AWS_SECRET_ACCESS_KEY=your-secret
    export PREFLIGHT_API_KEY=cp_your_key
    python python_textract.py invoice.pdf
"""

import hashlib
import json
import sys
from pathlib import Path

import boto3
import httpx

# Configuration
PREFLIGHT_URL = "http://localhost:8000"  # Or your deployed URL
PREFLIGHT_API_KEY = "cp_your_api_key_here"  # Replace with your key


def extract_with_textract(file_path: str) -> dict:
    """Extract document using AWS Textract."""
    textract = boto3.client("textract")

    with open(file_path, "rb") as f:
        document_bytes = f.read()

    response = textract.analyze_document(
        Document={"Bytes": document_bytes},
        FeatureTypes=["TABLES", "FORMS"],
    )

    return response, document_bytes


def convert_to_structural_features(textract_response: dict) -> dict:
    """Convert Textract response to PreFlight structural features."""
    blocks = textract_response.get("Blocks", [])

    # Count element types
    tables = [b for b in blocks if b["BlockType"] == "TABLE"]
    text_blocks = [b for b in blocks if b["BlockType"] == "LINE"]
    images = [b for b in blocks if b["BlockType"] == "SELECTION_ELEMENT"]
    pages = [b for b in blocks if b["BlockType"] == "PAGE"]

    # Extract bounding boxes with reading order
    bounding_boxes = []
    for i, block in enumerate(blocks):
        if "Geometry" not in block:
            continue

        bbox = block["Geometry"]["BoundingBox"]
        bounding_boxes.append(
            {
                "x": round(bbox["Left"], 4),
                "y": round(bbox["Top"], 4),
                "width": round(bbox["Width"], 4),
                "height": round(bbox["Height"], 4),
                "element_type": block["BlockType"].lower(),
                "confidence": round(block.get("Confidence", 90) / 100, 4),
                "reading_order": i,
            }
        )

    # Calculate layout complexity (entropy-based)
    total_area = sum(b["width"] * b["height"] for b in bounding_boxes)
    layout_complexity = min(1.0, total_area * len(bounding_boxes) / 100)

    # Detect columns (simplified)
    x_positions = [b["x"] for b in bounding_boxes]
    unique_x = len(set(round(x, 1) for x in x_positions))
    column_count = min(unique_x, 4)  # Cap at 4 columns

    # Calculate text density
    text_area = sum(
        b["width"] * b["height"] for b in bounding_boxes if b["element_type"] == "line"
    )
    text_density = round(text_area * 1000, 2)  # Normalized

    return {
        "element_count": len(blocks),
        "table_count": len(tables),
        "text_block_count": len(text_blocks),
        "image_count": len(images),
        "page_count": max(1, len(pages)),
        "text_density": text_density,
        "layout_complexity": round(layout_complexity, 4),
        "column_count": column_count,
        "has_header": any(b["y"] < 0.1 for b in bounding_boxes),
        "has_footer": any(b["y"] > 0.9 for b in bounding_boxes),
        "bounding_boxes": bounding_boxes[:100],  # Limit to 100 for API
    }


def compute_fingerprint(features: dict) -> str:
    """Compute SHA256 fingerprint of structural features."""
    # Create canonical representation (exclude bounding_boxes for fingerprint)
    fp_data = {k: v for k, v in features.items() if k != "bounding_boxes"}
    canonical = json.dumps(fp_data, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def evaluate_with_preflight(
    features: dict,
    fingerprint: str,
    doc_hash: str,
    correlation_id: str,
) -> dict:
    """Send structural features to PreFlight for evaluation."""
    response = httpx.post(
        f"{PREFLIGHT_URL}/v1/evaluate",
        headers={"X-API-Key": PREFLIGHT_API_KEY},
        json={
            "layout_fingerprint": fingerprint,
            "structural_features": features,
            "extractor_metadata": {
                "vendor": "aws",
                "model": "textract",
                "version": "2023-01",
                "confidence": 0.95,
                "latency_ms": 1500,
                "cost_usd": 0.015,
            },
            "client_doc_hash": doc_hash,
            "client_correlation_id": correlation_id,
            "pipeline_id": "textract-example-v1",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def handle_decision(result: dict, textract_response: dict) -> None:
    """Handle PreFlight decision and apply corrections."""
    decision = result["decision"]
    drift_score = result["drift_score"]
    reliability_score = result["reliability_score"]

    print(f"\n{'='*50}")
    print(f"PreFlight Evaluation Result")
    print(f"{'='*50}")
    print(f"Decision:    {decision}")
    print(f"Drift Score: {drift_score:.2%}")
    print(f"Reliability: {reliability_score:.2%}")
    print(f"Eval ID:     {result['evaluation_id']}")

    if result.get("alerts"):
        print(f"\nAlerts:")
        for alert in result["alerts"]:
            print(f"  - {alert}")

    if result.get("correction_rules"):
        print(f"\nCorrection Rules to Apply:")
        for rule in result["correction_rules"]:
            print(f"  - {rule['field']}: {rule['rule']}")

    # Decision-specific handling
    if decision == "MATCH":
        print("\n[OK] High confidence match - proceed with extraction")
        # Use extracted data directly

    elif decision == "REVIEW":
        print("\n[REVIEW] Medium confidence - flagging for human review")
        # Queue for manual review, but show extracted data

    elif decision == "NEW":
        print("\n[NEW] New document type detected")
        print("Consider registering this as a new template")
        # Could auto-register or queue for review

    elif decision == "REJECT":
        print("\n[REJECT] Anomaly detected - investigate!")
        # Don't use extraction results without investigation


def main():
    if len(sys.argv) < 2:
        print("Usage: python python_textract.py <document.pdf>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Processing: {file_path}")

    # Step 1: Extract with Textract
    print("Extracting with AWS Textract...")
    textract_response, doc_bytes = extract_with_textract(file_path)
    print(f"  Found {len(textract_response.get('Blocks', []))} blocks")

    # Step 2: Convert to structural features
    print("Converting to structural features...")
    features = convert_to_structural_features(textract_response)
    print(f"  Tables: {features['table_count']}")
    print(f"  Text blocks: {features['text_block_count']}")
    print(f"  Bounding boxes: {len(features['bounding_boxes'])}")

    # Step 3: Compute fingerprint and doc hash
    fingerprint = compute_fingerprint(features)
    doc_hash = hashlib.sha256(doc_bytes).hexdigest()
    print(f"  Fingerprint: {fingerprint[:16]}...")

    # Step 4: Evaluate with PreFlight
    print("Evaluating with PreFlight...")
    try:
        result = evaluate_with_preflight(
            features=features,
            fingerprint=fingerprint,
            doc_hash=doc_hash,
            correlation_id=f"textract-{Path(file_path).stem}",
        )
    except httpx.HTTPStatusError as e:
        print(f"Error: PreFlight API returned {e.response.status_code}")
        print(e.response.text)
        sys.exit(1)
    except httpx.ConnectError:
        print(f"Error: Could not connect to PreFlight at {PREFLIGHT_URL}")
        print("Make sure the API is running")
        sys.exit(1)

    # Step 5: Handle the decision
    handle_decision(result, textract_response)


if __name__ == "__main__":
    main()
