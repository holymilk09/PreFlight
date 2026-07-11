"""Tests for the client SDK (sdk/preflight_sdk).

The SDK lives in-repo but is a separate installable package; these tests add
it to sys.path directly so CI exercises it without an install step. Two
cross-checks only possible here (server code importable):

1. Adapter output must validate against the server's own StructuralFeatures
   pydantic model — the SDK can never produce a payload the API rejects.
2. SDK fingerprints must equal the server's template fingerprint
   (sha256 of StructuralFeatures.model_dump_json()) byte-for-byte, or the
   exact-match fast path silently never fires.
"""

import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "sdk"))

from preflight_sdk import PreFlight, PreFlightError, compute_fingerprint  # noqa: E402
from preflight_sdk.adapters import azure, google, textract, upstage  # noqa: E402

from src.models import StructuralFeatures  # noqa: E402

# ---------------------------------------------------------------------------
# Synthetic vendor payloads (minimal but structurally faithful)
# ---------------------------------------------------------------------------

TEXTRACT_RESPONSE = {
    "Blocks": [
        {"BlockType": "PAGE"},
        {
            "BlockType": "LINE",
            "Confidence": 98.2,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.05, "Width": 0.5, "Height": 0.03}},
        },
        {
            "BlockType": "LINE",
            "Confidence": 96.0,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.95, "Width": 0.4, "Height": 0.03}},
        },
        {
            "BlockType": "TABLE",
            "Confidence": 93.5,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.4, "Width": 0.8, "Height": 0.2}},
        },
        {
            "BlockType": "LAYOUT_FIGURE",
            "Confidence": 88.0,
            "Geometry": {"BoundingBox": {"Left": 0.6, "Top": 0.1, "Width": 0.3, "Height": 0.2}},
        },
        # Checkbox: must NOT be counted as an image.
        {
            "BlockType": "SELECTION_ELEMENT",
            "Confidence": 99.0,
            "Geometry": {"BoundingBox": {"Left": 0.05, "Top": 0.5, "Width": 0.02, "Height": 0.02}},
        },
        # WORD blocks are sub-elements of LINE; ignored.
        {
            "BlockType": "WORD",
            "Confidence": 98.0,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.05, "Width": 0.1, "Height": 0.03}},
        },
    ]
}

# Azure: 8.5x11in page — polygons in INCHES, must be normalized by page dims.
AZURE_RESULT = {
    "analyzeResult": {
        "pages": [{"pageNumber": 1, "width": 8.5, "height": 11.0, "unit": "inch"}],
        "paragraphs": [
            {
                "confidence": 0.97,
                "boundingRegions": [
                    # Top strip: y in [0.2, 0.5] inches -> normalized y ~0.018 (header)
                    {"pageNumber": 1, "polygon": [0.5, 0.2, 8.0, 0.2, 8.0, 0.5, 0.5, 0.5]}
                ],
            },
            {
                "boundingRegions": [
                    # Bottom strip -> normalized y ~0.95 (footer)
                    {"pageNumber": 1, "polygon": [0.5, 10.5, 8.0, 10.5, 8.0, 10.8, 0.5, 10.8]}
                ],
            },
        ],
        "tables": [
            {
                "boundingRegions": [
                    {"pageNumber": 1, "polygon": [1.0, 4.0, 7.5, 4.0, 7.5, 6.0, 1.0, 6.0]}
                ]
            }
        ],
        "figures": [],
    }
}

