"""SQLModel models for database tables and API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator
from sqlalchemy import DDL, Index, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Relationship, SQLModel
from sqlmodel import Field as SQLField
from uuid_extensions import uuid7

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class Decision(str, Enum):
    """Evaluation decision types."""

    MATCH = "MATCH"  # Matches known template, high confidence
    REVIEW = "REVIEW"  # Needs human review
    NEW = "NEW"  # New template detected
    REJECT = "REJECT"  # Anomaly detected, potential fraud


class TemplateStatus(str, Enum):
    """Template lifecycle status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REVIEW = "review"


class UserRole(str, Enum):
    """User role types."""

    USER = "user"  # Regular customer user
    ADMIN = "admin"  # Tenant admin
    SUPERADMIN = "superadmin"  # System admin (us)


class AuditAction(str, Enum):
    """Audit log action types."""

    API_KEY_CREATED = "api_key_created"
    API_KEY_ROTATED = "api_key_rotated"
    API_KEY_REVOKED = "api_key_revoked"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    TEMPLATE_DEPRECATED = "template_deprecated"
    TEMPLATE_STATUS_CHANGED = "template_status_changed"
    TENANT_CREATED = "tenant_created"
    TENANT_UPDATED = "tenant_updated"
    EVALUATION_REQUESTED = "evaluation_requested"
    AUTH_FAILED = "auth_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    QUOTA_EXCEEDED = "quota_exceeded"
    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    ACCOUNT_LOCKED = "account_locked"
    PASSWORD_CHANGED = "password_changed"
    SECURITY_DEGRADED = "security_degraded"
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RULE_CREATED = "alert_rule_created"
    ALERT_RULE_DELETED = "alert_rule_deleted"
    WEBHOOK_CREATED = "webhook_created"
    WEBHOOK_DELETED = "webhook_deleted"


# -----------------------------------------------------------------------------
# Database Models (with table=True)
# -----------------------------------------------------------------------------


class Tenant(SQLModel, table=True):
    """Tenant (customer) organization."""

    __tablename__ = "tenants"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    name: str = SQLField(max_length=255, nullable=False)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    settings: dict[str, Any] = SQLField(default_factory=dict, sa_column=Column(JSONB))

    # Relationships
    api_keys: list["APIKey"] = Relationship(back_populates="tenant")
    templates: list["Template"] = Relationship(back_populates="tenant")
    users: list["User"] = Relationship(back_populates="tenant")


class User(SQLModel, table=True):
    """User account for dashboard access."""

    __tablename__ = "users"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    email: str = SQLField(max_length=255, nullable=False, unique=True, index=True)
    password_hash: str = SQLField(max_length=255, nullable=False)
    role: str = SQLField(default="user", max_length=20)
    is_active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    last_login_at: datetime | None = SQLField(default=None)
    # Per-user brute-force lockout state. failed_login_count tracks consecutive
    # failed logins since the last success/lock; locked_until, when in the future,
    # blocks authentication even with a correct password.
    failed_login_count: int = SQLField(default=0, nullable=False)
    locked_until: datetime | None = SQLField(default=None)

    # Relationships
    tenant: Tenant = Relationship(back_populates="users")


class APIKey(SQLModel, table=True):
    """API key for authentication (stored as SHA256 hash)."""

    __tablename__ = "api_keys"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    key_hash: str = SQLField(max_length=64, nullable=False)  # SHA256 hex
    key_prefix: str = SQLField(max_length=8, nullable=False)  # For identification
    name: str | None = SQLField(max_length=255, default=None)
    scopes: list[str] = SQLField(default_factory=list, sa_column=Column(JSONB))
    rate_limit: int = SQLField(default=1000)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    last_used_at: datetime | None = SQLField(default=None)
    revoked_at: datetime | None = SQLField(default=None)

    # Relationships
    tenant: Tenant = Relationship(back_populates="api_keys")

    @property
    def is_active(self) -> bool:
        """Check if API key is active (not revoked)."""
        return self.revoked_at is None


