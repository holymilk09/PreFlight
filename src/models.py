"""SQLModel models for database tables and API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator
from sqlmodel import Column, Field as SQLField, Relationship, SQLModel
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from uuid7 import uuid7


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


class AuditAction(str, Enum):
    """Audit log action types."""

    API_KEY_CREATED = "api_key_created"
    API_KEY_ROTATED = "api_key_rotated"
    API_KEY_REVOKED = "api_key_revoked"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    EVALUATION_REQUESTED = "evaluation_requested"
    AUTH_FAILED = "auth_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


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
    correction_rules: list[dict[str, Any]] = SQLField(
        default_factory=list, sa_column=Column(JSONB)
    )
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

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    correlation_id: str = SQLField(max_length=255, nullable=False, index=True)
    document_hash: str = SQLField(max_length=64, nullable=False)
    template_id: UUID | None = SQLField(foreign_key="templates.id", default=None)
    decision: Decision = SQLField(nullable=False)
    match_confidence: float | None = SQLField(default=None)
    drift_score: float | None = SQLField(default=None)
    reliability_score: float | None = SQLField(default=None)
    correction_rules: list[dict[str, Any]] = SQLField(
        default_factory=list, sa_column=Column(JSONB)
    )
    extractor_vendor: str | None = SQLField(max_length=100, default=None)
    extractor_model: str | None = SQLField(max_length=100, default=None)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    processing_time_ms: int | None = SQLField(default=None)


class AuditLog(SQLModel, table=True):
    """Audit log for security-sensitive operations.

    Note: No RLS on this table - admin access only via separate connection.
    """

    __tablename__ = "audit_log"

    id: int | None = SQLField(default=None, primary_key=True)
    timestamp: datetime = SQLField(default_factory=datetime.utcnow, index=True)
    tenant_id: UUID | None = SQLField(default=None, index=True)
    actor_id: UUID | None = SQLField(default=None)
    action: AuditAction = SQLField(nullable=False)
    resource_type: str | None = SQLField(max_length=100, default=None)
    resource_id: UUID | None = SQLField(default=None)
    details: dict[str, Any] | None = SQLField(default=None, sa_column=Column(JSONB))
    ip_address: str | None = SQLField(default=None, max_length=45)  # IPv6 max length
    request_id: UUID | None = SQLField(default=None)


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
    client_doc_hash: str = Field(max_length=64, description="Client's document SHA256 (we never see content)")
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


class HealthResponse(SQLModel):
    """Health check response."""

    status: str
    version: str = "0.1.0"
