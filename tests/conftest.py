"""Pytest configuration and shared fixtures."""

import os

# Set required environment variables BEFORE any src imports
# These are test values - not used in production
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password_12345678901234567890")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("REDIS_PASSWORD", "test_redis_password_1234567890")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_1234567890123456789012345678901234567890")
os.environ.setdefault("API_KEY_SALT", "test_api_key_salt_12345678901234567890123456789012")

import pytest
from uuid import UUID
from uuid_extensions import uuid7

from src.models import (
    CorrectionRule,
    ExtractorMetadata,
    StructuralFeatures,
    Template,
    TemplateStatus,
)


@pytest.fixture
def sample_structural_features() -> StructuralFeatures:
    """Standard invoice-like structural features."""
    return StructuralFeatures(
        element_count=45,
        table_count=2,
        text_block_count=30,
        image_count=3,
        page_count=1,
        text_density=0.45,
        layout_complexity=0.32,
        column_count=2,
        has_header=True,
        has_footer=True,
        bounding_boxes=[],
    )


@pytest.fixture
def sample_extractor_metadata() -> ExtractorMetadata:
    """Standard NVIDIA extractor metadata."""
    return ExtractorMetadata(
        vendor="nvidia",
        model="nemotron-parse-1.2",
        version="1.2.0",
        confidence=0.95,
        latency_ms=234,
        cost_usd=0.002,
    )


@pytest.fixture
def sample_template(sample_structural_features: StructuralFeatures) -> Template:
    """Standard template for testing."""
    return Template(
        id=uuid7(),
        tenant_id=uuid7(),
        template_id="INV-ACME-001",
        version="1.0",
        fingerprint="abc123" * 10 + "abcd",  # 64 char hex
        structural_features=sample_structural_features.model_dump(),
        baseline_reliability=0.85,
        correction_rules=[
            {"field": "total", "rule": "sum_line_items", "parameters": None}
        ],
        status=TemplateStatus.ACTIVE,
    )


@pytest.fixture
def high_drift_features() -> StructuralFeatures:
    """Features with significant drift from standard template."""
    return StructuralFeatures(
        element_count=100,  # Much higher
        table_count=5,  # Different
        text_block_count=60,  # Higher
        image_count=10,  # Higher
        page_count=3,  # Different
        text_density=0.80,  # Much higher
        layout_complexity=0.70,  # Higher
        column_count=4,  # Different
        has_header=False,  # Different
        has_footer=False,  # Different
        bounding_boxes=[],
    )


@pytest.fixture
def low_confidence_extractor() -> ExtractorMetadata:
    """Extractor with low confidence."""
    return ExtractorMetadata(
        vendor="unknown_vendor",
        model="experimental",
        version="0.1.0",
        confidence=0.55,
        latency_ms=1500,
        cost_usd=0.01,
    )


# -----------------------------------------------------------------------------
# Integration Test Fixtures
# -----------------------------------------------------------------------------

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlmodel import SQLModel

from src.models import APIKey, Tenant
from src.security import generate_api_key


# Test database URL (can be overridden by environment)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/control_plane_test"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine and tables.

    This fixture creates all tables at the start of the test session
    and drops them at the end.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction rollback.

    Each test gets a fresh session that rolls back all changes
    at the end, ensuring test isolation.
    """
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        name="Test Tenant",
        settings={"plan": "enterprise"},
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def test_api_key(db_session: AsyncSession, test_tenant: Tenant) -> tuple[APIKey, str]:
    """Create a test API key.

    Returns:
        Tuple of (APIKey model, plain API key string)
    """
    key_components = generate_api_key()

    api_key = APIKey(
        tenant_id=test_tenant.id,
        key_hash=key_components.key_hash,
        key_prefix=key_components.key_prefix,
        name="test-key",
        scopes=["*"],
        rate_limit=1000,
    )
    db_session.add(api_key)
    await db_session.flush()

    return api_key, key_components.full_key


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    redis = AsyncMock()
    redis.script_load = AsyncMock(return_value="fake_sha_123")
    redis.evalsha = AsyncMock(return_value=[1, 0, 60])  # allowed, 0 existing, 60s window
    redis.ping = AsyncMock(return_value=True)
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
async def test_client(
    db_session: AsyncSession,
    mock_redis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP test client.

    This client:
    - Uses the test database session
    - Mocks Redis for rate limiting
    - Provides a clean app instance for each test
    """
    from src.api.main import app
    from src.api.deps import get_db_session, get_tenant_db
    from src.services.rate_limiter import get_redis_client

    # Override database dependency
    async def override_get_db():
        yield db_session

    async def override_get_tenant_db(tenant_id: UUID = None):
        # Set tenant context for RLS
        if tenant_id:
            await db_session.execute(
                f"SET LOCAL app.tenant_id = '{tenant_id}'"
            )
        yield db_session

    async def override_redis():
        return mock_redis

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_redis_client] = override_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(
    test_client: AsyncClient,
    test_api_key: tuple[APIKey, str],
) -> AsyncClient:
    """Create an authenticated test client with API key header."""
    _, plain_key = test_api_key
    test_client.headers["X-API-Key"] = plain_key
    return test_client


@pytest.fixture
def valid_evaluate_request_data(sample_structural_features: StructuralFeatures) -> dict:
    """Create valid data for evaluate request."""
    import hashlib
    import json

    # Generate a valid fingerprint from structural features
    features_json = json.dumps(sample_structural_features.model_dump(), sort_keys=True)
    fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

    return {
        "layout_fingerprint": fingerprint,
        "structural_features": sample_structural_features.model_dump(),
        "extractor_metadata": {
            "vendor": "nvidia",
            "model": "nemotron-parse-1.2",
            "version": "1.2.0",
            "confidence": 0.95,
            "latency_ms": 234,
            "cost_usd": 0.002,
        },
        "client_doc_hash": "a" * 64,
        "client_correlation_id": "test-correlation-123",
        "pipeline_id": "test-pipeline-1",
    }


@pytest.fixture
def valid_template_create_data(sample_structural_features: StructuralFeatures) -> dict:
    """Create valid data for template creation."""
    return {
        "template_id": "INV-TEST-001",
        "version": "1.0",
        "structural_features": sample_structural_features.model_dump(),
        "baseline_reliability": 0.85,
        "correction_rules": [
            {"field": "total", "rule": "sum_line_items", "parameters": {"tolerance": 0.01}}
        ],
    }