class Template(SQLModel, table=True):
    """Document template with structural fingerprint."""

    __tablename__ = "templates"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    template_id: str = SQLField(max_length=255, nullable=False)  # Human-readable ID
    version: str = SQLField(max_length=50, nullable=False)
    fingerprint: str = SQLField(max_length=64, nullable=False)  # SHA256 of features
    structural_features: dict[str, Any] = SQLField(sa_column=Column(JSONB, nullable=False))
    baseline_reliability: float = SQLField(default=0.85)
    correction_rules: list[dict[str, Any]] = SQLField(default_factory=list, sa_column=Column(JSONB))
    status: TemplateStatus = SQLField(default=TemplateStatus.ACTIVE)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    created_by: UUID | None = SQLField(default=None)

    # Relationships
    tenant: Tenant = Relationship(back_populates="templates")

    class Config:
        """SQLModel config."""

        # Create unique constraint on (tenant_id, template_id, version)
        table_args = {"schema": None}


class Evaluation(SQLModel, table=True):
    """Document evaluation record."""

    __tablename__ = "evaluations"
    # Composite index for tenant-scoped time-range scans (analytics endpoints
    # and the /v1/evaluations listing). Serves the tenant_id equality + created_at
    # range/ordering in one access path.
    __table_args__ = (Index("ix_evaluations_tenant_created", "tenant_id", "created_at"),)

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    correlation_id: str = SQLField(max_length=255, nullable=False, index=True)
    document_hash: str = SQLField(max_length=64, nullable=False)
    template_id: UUID | None = SQLField(foreign_key="templates.id", default=None)
    decision: Decision = SQLField(nullable=False)
    match_confidence: float | None = SQLField(default=None)
    drift_score: float | None = SQLField(default=None)
    reliability_score: float | None = SQLField(default=None)
    correction_rules: list[dict[str, Any]] = SQLField(default_factory=list, sa_column=Column(JSONB))

    # Enhanced extractor tracking
    extractor_vendor: str | None = SQLField(max_length=100, default=None)
    extractor_model: str | None = SQLField(max_length=100, default=None)
    extractor_version: str | None = SQLField(max_length=50, default=None)
    extractor_confidence: float | None = SQLField(default=None)
    extractor_latency_ms: int | None = SQLField(default=None)
    extractor_cost_usd: float | None = SQLField(default=None)

    # Provider reference
    provider_id: UUID | None = SQLField(default=None, foreign_key="extractor_providers.id")

    # Safeguard results
    validation_warnings: list[str] = SQLField(default_factory=list, sa_column=Column(JSONB))

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    processing_time_ms: int | None = SQLField(default=None)


class ExtractorProvider(SQLModel, table=True):
    """Extractor provider configuration for multi-vendor support."""

    __tablename__ = "extractor_providers"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    vendor: str = SQLField(max_length=50, nullable=False, unique=True, index=True)
    display_name: str = SQLField(max_length=100, nullable=False)

    # Calibration factors (1.0 = no adjustment)
    confidence_multiplier: float = SQLField(default=1.0)
    drift_sensitivity: float = SQLField(default=1.0)

    # Provider characteristics
    supported_element_types: list[str] = SQLField(default_factory=list, sa_column=Column(JSONB))
    typical_latency_ms: int = SQLField(default=500)

    # Status
    is_active: bool = SQLField(default=True)
    is_known: bool = SQLField(default=True)

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    """Audit log for security-sensitive operations.

    Note: No RLS on this table - admin access only via separate connection.
    """

    __tablename__ = "audit_log"

    id: int | None = SQLField(default=None, primary_key=True)
    timestamp: datetime = SQLField(default_factory=datetime.utcnow, index=True)
    tenant_id: UUID | None = SQLField(default=None, index=True)
    actor_id: UUID | None = SQLField(default=None)
    action: str = SQLField(max_length=50, nullable=False)
    resource_type: str | None = SQLField(max_length=100, default=None)
    resource_id: UUID | None = SQLField(default=None)
    details: dict[str, Any] | None = SQLField(default=None, sa_column=Column(JSONB))
    ip_address: str | None = SQLField(default=None, max_length=45)  # IPv6 max length
    request_id: UUID | None = SQLField(default=None)


