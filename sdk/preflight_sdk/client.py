"""HTTP client for the PreFlight API."""

from typing import Any

import httpx

from preflight_sdk.features import compute_fingerprint


class PreFlightError(Exception):
    """API error with status code and the server's structured detail."""

    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"PreFlight API error {status_code}: {detail}")


class PreFlight:
    """Synchronous PreFlight API client.

    Args:
        api_key: PreFlight API key (``cp_...``).
        base_url: Your PreFlight deployment URL.
        timeout: Per-request timeout in seconds.
        client: Optional pre-configured httpx.Client (useful for testing).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ):
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise PreFlightError(response.status_code, detail)
        if response.status_code == 204:
            return {}
        return response.json()

    def evaluate(
        self,
        features: dict[str, Any],
        *,
        vendor: str,
        model: str,
        version: str,
        confidence: float,
        doc_hash: str,
        correlation_id: str,
        latency_ms: int = 0,
        cost_usd: float | None = None,
        pipeline_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate extraction metadata; returns decision, drift, reliability.

        ``features`` is the dict produced by a vendor adapter (or your own
        code, matching the structural feature schema). Only metadata is sent.
        """
        payload: dict[str, Any] = {
            "layout_fingerprint": compute_fingerprint(features),
            "structural_features": features,
            "extractor_metadata": {
                "vendor": vendor,
                "model": model,
                "version": version,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
            },
            "client_doc_hash": doc_hash,
            "client_correlation_id": correlation_id,
        }
        if pipeline_id is not None:
            payload["pipeline_id"] = pipeline_id
        return self._request("POST", "/v1/evaluate", json=payload)

    def submit_feedback(
        self,
        evaluation_id: str,
        outcome: str,
        *,
        field_error_count: int | None = None,
        review_seconds: int | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Report what actually happened downstream (correct/corrected/rejected).

        Feedback calibrates PreFlight's scores against your reality and powers
        the calibration/ROI analytics.
        """
        body: dict[str, Any] = {"outcome": outcome}
        if field_error_count is not None:
            body["field_error_count"] = field_error_count
        if review_seconds is not None:
            body["review_seconds"] = review_seconds
        if source is not None:
            body["source"] = source
        return self._request("POST", f"/v1/evaluations/{evaluation_id}/feedback", json=body)

    def register_template(
        self,
        template_id: str,
        version: str,
        features: dict[str, Any],
        *,
        baseline_reliability: float = 0.85,
        correction_rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Register a document template from its structural features."""
        return self._request(
            "POST",
            "/v1/templates",
            json={
                "template_id": template_id,
                "version": version,
                "structural_features": features,
                "baseline_reliability": baseline_reliability,
                "correction_rules": correction_rules or [],
            },
        )

    def get_usage(self) -> dict[str, Any]:
        """Current month's evaluation usage vs plan quota."""
        return self._request("GET", "/v1/usage")

    def get_calibration(self, **params: Any) -> dict[str, Any]:
        """Score calibration vs reported outcomes (the ROI report)."""
        return self._request("GET", "/v1/analytics/calibration", params=params)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PreFlight":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
