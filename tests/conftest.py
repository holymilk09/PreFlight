"""Pytest configuration and shared fixtures."""

import os

# Set required environment variables BEFORE any src imports
# These are test values - must match .env for integration tests
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://controlplane:test_postgres_password_12345678901234567890@localhost:5432/controlplane",
)
os.environ.setdefault("POSTGRES_PASSWORD", "test_postgres_password_12345678901234567890")
os.environ.setdefault(
    "REDIS_URL", "redis://:test_redis_password_12345678901234567890@localhost:6379/0"
)
os.environ.setdefault("REDIS_PASSWORD", "test_redis_password_12345678901234567890")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_1234567890123456789012345678901234567890")
os.environ.setdefault("API_KEY_SALT", "test_api_key_salt_12345678901234567890123456789012")


import pytest
from uuid_extensions import uuid7

from src.models import (
    APIKey,
    ExtractorMetadata,
    ExtractorProvider,
    StructuralFeatures,
    Template,
    TemplateStatus,
    Tenant,
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
        correction_rules=[{"field": "total", "rule": "sum_line_items", "parameters": None}],
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

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from src.security import generate_api_key

# Test database URL (uses same credentials as main DB but different database name)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://controlplane:{os.environ.get('POSTGRES_PASSWORD', 'test_postgres_password_12345678901234567890')}@localhost:5432/control_plane_test",
)


