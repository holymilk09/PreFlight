"""PreFlight SDK: metadata-only document extraction observability.

Turn raw extractor output into PreFlight structural features and evaluate:

    from preflight_sdk import PreFlight
    from preflight_sdk.adapters import textract

    features = textract.extract_features(textract_response)
    client = PreFlight(api_key="cp_...", base_url="https://your-deploy")
    result = client.evaluate(
        features,
        vendor="aws", model="textract", version="2023-01", confidence=0.95,
        doc_hash=sha256_of_your_document,
        correlation_id="invoice-123",
    )
    if result["decision"] != "MATCH":
        route_to_review()

Only structural metadata (counts, normalized bounding boxes) ever leaves your
environment — never document content.
"""

from preflight_sdk.client import PreFlight, PreFlightError
from preflight_sdk.features import compute_fingerprint, features_from_boxes

__all__ = ["PreFlight", "PreFlightError", "compute_fingerprint", "features_from_boxes"]

__version__ = "0.1.0"