# Make audit_log append-only at the database level: a BEFORE UPDATE OR DELETE
# trigger rejects any row mutation, for every role (tamper-evidence for SR 26-2
# style audit requirements). INSERT and TRUNCATE/DROP are unaffected, so normal
# logging and test teardown still work. Attached to create_all (tests) and
# replicated in migration 009 for existing databases.
_AUDIT_NO_MUTATE_FN = DDL(  # type: ignore[no-untyped-call]
    """
    CREATE OR REPLACE FUNCTION audit_log_no_mutate() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only; updates and deletes are not permitted';
    END;
    $$ LANGUAGE plpgsql;
    """
)
_AUDIT_NO_MUTATE_TRIGGER = DDL(  # type: ignore[no-untyped-call]
    "CREATE TRIGGER audit_log_append_only "
    "BEFORE UPDATE OR DELETE ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutate()"
)
event.listen(AuditLog.__table__, "after_create", _AUDIT_NO_MUTATE_FN)  # type: ignore[attr-defined]
event.listen(AuditLog.__table__, "after_create", _AUDIT_NO_MUTATE_TRIGGER)  # type: ignore[attr-defined]


class AlertRule(SQLModel, table=True):
    """Tenant-defined alerting rule.

    Compares an evaluation metric against a threshold. When breached, an
    AlertEvent is generated. If a tenant defines no rules, built-in default
    rules (encoding CLAUDE.md thresholds) apply.
    """

    __tablename__ = "alert_rules"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    name: str = SQLField(max_length=120, nullable=False)
    # "drift" | "reliability" | "unknown_provider"
    metric: str = SQLField(max_length=40, nullable=False)
    # "gt" | "lt" | "eq" (for unknown_provider, ignored/"eq")
    comparator: str = SQLField(max_length=4, nullable=False, default="gt")
    threshold: float | None = SQLField(default=None)
    # "info" | "warning" | "critical"
    severity: str = SQLField(max_length=20, nullable=False, default="warning")
    enabled: bool = SQLField(default=True, nullable=False)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class WebhookEndpoint(SQLModel, table=True):
    """Tenant webhook endpoint for alert delivery.

    The ``secret`` is retained server-side to compute the outbound HMAC
    signature. It is stored in plaintext at rest (encryption deferred) and
    is returned to the client only once, at creation time.
    """

    __tablename__ = "webhook_endpoints"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    url: str = SQLField(max_length=2048, nullable=False)
    # Stores the signing secret encrypted at rest (Fernet); ciphertext is longer
    # than the 64-char plaintext, so allow ample width.
    secret: str = SQLField(max_length=512, nullable=False)
    description: str | None = SQLField(max_length=255, default=None)
    enabled: bool = SQLField(default=True, nullable=False)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class AlertEvent(SQLModel, table=True):
    """A generated alert event, persisted synchronously in the evaluate txn.

    Webhook delivery state is updated asynchronously by the background task.
    A null ``rule_id`` indicates a built-in default rule fired.
    """

    __tablename__ = "alert_events"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    evaluation_id: UUID | None = SQLField(default=None, foreign_key="evaluations.id", index=True)
    rule_id: UUID | None = SQLField(default=None, foreign_key="alert_rules.id")
    metric: str = SQLField(max_length=40, nullable=False)
    value: float | None = SQLField(default=None)
    threshold: float | None = SQLField(default=None)
    severity: str = SQLField(max_length=20, nullable=False)
    message: str = SQLField(max_length=500, nullable=False)
    # "pending" | "sent" | "failed" | "no_endpoint"
    delivery_status: str = SQLField(max_length=20, nullable=False, default="pending")
    delivery_attempts: int = SQLField(default=0, nullable=False)
    last_error: str | None = SQLField(max_length=500, default=None)
    created_at: datetime = SQLField(default_factory=datetime.utcnow, index=True)


