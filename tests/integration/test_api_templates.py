"""Integration tests for template API endpoints."""

import pytest
from httpx import AsyncClient


class TestCreateTemplate:
    """Tests for POST /v1/templates endpoint."""

    @pytest.mark.asyncio
    async def test_create_template_requires_auth(
        self,
        test_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Creating template should require authentication."""
        response = await test_client.post("/v1/templates", json=valid_template_create_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_template_success(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Creating template with valid data should succeed."""
        response = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["template_id"] == valid_template_create_data["template_id"]
        assert data["version"] == valid_template_create_data["version"]
        assert "fingerprint" in data
        assert len(data["fingerprint"]) == 64  # SHA256 hex
        assert data["status"] == "active"
        assert "id" in data  # UUID
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_template_duplicate_returns_409(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Creating duplicate template should return 409."""
        # Create first template
        response1 = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )

        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_template_different_version_allowed(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Creating template with different version should be allowed."""
        # Create v1.0
        response1 = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )
        assert response1.status_code == 201

        # Create v2.0
        valid_template_create_data["version"] = "2.0"
        response2 = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )

        assert response2.status_code == 201
        assert response2.json()["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_create_template_with_correction_rules(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Template with correction rules should store them correctly."""
        valid_template_create_data["correction_rules"] = [
            {"field": "total", "rule": "sum_line_items", "parameters": {"tolerance": 0.01}},
            {"field": "date", "rule": "iso8601_normalize", "parameters": None},
        ]

        response = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["correction_rules"]) == 2

    @pytest.mark.asyncio
    async def test_create_template_invalid_baseline_reliability(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Template with invalid baseline_reliability should fail validation."""
        valid_template_create_data["baseline_reliability"] = 1.5  # Invalid: > 1

        response = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )

        assert response.status_code == 422


class TestListTemplates:
    """Tests for GET /v1/templates endpoint."""

    @pytest.mark.asyncio
    async def test_list_templates_requires_auth(self, test_client: AsyncClient):
        """Listing templates should require authentication."""
        response = await test_client.get("/v1/templates")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_templates_empty(self, authenticated_client: AsyncClient):
        """Listing templates with no templates should return empty list."""
        response = await authenticated_client.get("/v1/templates")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_templates_returns_created(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Listing templates should return created templates."""
        # Create a template
        await authenticated_client.post("/v1/templates", json=valid_template_create_data)

        # List templates
        response = await authenticated_client.get("/v1/templates")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["template_id"] == valid_template_create_data["template_id"]

    @pytest.mark.asyncio
    async def test_list_templates_pagination(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """Listing templates should support pagination."""
        # Create multiple templates
        for i in range(5):
            template_data = {
                "template_id": f"INV-TEST-{i:03d}",
                "version": "1.0",
                "structural_features": sample_structural_features.model_dump(),
                "baseline_reliability": 0.85,
            }
            await authenticated_client.post("/v1/templates", json=template_data)

        # Get first page
        response1 = await authenticated_client.get("/v1/templates?limit=2&offset=0")
        assert response1.status_code == 200
        assert len(response1.json()) == 2

        # Get second page
        response2 = await authenticated_client.get("/v1/templates?limit=2&offset=2")
        assert response2.status_code == 200
        assert len(response2.json()) == 2

        # Get third page
        response3 = await authenticated_client.get("/v1/templates?limit=2&offset=4")
        assert response3.status_code == 200
        assert len(response3.json()) == 1

    @pytest.mark.asyncio
    async def test_list_templates_status_filter(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Listing templates should support status filter."""
        # Create template (status=active by default)
        await authenticated_client.post("/v1/templates", json=valid_template_create_data)

        # Filter by active status
        response = await authenticated_client.get("/v1/templates?status_filter=active")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Filter by deprecated status (should be empty)
        response = await authenticated_client.get("/v1/templates?status_filter=deprecated")
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestGetTemplate:
    """Tests for GET /v1/templates/{template_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_template_requires_auth(self, test_client: AsyncClient):
        """Getting template should require authentication."""
        from uuid_extensions import uuid7

        response = await test_client.get(f"/v1/templates/{uuid7()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, authenticated_client: AsyncClient):
        """Getting non-existent template should return 404."""
        from uuid_extensions import uuid7

        response = await authenticated_client.get(f"/v1/templates/{uuid7()}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_template_success(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
    ):
        """Getting existing template should return it."""
        # Create template
        create_response = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )
        template_id = create_response.json()["id"]

        # Get template
        response = await authenticated_client.get(f"/v1/templates/{template_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == template_id
        assert data["template_id"] == valid_template_create_data["template_id"]
        assert data["version"] == valid_template_create_data["version"]