GOOGLE_DOCUMENT = {
    "document": {
        "pages": [
            {
                "dimension": {"width": 612.0, "height": 792.0},
                "blocks": [
                    {
                        "layout": {
                            "confidence": 0.98,
                            "boundingPoly": {
                                "normalizedVertices": [
                                    {"x": 0.1, "y": 0.05},
                                    {"x": 0.6, "y": 0.05},
                                    {"x": 0.6, "y": 0.08},
                                    {"x": 0.1, "y": 0.08},
                                ]
                            },
                        }
                    },
                    {
                        # Absolute vertices path: normalized via page dimension.
                        "layout": {
                            "boundingPoly": {
                                "vertices": [
                                    {"x": 61, "y": 700},
                                    {"x": 550, "y": 700},
                                    {"x": 550, "y": 780},
                                    {"x": 61, "y": 780},
                                ]
                            }
                        }
                    },
                ],
                "tables": [
                    {
                        "layout": {
                            "boundingPoly": {
                                "normalizedVertices": [
                                    {"x": 0.1, "y": 0.4},
                                    {"x": 0.9, "y": 0.4},
                                    {"x": 0.9, "y": 0.6},
                                    {"x": 0.1, "y": 0.6},
                                ]
                            }
                        }
                    }
                ],
                "visualElements": [],
            }
        ]
    }
}


# Upstage Document Parse: single `elements` array, categories, polygon
# coordinates ALREADY normalized to [0, 1] (no page-dimension division).
UPSTAGE_RESPONSE = {
    "api": "2.0",
    "model": "document-parse-250101",
    "usage": {"pages": 1},
    "elements": [
        {
            "id": 0,
            "category": "heading1",
            "page": 1,
            "coordinates": [
                {"x": 0.10, "y": 0.03},
                {"x": 0.90, "y": 0.03},
                {"x": 0.90, "y": 0.07},
                {"x": 0.10, "y": 0.07},
            ],
        },
        {
            "id": 1,
            "category": "table",
            "page": 1,
            "coordinates": [
                {"x": 0.10, "y": 0.40},
                {"x": 0.90, "y": 0.40},
                {"x": 0.90, "y": 0.60},
                {"x": 0.10, "y": 0.60},
            ],
        },
        {
            "id": 2,
            "category": "chart",
            "page": 1,
            "coordinates": [
                {"x": 0.60, "y": 0.10},
                {"x": 0.90, "y": 0.10},
                {"x": 0.90, "y": 0.30},
                {"x": 0.60, "y": 0.30},
            ],
        },
        {
            "id": 3,
            "category": "footer",
            "page": 1,
            "coordinates": [
                {"x": 0.10, "y": 0.95},
                {"x": 0.50, "y": 0.95},
                {"x": 0.50, "y": 0.98},
                {"x": 0.10, "y": 0.98},
            ],
        },
        # An unknown/future category must fall back to the text channel.
        {
            "id": 4,
            "category": "some_new_category",
            "page": 1,
            "coordinates": [
                {"x": 0.10, "y": 0.20},
                {"x": 0.80, "y": 0.20},
                {"x": 0.80, "y": 0.24},
                {"x": 0.10, "y": 0.24},
            ],
        },
    ],
}


class TestAdapters:
    def test_textract_features_valid_and_typed(self):
        features = textract.extract_features(TEXTRACT_RESPONSE)
        model = StructuralFeatures.model_validate(features)  # server-side contract
        assert model.page_count == 1
        assert model.table_count == 1
        assert model.image_count == 1  # LAYOUT_FIGURE, not the checkbox
        assert model.text_block_count == 2  # LINEs only, WORD ignored
        assert model.has_header is True
        assert model.has_footer is True

    def test_azure_normalizes_page_units(self):
        features = azure.extract_features(AZURE_RESULT)
        model = StructuralFeatures.model_validate(features)
        assert model.table_count == 1
        # If polygons weren't normalized by page dims, every coordinate would
        # exceed 1.0 and header/footer detection would be impossible.
        for box in model.bounding_boxes:
            assert 0.0 <= box.x <= 1.0 and 0.0 <= box.y <= 1.0
        assert model.has_header is True
        assert model.has_footer is True

    def test_google_both_vertex_paths(self):
        features = google.extract_features(GOOGLE_DOCUMENT)
        model = StructuralFeatures.model_validate(features)
        assert model.text_block_count == 2
        assert model.table_count == 1
        # The absolute-vertices block sits at the page bottom (footer).
        assert model.has_footer is True

    def test_upstage_normalized_polygons_and_categories(self):
        features = upstage.extract_features(UPSTAGE_RESPONSE)
        model = StructuralFeatures.model_validate(features)
        assert model.page_count == 1
        assert model.table_count == 1  # table
        assert model.image_count == 1  # chart -> figure channel
        assert model.text_block_count == 3  # heading1 + footer + unknown-category
        assert model.has_header is True  # heading1 at y=0.03
        assert model.has_footer is True  # footer near y=0.97
        # Coordinates are already normalized; nothing should exceed 1.0.
        for box in model.bounding_boxes:
            assert 0.0 <= box.x <= 1.0 and 0.0 <= box.y <= 1.0

    def test_all_adapters_share_schema(self):
        for features in (
            textract.extract_features(TEXTRACT_RESPONSE),
            azure.extract_features(AZURE_RESULT),
            google.extract_features(GOOGLE_DOCUMENT),
            upstage.extract_features(UPSTAGE_RESPONSE),
        ):
            model = StructuralFeatures.model_validate(features)
            assert 0.0 <= model.text_density <= 1.0
            assert 0.0 <= model.layout_complexity <= 1.0


