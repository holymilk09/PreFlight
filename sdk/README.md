# preflight-sdk

Turn raw extractor output (AWS Textract, Azure Document Intelligence, Google
Document AI) into PreFlight structural features and evaluate — in 3 lines.
Only structural metadata (counts, normalized bounding boxes) ever leaves your
environment. Never document content.

## Install

```bash
pip install preflight-sdk        # once published; or: pip install ./sdk
```

## Usage

```python
from preflight_sdk import PreFlight
from preflight_sdk.adapters import textract  # or azure, google, upstage

# 1. Your normal extraction
response = boto3.client("textract").analyze_document(...)

# 2. Reduce to metadata (local — nothing leaves your environment yet)
features = textract.extract_features(response)

# 3. Evaluate
client = PreFlight(api_key="cp_...", base_url="https://your-preflight-deploy")
result = client.evaluate(
    features,
    vendor="aws", model="textract", version="2023-01", confidence=0.95,
    doc_hash="<sha256 of your document, computed by you>",
    correlation_id="invoice-123",
)

if result["decision"] == "MATCH":
    auto_process()
else:                      # REVIEW / NEW / REJECT
    route_to_human(result["drift_score"], result["reliability_score"])
```

Close the loop so PreFlight can prove (or improve) its scores against your
reality:

```python
client.submit_feedback(result["evaluation_id"], "corrected", field_error_count=2)
print(client.get_calibration())   # errors caught vs missed, per score band
```

## Adapters

| Adapter | Input | Notes |
|---|---|---|
| `adapters.textract` | `analyze_document` response dict | Geometry already normalized |
| `adapters.azure` | `prebuilt-layout` analyzeResult dict | Polygons are page-unit — normalized by page dimensions automatically |
| `adapters.google` | Document AI document dict | Uses normalizedVertices when present |
| `adapters.upstage` | Document Parse response dict | Polygon coordinates already normalized (0-1); 12-category taxonomy |

All adapters reduce to the same normalized-box schema before computing
features, which is what makes scores comparable across vendors.
