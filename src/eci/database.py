"""SQLAlchemy models and transactional repository operations."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Iterator, Sequence

import pandas as pd
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from eci.config import Settings
from eci.exceptions import DatabaseOperationError
from eci.schemas import ComplaintRecord, RunStatus

LOGGER = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class ComplaintModel(Base):
    __tablename__ = "complaints"

    complaint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date_received: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    sub_product: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issue: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    amount_disputed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    timely_response: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    complaint_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ingestion_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ingestion_runs.run_id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_complaints_product_date", "product", "date_received"),
        Index("ix_complaints_company_state", "company", "state"),
    )


class IngestionRunModel(Base):
    __tablename__ = "ingestion_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vectors_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    app_version: Mapped[str] = mapped_column(String(30), nullable=False)


class RejectedRecordModel(Base):
    __tablename__ = "rejected_records"

    rejection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ingestion_runs.run_id"), nullable=False, index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    complaint_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    redacted_record: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class QueryAuditModel(Base):
    __tablename__ = "query_audit"

    query_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    vector_backend: Mapped[str] = mapped_column(String(30), nullable=False)
    answer_backend: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    retrieved_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_class: Mapped[str | None] = mapped_column(String(120))


class Database:
    """Owns the SQLAlchemy engine and all database transactions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        engine_kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
        if settings.is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs.update(
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_recycle=settings.database_pool_recycle_seconds,
            )
        self.engine: Engine = create_engine(settings.database_url, **engine_kwargs)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

    def create_schema(self) -> None:
        try:
            Base.metadata.create_all(self.engine)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not create the database schema.") from exc

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> tuple[bool, str]:
        started = time.perf_counter()
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            elapsed = (time.perf_counter() - started) * 1000
            return True, f"Connected ({elapsed:.0f} ms)"
        except SQLAlchemyError:
            LOGGER.exception("Database health check failed")
            return False, "Database connection failed"

    def start_ingestion_run(
        self, run_id: str, source_file: str, source_sha256: str
    ) -> None:
        try:
            with self.session_scope() as session:
                session.add(
                    IngestionRunModel(
                        run_id=run_id,
                        source_file=source_file,
                        source_sha256=source_sha256,
                        status=RunStatus.RUNNING.value,
                        app_version=self.settings.app_version,
                    )
                )
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not create the ingestion audit record.") from exc

    def complete_ingestion_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        rows_read: int,
        rows_valid: int,
        rows_rejected: int,
        rows_inserted: int,
        rows_updated: int,
        vectors_upserted: int,
        error_message: str | None = None,
    ) -> None:
        try:
            with self.session_scope() as session:
                run = session.get(IngestionRunModel, run_id)
                if run is None:
                    raise DatabaseOperationError(f"Ingestion run {run_id} was not found.")
                run.status = status.value
                run.completed_at = datetime.now(UTC)
                run.rows_read = rows_read
                run.rows_valid = rows_valid
                run.rows_rejected = rows_rejected
                run.rows_inserted = rows_inserted
                run.rows_updated = rows_updated
                run.vectors_upserted = vectors_upserted
                run.error_message = error_message
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not finalize the ingestion audit record.") from exc

    def upsert_complaints(self, records: Sequence[ComplaintRecord]) -> tuple[int, int]:
        """Idempotently insert new complaints and update changed complaints."""
        inserted = 0
        updated = 0
        try:
            with self.session_scope() as session:
                for record in records:
                    existing = session.get(ComplaintModel, record.complaint_id)
                    values = record.model_dump()
                    values["channel"] = record.channel.value
                    values["status"] = record.status.value
                    values.pop("ingested_at", None)
                    if existing is None:
                        session.add(ComplaintModel(**values))
                        inserted += 1
                        continue
                    if existing.content_hash == record.content_hash:
                        continue
                    for field, value in values.items():
                        setattr(existing, field, value)
                    existing.updated_at = datetime.now(UTC)
                    updated += 1
            return inserted, updated
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Complaint upsert transaction failed.") from exc

    def add_rejected_records(
        self, run_id: str, rejected: Sequence[dict[str, Any]]
    ) -> None:
        if not rejected or not self.settings.store_rejected_rows_in_database:
            return
        try:
            with self.session_scope() as session:
                session.add_all(
                    [
                        RejectedRecordModel(
                            run_id=run_id,
                            source_row_number=int(item["source_row_number"]),
                            complaint_id=item.get("complaint_id"),
                            validation_errors=item["validation_errors"],
                            redacted_record=item["redacted_record"],
                        )
                        for item in rejected
                    ]
                )
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not persist rejected-record diagnostics.") from exc

    def record_query_audit(
        self,
        *,
        query_hash: str,
        vector_backend: str,
        answer_backend: str,
        model_name: str,
        retrieved_ids: list[str],
        duration_ms: int,
        succeeded: bool,
        error_class: str | None,
    ) -> None:
        if not self.settings.audit_user_queries:
            return
        try:
            with self.session_scope() as session:
                session.add(
                    QueryAuditModel(
                        query_hash=query_hash,
                        vector_backend=vector_backend,
                        answer_backend=answer_backend,
                        model_name=model_name,
                        retrieved_ids=retrieved_ids,
                        duration_ms=duration_ms,
                        succeeded=succeeded,
                        error_class=error_class,
                    )
                )
        except SQLAlchemyError:
            # Audit logging must not break the primary user operation.
            LOGGER.exception("Query audit persistence failed")

    def complaints_dataframe(self) -> pd.DataFrame:
        columns = [
            ComplaintModel.complaint_id,
            ComplaintModel.date_received,
            ComplaintModel.product,
            ComplaintModel.sub_product,
            ComplaintModel.issue,
            ComplaintModel.company,
            ComplaintModel.state,
            ComplaintModel.channel,
            ComplaintModel.amount_disputed,
            ComplaintModel.timely_response,
            ComplaintModel.status,
            ComplaintModel.complaint_text,
            ComplaintModel.updated_at,
        ]
        try:
            return pd.read_sql(select(*columns), self.engine)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not read complaint analytics data.") from exc

    def ingestion_runs_dataframe(self, limit: int = 50) -> pd.DataFrame:
        statement = (
            select(IngestionRunModel)
            .order_by(IngestionRunModel.started_at.desc())
            .limit(limit)
        )
        try:
            return pd.read_sql(statement, self.engine)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not read ingestion audit data.") from exc

    def rejected_records_dataframe(self, limit: int = 200) -> pd.DataFrame:
        statement = (
            select(RejectedRecordModel)
            .order_by(RejectedRecordModel.rejection_id.desc())
            .limit(limit)
        )
        try:
            return pd.read_sql(statement, self.engine)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not read rejected-record data.") from exc

    def complaint_count(self) -> int:
        try:
            with self.session_scope() as session:
                return int(session.scalar(select(func.count()).select_from(ComplaintModel)) or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Could not count complaints.") from exc