# -----------------------------------------------------------------------------
# API Request/Response Schemas (table=False, Pydantic only)
# -----------------------------------------------------------------------------


class BoundingBox(SQLModel):
    """Bounding box element from layout analysis."""

    x: float = Field(ge=0, le=1, description="Normalized X coordinate (0-1)")
    y: float = Field(ge=0, le=1, description="Normalized Y coordinate (0-1)")
    width: float = Field(ge=0, le=1, description="Normalized width (0-1)")
    height: float = Field(ge=0, le=1, description="Normalized height (0-1)")
    element_type: str = Field(max_length=50, description="Element type: text, table, image, etc.")
    confidence: float = Field(ge=0, le=1, description="Detection confidence")
    reading_order: int = Field(ge=0, description="Reading order index")


class StructuralFeatures(SQLModel):
    """Structural features extracted from document layout."""

    element_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    text_block_count: int = Field(ge=0)
    image_count: int = Field(ge=0)
    page_count: int = Field(ge=1)
    text_density: float = Field(ge=0, description="Characters per normalized area")
    layout_complexity: float = Field(ge=0, le=1, description="Entropy of bounding boxes")
    column_count: int = Field(ge=0)
    has_header: bool
    has_footer: bool
    bounding_boxes: list[BoundingBox] = Field(default_factory=list, max_length=1000)


class ExtractorMetadata(SQLModel):
    """Metadata about the extractor that processed the document."""

    vendor: str = Field(max_length=100, description="Vendor name: nvidia, abbyy, tesseract")
    model: str = Field(max_length=100, description="Model identifier")
    version: str = Field(max_length=50, description="Model version")
    confidence: float = Field(ge=0, le=1, description="Overall extraction confidence")
    latency_ms: int = Field(ge=0, description="Processing latency in milliseconds")
    cost_usd: float | None = Field(default=None, ge=0, description="Processing cost")


class EvaluateRequest(SQLModel):
    """Request body for /v1/evaluate endpoint."""

    layout_fingerprint: str = Field(max_length=64, description="SHA256 hash of structural features")
    structural_features: StructuralFeatures
    extractor_metadata: ExtractorMetadata
    client_doc_hash: str = Field(
        max_length=64, description="Client's document SHA256 (we never see content)"
    )
    client_correlation_id: str = Field(max_length=255, description="Client's correlation ID")
    pipeline_id: str = Field(max_length=255, description="Client's pipeline identifier")

    @field_validator("layout_fingerprint", "client_doc_hash")
    @classmethod
    def validate_hex_hash(cls, v: str) -> str:
        """Validate SHA256 hex string."""
        if len(v) != 64:
            raise ValueError("Must be a 64-character SHA256 hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Must be a valid hexadecimal string")
        return v.lower()


class CorrectionRule(SQLModel):
    """Correction rule to apply to extraction results."""

    field: str = Field(max_length=100, description="Field to apply rule to (* for all)")
    rule: str = Field(max_length=100, description="Rule identifier")
    parameters: dict[str, Any] | None = Field(default=None)


class EvaluateResponse(SQLModel):
    """Response body for /v1/evaluate endpoint."""

    decision: Decision
    template_version_id: str | None = None
    drift_score: float = Field(ge=0, le=1, description="0.0 (no drift) to 1.0 (severe drift)")
    reliability_score: float = Field(ge=0, le=1, description="Predicted extraction reliability")
    correction_rules: list[CorrectionRule] = Field(default_factory=list)
    replay_hash: str = Field(description="Hash for audit replay")
    evaluation_id: UUID = Field(description="Unique evaluation identifier")
    alerts: list[str] = Field(default_factory=list)


