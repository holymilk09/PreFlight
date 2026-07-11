"""Integration tests for analytics endpoints (require Postgres + RLS)."""

import pytest
from httpx import AsyncClient


class TestAnalyticsAuth:
    @pytest.mark.asyncio
    async def test_summary_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get("/v1/analytics/summary")
        assert resp.status_code == 401


class TestAnalyticsSummary:
    @pytest.mark.asyncio
    async def test_summary_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_evaluations"] == 0
        assert data["decision_breakdown"] == {}
        assert data["avg_drift"] is None

    @pytest.mark.asyncio
    async def test_summary_after_evaluations(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        for _ in range(3):
            resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)
            assert resp.status_code == 200

        resp = await authenticated_client.get("/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_evaluations"] == 3
        assert sum(data["decision_breakdown"].values()) == 3

    @pytest.mark.asyncio
    async def test_invalid_range_rejected(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(
            "/v1/analytics/summary",
            params={"from_ts": "2026-02-01T00:00:00", "to_ts": "2026-01-01T00:00:00"},
        )
        assert resp.status_code == 400


class TestAnalyticsTimeseries:
    @pytest.mark.asyncio
    async def test_timeseries_default(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/v1/analytics/timeseries?interval=day")
        assert resp.status_code == 200
        assert resp.json()["interval"] == "day"

    @pytest.mark.asyncio
    async def test_invalid_interval_rejected(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/v1/analytics/timeseries?interval=year")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_too_many_buckets_rejected(self, authenticated_client: AsyncClient):
        # 30 days of hourly buckets is fine; use a huge range with hourly to exceed cap.
        resp = await authenticated_client.get(
            "/v1/analytics/timeseries",
            params={
                "interval": "hour",
                "from_ts": "2020-01-01T00:00:00",
                "to_ts": "2020-12-31T00:00:00",
            },
        )
        assert resp.status_code == 400


class TestAnalyticsExtractors:
    @pytest.mark.asyncio
    async def test_extractors_after_evaluations(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)
        assert resp.status_code == 200

        resp = await authenticated_client.get("/v1/analytics/extractors")
        assert resp.status_code == 200
        data = resp.json()
        vendors = {e["vendor"] for e in data["extractors"]}
        assert "nvidia" in vendors