class TestFingerprintParity:
    def test_matches_server_template_fingerprint(self):
        """SDK fingerprint == sha256(server model's model_dump_json())."""
        features = textract.extract_features(TEXTRACT_RESPONSE)
        server_json = StructuralFeatures.model_validate(features).model_dump_json()
        server_fp = hashlib.sha256(server_json.encode()).hexdigest()
        assert compute_fingerprint(features) == server_fp

    def test_parity_across_adapters(self):
        for features in (
            azure.extract_features(AZURE_RESULT),
            google.extract_features(GOOGLE_DOCUMENT),
            upstage.extract_features(UPSTAGE_RESPONSE),
        ):
            server_json = StructuralFeatures.model_validate(features).model_dump_json()
            server_fp = hashlib.sha256(server_json.encode()).hexdigest()
            assert compute_fingerprint(features) == server_fp


class TestClient:
    def _client(self, handler) -> PreFlight:
        transport = httpx.MockTransport(handler)
        http = httpx.Client(
            transport=transport,
            base_url="https://api.test",
            headers={"X-API-Key": "cp_" + "a" * 32},
        )
        return PreFlight(api_key="cp_" + "a" * 32, base_url="https://api.test", client=http)

    def test_evaluate_sends_fingerprint_and_metadata(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content)
            captured["api_key"] = request.headers.get("X-API-Key")
            return httpx.Response(200, json={"decision": "MATCH", "evaluation_id": "e-1"})

        features = textract.extract_features(TEXTRACT_RESPONSE)
        result = self._client(handler).evaluate(
            features,
            vendor="aws",
            model="textract",
            version="2023-01",
            confidence=0.95,
            doc_hash="d" * 64,
            correlation_id="inv-1",
            pipeline_id="p-1",
        )

        assert result["decision"] == "MATCH"
        assert captured["path"] == "/v1/evaluate"
        assert captured["api_key"].startswith("cp_")
        body = captured["body"]
        assert body["layout_fingerprint"] == compute_fingerprint(features)
        assert body["extractor_metadata"]["vendor"] == "aws"
        assert body["pipeline_id"] == "p-1"

    def test_feedback_posts_outcome(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"evaluation_id": "e-1", "outcome": "corrected"})

        result = self._client(handler).submit_feedback(
            "e-1", "corrected", field_error_count=2, source="human_review"
        )
        assert result["outcome"] == "corrected"
        assert captured["path"] == "/v1/evaluations/e-1/feedback"
        assert captured["body"] == {
            "outcome": "corrected",
            "field_error_count": 2,
            "source": "human_review",
        }

    def test_error_raises_with_detail(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429, json={"detail": {"code": "QUOTA_EXCEEDED", "message": "over quota"}}
            )

        with pytest.raises(PreFlightError) as exc:
            self._client(handler).get_usage()
        assert exc.value.status_code == 429
        assert exc.value.detail["code"] == "QUOTA_EXCEEDED"