@pytest.fixture
async def test_engine():
    """Create test database engine for each test.

    Each test gets its own engine to avoid event loop conflicts.
    Tables are dropped and recreated to ensure schema matches models.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Check connection validity
    )

    # Drop and recreate all tables to ensure schema matches current models
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    # Set up RLS policies (idempotent - will not error if already exist)
    async with engine.begin() as conn:
        # Create a non-superuser role for RLS testing (superusers bypass all RLS)
        await conn.execute(
            text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'test_rls_user') THEN
                    CREATE ROLE test_rls_user WITH LOGIN PASSWORD 'test_rls_password';
                END IF;
            END
            $$
        """)
        )
        # Grant privileges to the test role
        await conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO test_rls_user"))
        await conn.execute(text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO test_rls_user"))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO test_rls_user"))

        # Enable RLS on tables (FORCE makes it apply to table owner too)
        await conn.execute(text("ALTER TABLE templates ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE templates FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE evaluations FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE api_keys FORCE ROW LEVEL SECURITY"))

        # Drop existing policies if they exist (for idempotency)
        await conn.execute(text("DROP POLICY IF EXISTS tenant_isolation_templates ON templates"))
        await conn.execute(
            text("DROP POLICY IF EXISTS tenant_isolation_evaluations ON evaluations")
        )
        await conn.execute(text("DROP POLICY IF EXISTS tenant_isolation_api_keys ON api_keys"))

        # Create RLS policies (NULLIF handles empty strings gracefully)
        # Using WITH CHECK allows INSERTs that match the tenant context
        await conn.execute(
            text("""
            CREATE POLICY tenant_isolation_templates ON templates
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """)
        )
        await conn.execute(
            text("""
            CREATE POLICY tenant_isolation_evaluations ON evaluations
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """)
        )
        await conn.execute(
            text("""
            CREATE POLICY tenant_isolation_api_keys ON api_keys
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """)
        )

    # Clean up test data before each test for isolation
    async with engine.begin() as conn:
        # Truncate tables in correct order (respecting foreign keys)
        # Disable RLS temporarily for cleanup
        await conn.execute(text("SET session_replication_role = 'replica'"))
        await conn.execute(text("TRUNCATE TABLE audit_log CASCADE"))
        await conn.execute(text("TRUNCATE TABLE evaluations CASCADE"))
        await conn.execute(text("TRUNCATE TABLE templates CASCADE"))
        await conn.execute(text("TRUNCATE TABLE api_keys CASCADE"))
        await conn.execute(text("TRUNCATE TABLE tenants CASCADE"))
        # Truncate and reseed provider table
        await conn.execute(text("TRUNCATE TABLE extractor_providers CASCADE"))
        await conn.execute(text("SET session_replication_role = 'origin'"))

    # Seed default providers for tests
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            INSERT INTO extractor_providers (id, vendor, display_name, confidence_multiplier, drift_sensitivity, supported_element_types, typical_latency_ms, is_active, is_known, created_at, updated_at)
            VALUES
                (gen_random_uuid(), 'aws', 'AWS Textract', 1.0, 1.0, '["PAGE", "LINE", "WORD", "TABLE", "CELL", "KEY_VALUE_SET"]', 450, true, true, NOW(), NOW()),
                (gen_random_uuid(), 'azure', 'Azure Document Intelligence', 0.95, 1.1, '["page", "paragraph", "table", "figure", "keyValuePair"]', 600, true, true, NOW(), NOW()),
                (gen_random_uuid(), 'google', 'Google Document AI', 1.0, 1.0, '["text_segment", "table", "form_field", "paragraph"]', 550, true, true, NOW(), NOW()),
                (gen_random_uuid(), 'nvidia', 'NVIDIA Nemotron', 1.05, 0.9, '["text", "table", "figure", "list", "title"]', 300, true, true, NOW(), NOW()),
                (gen_random_uuid(), 'abbyy', 'ABBYY FineReader', 0.98, 1.0, '["text", "table", "barcode", "checkmark"]', 800, true, true, NOW(), NOW()),
                (gen_random_uuid(), 'tesseract', 'Tesseract OCR', 0.85, 1.2, '["text", "line", "word"]', 200, true, true, NOW(), NOW())
            ON CONFLICT (vendor) DO NOTHING
        """)
        )

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a simple test database session.

    For tests that don't interact with the API, this provides a basic session.
    For API tests, use the authenticated_client fixture instead.
    """
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture
async def test_tenant(test_engine) -> Tenant:
    """Create a test tenant that persists for the duration of the test.

    This commits the tenant to the database so it's visible to API calls.
    Note: No cleanup is performed to avoid event loop issues. The test database
    should be reset between test runs or cleaned up at the session level.
    """
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        tenant = Tenant(
            name=f"Test Tenant {uuid7()}",  # Unique name for each test
            settings={"plan": "enterprise"},
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return tenant


@pytest.fixture
async def test_api_key(test_engine, test_tenant: Tenant) -> tuple[APIKey, str]:
    """Create a test API key that persists for the duration of the test.

    Returns:
        Tuple of (APIKey model, plain API key string)

    Note: No cleanup is performed to avoid event loop issues. The test database
    should be reset between test runs or cleaned up at the session level.
    """
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    key_components = generate_api_key()

    async with async_session() as session:
        api_key = APIKey(
            tenant_id=test_tenant.id,
            key_hash=key_components.key_hash,
            key_prefix=key_components.key_prefix,
            name=f"test-key-{uuid7()}",  # Unique name for each test
            scopes=["*"],
            rate_limit=1000,
        )
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
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
    test_engine,  # Ensure tables are created
    mock_redis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP test client (unauthenticated).

    This client:
    - Mocks Redis for rate limiting
    - Uses the test database engine
    - Does NOT have authentication (use authenticated_client for that)
    """
    from src import db
    from src.api.deps import get_db_session
    from src.api.main import app
    from src.services import rate_limiter

    # Create a test session maker bound to our test engine
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Override database dependency
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db

    # Patch the global database session maker
    original_session_maker = db.async_session_maker
    db.async_session_maker = test_session_maker

    # Patch the audit module's reference to async_session_maker
    from src import audit

    original_audit_session_maker = audit.async_session_maker
    audit.async_session_maker = test_session_maker

    # Patch the auth module's reference to async_session_maker
    from src.api import auth

    original_auth_session_maker = auth.async_session_maker
    auth.async_session_maker = test_session_maker

    # Patch the global Redis client and rate limiter
    original_redis_client = rate_limiter._redis_client
    original_rate_limiter = rate_limiter._rate_limiter

    rate_limiter._redis_client = mock_redis
    rate_limiter._rate_limiter = rate_limiter.RateLimiter(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Restore original values
    db.async_session_maker = original_session_maker
    audit.async_session_maker = original_audit_session_maker
    auth.async_session_maker = original_auth_session_maker
    rate_limiter._redis_client = original_redis_client
    rate_limiter._rate_limiter = original_rate_limiter
    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(
    test_engine,
    mock_redis,
    test_tenant: Tenant,
    test_api_key: tuple[APIKey, str],
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated test client.

    This client:
    - Mocks authentication to return the test tenant
    - Mocks Redis for rate limiting
    - Uses the test database engine for API endpoints
    """
    from src import db
    from src.api.auth import AuthenticatedTenant, validate_api_key
    from src.api.deps import get_db_session, get_tenant_db
    from src.api.main import app
    from src.services import rate_limiter

    api_key_record, plain_key = test_api_key

    # Create mock authenticated tenant
    mock_tenant = AuthenticatedTenant(
        tenant_id=test_tenant.id,
        tenant_name=test_tenant.name,
        api_key_id=api_key_record.id,
        api_key_name=api_key_record.name,
        scopes=api_key_record.scopes or ["*"],
        rate_limit=api_key_record.rate_limit,
    )

    # Create a test session maker bound to our test engine
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Override dependencies
    async def override_auth():
        return mock_tenant

    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    async def override_get_tenant_db():
        async with test_session_maker() as session:
            from sqlalchemy import text

            tenant_id_str = str(test_tenant.id)
            await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'"))
            yield session

    app.dependency_overrides[validate_api_key] = override_auth
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_tenant_db] = override_get_tenant_db

    # Patch the global database session maker (used by some parts of the app)
    original_session_maker = db.async_session_maker
    db.async_session_maker = test_session_maker

    # Patch the audit module's reference to async_session_maker
    from src import audit

    original_audit_session_maker = audit.async_session_maker
    audit.async_session_maker = test_session_maker

    # Patch the auth module's reference to async_session_maker
    from src.api import auth

    original_auth_session_maker = auth.async_session_maker
    auth.async_session_maker = test_session_maker

    # Patch the global Redis client and rate limiter
    original_redis_client = rate_limiter._redis_client
    original_rate_limiter = rate_limiter._rate_limiter

    rate_limiter._redis_client = mock_redis
    rate_limiter._rate_limiter = rate_limiter.RateLimiter(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Also set the API key header for completeness
        client.headers["X-API-Key"] = plain_key
        yield client

    # Restore original values
    db.async_session_maker = original_session_maker
    audit.async_session_maker = original_audit_session_maker
    auth.async_session_maker = original_auth_session_maker
    rate_limiter._redis_client = original_redis_client
    rate_limiter._rate_limiter = original_rate_limiter
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(
    test_engine,
    mock_redis,
    test_tenant: Tenant,
    test_api_key: tuple[APIKey, str],
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated test client with admin scope.

    This client:
    - Mocks authentication to return the test tenant with admin scope
    - Mocks Redis for rate limiting
    - Uses the test database engine for API endpoints
    """
    from src import db
    from src.api.auth import AuthenticatedTenant, validate_api_key
    from src.api.deps import get_db_session, get_tenant_db
    from src.api.main import app
    from src.services import rate_limiter

    api_key_record, plain_key = test_api_key

    # Create mock authenticated tenant with admin scope
    mock_tenant = AuthenticatedTenant(
        tenant_id=test_tenant.id,
        tenant_name=test_tenant.name,
        api_key_id=api_key_record.id,
        api_key_name=api_key_record.name,
        scopes=["*", "admin"],  # Include admin scope
        rate_limit=api_key_record.rate_limit,
    )

    # Create a test session maker bound to our test engine
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Override dependencies
    async def override_auth():
        return mock_tenant

    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    async def override_get_tenant_db():
        async with test_session_maker() as session:
            from sqlalchemy import text

            tenant_id_str = str(test_tenant.id)
            await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'"))
            yield session

    app.dependency_overrides[validate_api_key] = override_auth
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_tenant_db] = override_get_tenant_db

    # Patch the global database session maker (used by some parts of the app)
    original_session_maker = db.async_session_maker
    db.async_session_maker = test_session_maker

    # Patch the audit module's reference to async_session_maker
    from src import audit

    original_audit_session_maker = audit.async_session_maker
    audit.async_session_maker = test_session_maker

    # Patch the auth module's reference to async_session_maker
    from src.api import auth

    original_auth_session_maker = auth.async_session_maker
    auth.async_session_maker = test_session_maker

    # Patch the global Redis client and rate limiter
    original_redis_client = rate_limiter._redis_client
    original_rate_limiter = rate_limiter._rate_limiter

    rate_limiter._redis_client = mock_redis
    rate_limiter._rate_limiter = rate_limiter.RateLimiter(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["X-API-Key"] = plain_key
        yield client

    # Restore original values
    db.async_session_maker = original_session_maker
    audit.async_session_maker = original_audit_session_maker
    auth.async_session_maker = original_auth_session_maker
    rate_limiter._redis_client = original_redis_client
    rate_limiter._rate_limiter = original_rate_limiter
    app.dependency_overrides.clear()


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
