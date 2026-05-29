"""Integration tests for alerting endpoints (require Postgres + RLS)."""

import pytest
from httpx import AsyncClient


class TestAlertRulesCRUD:
    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get("/v1/alert-rules")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_and_list_rule(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/v1/alert-rules",
            json={
                "name": "strict drift",
                "metric": "drift",
                "comparator": "gt",
                "threshold": 0.2,
                "severity": "critical",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric"] == "drift"
        assert data["severity"] == "critical"
        rule_id = data["id"]

        resp = await authenticated_client.get("/v1/alert-rules")
        assert resp.status_code == 200
        assert any(r["id"] == rule_id for r in resp.json())

    @pytest.mark.asyncio
    async def test_invalid_metric_rejected(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/v1/alert-rules",
            json={"name": "bad", "metric": "nonsense", "threshold": 0.5},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_threshold_required_for_drift(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/v1/alert-rules",
            json={"name": "no threshold", "metric": "drift", "comparator": "gt"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_rule(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/v1/alert-rules",
            json={"name": "tmp", "metric": "reliability", "comparator": "lt", "threshold": 0.7},
        )
        rule_id = resp.json()["id"]
        resp = await authenticated_client.delete(f"/v1/alert-rules/{rule_id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_missing_rule_404(self, authenticated_client: AsyncClient):
        import uuid

        resp = await authenticated_client.delete(f"/v1/alert-rules/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestWebhooksCRUD:
    @pytest.mark.asyncio
    async def test_create_returns_secret_once(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/v1/webhooks",
            json={"url": "https://example.com/hook", "description": "test"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "secret" in data
        assert len(data["secret"]) == 64  # token_hex(32)

        # List must NOT include secret.
        resp = await authenticated_client.get("/v1/webhooks")
        assert resp.status_code == 200
        for wh in resp.json():
            assert "secret" not in wh

    @pytest.mark.asyncio
    async def test_invalid_url_rejected(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/v1/webhooks", json={"url": "ftp://nope"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_webhook(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/v1/webhooks", json={"url": "https://example.com/hook"}
        )
        wid = resp.json()["id"]
        resp = await authenticated_client.delete(f"/v1/webhooks/{wid}")
        assert resp.status_code == 204


class TestAlertsList:
    @pytest.mark.asyncio
    async def test_list_alerts_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_severity_filter_rejected(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/v1/alerts?severity=bogus")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_evaluate_generates_alert_events(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """An unknown vendor should produce at least an unknown_provider alert."""
        body = dict(valid_evaluate_request_data)
        body["extractor_metadata"] = dict(body["extractor_metadata"])
        body["extractor_metadata"]["vendor"] = "totally_unknown_vendor"

        resp = await authenticated_client.post("/v1/evaluate", json=body)
        assert resp.status_code == 200
        # Contract preserved: human-readable alerts still present.
        assert isinstance(resp.json()["alerts"], list)

        resp = await authenticated_client.get("/v1/alerts?metric=unknown_provider")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