class TemplateCreate(SQLModel):
    """Request body for creating a new template."""

    template_id: str = Field(max_length=255, description="Human-readable template ID")
    version: str = Field(max_length=50, description="Version string")
    structural_features: StructuralFeatures
    baseline_reliability: float = Field(default=0.85, ge=0, le=1)
    correction_rules: list[CorrectionRule] = Field(default_factory=list)


class TemplateResponse(SQLModel):
    """Response body for template endpoints."""

    id: UUID
    template_id: str
    version: str
    fingerprint: str
    baseline_reliability: float
    status: TemplateStatus
    created_at: datetime
    correction_rules: list[CorrectionRule] = Field(default_factory=list)


class TemplateUpdate(SQLModel):
    """Request body for updating a template."""

    baseline_reliability: float | None = Field(default=None, ge=0, le=1)
    correction_rules: list[CorrectionRule] | None = Field(default=None)


class TemplateStatusUpdate(SQLModel):
    """Request body for updating template status."""

    status: TemplateStatus


class HealthResponse(SQLModel):
    """Health check response."""

    status: str
    version: str = "0.1.0"


class ServiceStatus(SQLModel):
    """Individual service status."""

    healthy: bool
    latency_ms: float | None = None
    error: str | None = None


class DetailedHealthResponse(SQLModel):
    """Detailed health check response for /v1/status."""

    status: str
    version: str = "0.1.0"
    services: dict[str, ServiceStatus] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Evaluation Response Schemas
# -----------------------------------------------------------------------------


class EvaluationRecord(SQLModel):
    """Response body for a single evaluation record."""

    id: UUID
    correlation_id: str
    document_hash: str
    template_id: UUID | None
    template_version_id: str | None = None
    decision: Decision
    match_confidence: float | None
    drift_score: float | None
    reliability_score: float | None
    correction_rules: list[CorrectionRule] = Field(default_factory=list)
    extractor_vendor: str | None
    extractor_model: str | None
    extractor_version: str | None = None
    extractor_confidence: float | None = None
    extractor_latency_ms: int | None = None
    validation_warnings: list[str] = Field(default_factory=list)
    processing_time_ms: int | None
    created_at: datetime


class EvaluationListResponse(SQLModel):
    """Paginated response for listing evaluations."""

    evaluations: list[EvaluationRecord]
    total: int = Field(description="Total number of evaluations matching filters")
    limit: int
    offset: int
    has_more: bool = Field(description="Whether there are more results")


# -----------------------------------------------------------------------------
# Auth Request/Response Schemas
# -----------------------------------------------------------------------------


class SignupRequest(SQLModel):
    """Request body for user signup."""

    email: str = Field(max_length=255, description="User email address")
    password: str = Field(min_length=8, max_length=128, description="User password (min 8 chars)")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class LoginRequest(SQLModel):
    """Request body for user login."""

    email: str = Field(max_length=255, description="User email address")
    password: str = Field(max_length=128, description="User password")


