"""Pydantic data contracts for validated records and service boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubmissionChannel(StrEnum):
    WEB = "Web"
    PHONE = "Phone"
    EMAIL = "Email"
    POSTAL_MAIL = "Postal mail"
    REFERRAL = "Referral"


class ComplaintStatus(StrEnum):
    CLOSED = "Closed"
    CLOSED_WITH_EXPLANATION = "Closed with explanation"
    CLOSED_WITH_RELIEF = "Closed with relief"
    IN_PROGRESS = "In progress"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ComplaintRecord(BaseModel):
    """Canonical validated complaint stored in the relational database."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    complaint_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Z0-9_-]+$")
    date_received: date
    customer_ref: str = Field(min_length=10, max_length=64)
    product: str = Field(min_length=2, max_length=120)
    sub_product: str | None = Field(default=None, max_length=120)
    issue: str = Field(min_length=3, max_length=200)
    company: str = Field(min_length=2, max_length=200)
    state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    channel: SubmissionChannel
    amount_disputed: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    timely_response: bool
    status: ComplaintStatus
    complaint_text: str = Field(min_length=20, max_length=8000)
    source_file: str = Field(min_length=1, max_length=255)
    source_row_number: int = Field(ge=2)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    ingestion_run_id: str = Field(min_length=36, max_length=36)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("complaint_id")
    @classmethod
    def normalize_complaint_id(cls, value: str) -> str:
        return value.upper()

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("date_received")
    @classmethod
    def validate_date_received(cls, value: date) -> date:
        if value < date(2000, 1, 1):
            raise ValueError("date_received cannot be earlier than 2000-01-01")
        if value > date.today() + timedelta(days=1):
            raise ValueError("date_received cannot be in the future")
        return value


class VectorDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    complaint_id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any]


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str | None = None
    state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    company: str | None = None


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complaint_id: str
    text: str
    score: float = Field(ge=-1.0, le=1.0)
    distance: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any]


class AnswerResult(BaseModel):
    answer: str
    sources: list[SearchResult]
    model_name: str
    retrieval_count: int
    query: str


class PipelineSummary(BaseModel):
    run_id: str
    status: RunStatus
    source_file: str
    rows_read: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    vectors_upserted: int = 0
    processed_file: str | None = None
    rejected_file: str | None = None
    error_message: str | None = None


class ComponentHealth(BaseModel):
    component: str
    healthy: bool
    detail: str
