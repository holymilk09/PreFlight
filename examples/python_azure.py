"""
PreFlight + Azure Document Intelligence Integration Example

This example shows how to:
1. Extract a document using Azure Document Intelligence (Form Recognizer)
2. Convert the response to PreFlight structural features
3. Send metadata to PreFlight for governance evaluation
4. Handle the response and apply correction rules

Requirements:
    pip install azure-ai-documentintelligence httpx

Usage:
    export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
    export AZURE_DOCUMENT_INTELLIGENCE_KEY=your-key
    export PREFLIGHT_API_KEY=cp_your_key
    python python_azure.py invoice.pdf
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import httpx
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

# Configuration
PREFLIGHT_URL = "http://localhost:8000"  # Or your deployed URL
PREFLIGHT_API_KEY = os.getenv("PREFLIGHT_API_KEY", "cp_your_api_key_here")
AZURE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")


def extract_with_azure(file_path: str) -> tuple[AnalyzeResult, bytes]:
    """Extract document using Azure Document Intelligence."""
    if not AZURE_ENDPOINT or not AZURE_KEY:
        raise ValueError(
            "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
            "AZURE_DOCUMENT_INTELLIGENCE_KEY environment variables"
        )

    client = DocumentIntelligenceClient(
        endpoint=AZURE_ENDPOINT,
        credential=AzureKeyCredential(AZURE_KEY),
    )

    with open(file_path, "rb") as f:
        document_bytes = f.read()

    # Use prebuilt-layout for general document structure
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        analyze_request=document_bytes,
        content_type="application/octet-stream",
    )
    result = poller.result()

    return result, document_bytes


def convert_to_structural_features(azure_result: AnalyzeResult) -> dict:
    """Convert Azure Document Intelligence result to PreFlight structural features."""
    bounding_boxes = []
    reading_order = 0

    # Process paragraphs
    paragraphs = azure_result.paragraphs or []
    for para in paragraphs:
        if para.bounding_regions:
            for region in para.bounding_regions:
                # Azure uses polygon, convert to bounding box
                polygon = region.polygon
                if len(polygon) >= 4:
                    x_coords = [polygon[i] for i in range(0, len(polygon), 2)]
                    y_coords = [polygon[i] for i in range(1, len(polygon), 2)]
                    bounding_boxes.append(
                        {
                            "x": round(min(x_coords), 4),
                            "y": round(min(y_coords), 4),
                            "width": round(max(x_coords) - min(x_coords), 4),
                            "height": round(max(y_coords) - min(y_coords), 4),
                            "element_type": "text",
                            "confidence": round(para.confidence or 0.9, 4),
                            "reading_order": reading_order,
                        }
                    )
                    reading_order += 1

    # Process tables
    tables = azure_result.tables or []
    for table in tables:
        if table.bounding_regions:
            for region in table.bounding_regions:
                polygon = region.polygon
                if len(polygon) >= 4:
                    x_coords = [polygon[i] for i in range(0, len(polygon), 2)]
                    y_coords = [polygon[i] for i in range(1, len(polygon), 2)]
                    bounding_boxes.append(
                        {
                            "x": round(min(x_coords), 4),
                            "y": round(min(y_coords), 4),
                            "width": round(max(x_coords) - min(x_coords), 4),
                            "height": round(max(y_coords) - min(y_coords), 4),
                            "element_type": "table",
                            "confidence": 0.95,
                            "reading_order": reading_order,
                        }
                    )
                    reading_order += 1

    # Process figures/images
    figures = azure_result.figures or []
    for figure in figures:
        if figure.bounding_regions:
            for region in figure.bounding_regions:
                polygon = region.polygon
                if len(polygon) >= 4:
                    x_coords = [polygon[i] for i in range(0, len(polygon), 2)]
                    y_coords = [polygon[i] for i in range(1, len(polygon), 2)]
                    bounding_boxes.append(
                        {
                            "x": round(min(x_coords), 4),
                            "y": round(min(y_coords), 4),
                            "width": round(max(x_coords) - min(x_coords), 4),
                            "height": round(max(y_coords) - min(y_coords), 4),
                            "element_type": "image",
                            "confidence": 0.90,
                            "reading_order": reading_order,
                        }
                    )
                    reading_order += 1

    # Count elements
    pages = azure_result.pages or []
    page_count = len(pages)

    # Calculate layout complexity
    total_area = sum(b["width"] * b["height"] for b in bounding_boxes)
    layout_complexity = min(1.0, total_area * len(bounding_boxes) / 100)

    # Calculate text density
    text_boxes = [b for b in bounding_boxes if b["element_type"] == "text"]
    text_area = sum(b["width"] * b["height"] for b in text_boxes)
    text_density = round(text_area * 1000, 2)

    # Detect columns
    if bounding_boxes:
        x_positions = [b["x"] for b in bounding_boxes]
        unique_x = len(set(round(x, 1) for x in x_positions))
        column_count = min(unique_x, 4)
    else:
        column_count = 1

    return {
        "element_count": len(bounding_boxes),
        "table_count": len(tables),
        "text_block_count": len(paragraphs),
        "image_count": len(figures),
        "page_count": max(1, page_count),
        "text_density": text_density,
        "layout_complexity": round(layout_complexity, 4),
        "column_count": column_count,
        "has_header": any(b["y"] < 0.1 for b in bounding_boxes),
        "has_footer": any(b["y"] > 0.9 for b in bounding_boxes),
        "bounding_boxes": bounding_boxes[:100],
    }


def compute_fingerprint(features: dict) -> str:
    """Compute SHA256 fingerprint of structural features."""
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
                "vendor": "azure",
                "model": "document-intelligence",
                "version": "2024-02-29-preview",
                "confidence": 0.95,
                "latency_ms": 2000,
                "cost_usd": 0.01,
            },
            "client_doc_hash": doc_hash,
            "client_correlation_id": correlation_id,
            "pipeline_id": "azure-docint-example-v1",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def handle_decision(result: dict) -> None:
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
    elif decision == "REVIEW":
        print("\n[REVIEW] Medium confidence - flagging for human review")
    elif decision == "NEW":
        print("\n[NEW] New document type detected")
        print("Consider registering this as a new template")
    elif decision == "REJECT":
        print("\n[REJECT] Anomaly detected - investigate!")


def main():
    if len(sys.argv) < 2:
        print("Usage: python python_azure.py <document.pdf>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Processing: {file_path}")

    # Step 1: Extract with Azure
    print("Extracting with Azure Document Intelligence...")
    try:
        azure_result, doc_bytes = extract_with_azure(file_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Step 2: Convert to structural features
    print("Converting to structural features...")
    features = convert_to_structural_features(azure_result)
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
            correlation_id=f"azure-{Path(file_path).stem}",
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
    handle_decision(result)


if __name__ == "__main__":
    main()