class AuthResponse(SQLModel):
    """Response for successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiry in seconds")


class UserResponse(SQLModel):
    """Response for user info endpoint."""

    id: UUID
    email: str
    role: str
    tenant_id: UUID
    tenant_name: str
    created_at: datetime


class UsageResponse(SQLModel):
    """Response for the monthly usage metering endpoint."""

    plan: str
    period_start: datetime
    period_end: datetime
    monthly_limit: int | None = Field(
        default=None, description="Evaluations allowed this period (null = unlimited)"
    )
    used: int = Field(description="Evaluations consumed this period")
    remaining: int | None = Field(
        default=None, description="Evaluations left this period (null = unlimited)"
    )
    enforcement_enabled: bool = Field(
        description="Whether the quota is enforced (429 when exceeded) or metering-only"
    )


# -----------------------------------------------------------------------------
# Alerting Schemas (table=False)
# -----------------------------------------------------------------------------

# Allowed enum values for alert rule validation.
ALERT_METRICS = ("drift", "reliability", "unknown_provider")
ALERT_COMPARATORS = ("gt", "lt", "eq")
ALERT_SEVERITIES = ("info", "warning", "critical")
ALERT_DELIVERY_STATUSES = ("pending", "sent", "failed", "no_endpoint")


class AlertRuleCreate(SQLModel):
    """Request body for creating an alert rule."""

    name: str = Field(max_length=120)
    metric: str = Field(description="drift | reliability | unknown_provider")
    comparator: str = Field(default="gt", description="gt | lt | eq")
    threshold: float | None = Field(default=None)
    severity: str = Field(default="warning", description="info | warning | critical")
    enabled: bool = Field(default=True)


class AlertRuleResponse(SQLModel):
    """Response body for an alert rule."""

    id: UUID
    name: str
    metric: str
    comparator: str
    threshold: float | None
    severity: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class WebhookCreate(SQLModel):
    """Request body for creating a webhook endpoint."""

    url: str = Field(max_length=2048, description="HTTPS endpoint to receive alert deliveries")
    description: str | None = Field(default=None, max_length=255)


class WebhookResponse(SQLModel):
    """Response body for a webhook endpoint (never includes the secret)."""

    id: UUID
    url: str
    description: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class WebhookCreatedResponse(SQLModel):
    """Response returned ONCE on webhook creation, includes the signing secret."""

    id: UUID
    url: str
    description: str | None
    enabled: bool
    secret: str = Field(description="HMAC signing secret. Shown only once; store it securely.")
    created_at: datetime
    updated_at: datetime


class WebhookTestResponse(SQLModel):
    """Result of sending a test webhook delivery."""

    webhook_id: UUID
    delivery_status: str
    status_code: int | None = None
    error: str | None = None


class AlertEventRecord(SQLModel):
    """Response body for a single alert event."""

    id: UUID
    evaluation_id: UUID | None
    rule_id: UUID | None
    metric: str
    value: float | None
    threshold: float | None
    severity: str
    message: str
    delivery_status: str
    delivery_attempts: int
    last_error: str | None
    created_at: datetime


class AlertEventListResponse(SQLModel):
    """Paginated response for listing alert events."""

    items: list[AlertEventRecord]
    total: int
    limit: int
    offset: int
    has_more: bool


# -----------------------------------------------------------------------------
# Analytics Schemas (table=False)
# -----------------------------------------------------------------------------


class AnalyticsSummaryResponse(SQLModel):
    """Aggregate analytics summary over a time range."""

    from_ts: datetime
    to_ts: datetime
    total_evaluations: int
    decision_breakdown: dict[str, int] = Field(default_factory=dict)
    avg_drift: float | None = None
    p95_drift: float | None = None
    avg_reliability: float | None = None
    p95_reliability: float | None = None


class AnalyticsTimeseriesBucket(SQLModel):
    """A single time bucket in an analytics timeseries."""

    bucket: datetime
    total: int
    decision_breakdown: dict[str, int] = Field(default_factory=dict)
    avg_drift: float | None = None
    avg_reliability: float | None = None


class AnalyticsTimeseriesResponse(SQLModel):
    """Timeseries analytics over a time range, bucketed by interval."""

    from_ts: datetime
    to_ts: datetime
    interval: str
    buckets: list[AnalyticsTimeseriesBucket] = Field(default_factory=list)


class AnalyticsExtractorStat(SQLModel):
    """Per-vendor extractor analytics."""

    vendor: str | None
    count: int
    avg_drift: float | None = None
    p95_drift: float | None = None
    avg_reliability: float | None = None
    avg_extractor_confidence: float | None = None
    avg_extractor_latency_ms: float | None = None
    decision_breakdown: dict[str, int] = Field(default_factory=dict)


class AnalyticsExtractorResponse(SQLModel):
    """Cross-vendor extractor analytics over a time range (tenant-scoped)."""

    from_ts: datetime
    to_ts: datetime
    extractors: list[AnalyticsExtractorStat] = Field(default_factory=list)
