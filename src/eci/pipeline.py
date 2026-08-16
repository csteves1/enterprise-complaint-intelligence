"""End-to-end ingestion pipeline: CSV -> clean -> validate -> SQL -> vectors."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from eci.cleaning import clean_dataframe, profile_dataframe
from eci.config import Settings
from eci.database import Database
from eci.embeddings import EmbeddingProvider
from eci.schemas import ComplaintRecord, PipelineSummary, RunStatus, VectorDocument
from eci.security import (
    pseudonymize,
    redact_pii,
    sanitize_for_csv,
    sha256_file,
    stable_content_hash,
)
from eci.vector_store import VectorStore

LOGGER = logging.getLogger(__name__)


class PipelineRunner:
    """Coordinates the complete, restart-safe ingestion workflow."""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.settings = settings
        self.database = database
        self.embeddings = embeddings
        self.vector_store = vector_store

    @staticmethod
    def _clean_scalar(value: Any) -> Any:
        """Convert Pandas missing-value sentinels to plain ``None`` safely."""
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            # Container values are not expected here, but retaining them is safer
            # than raising from a diagnostic or quarantine code path.
            pass
        return value

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        value = cls._clean_scalar(value)
        if value is None:
            return None
        if isinstance(value, (date, datetime, Decimal)):
            return str(value)
        return value

    def _redacted_raw_record(self, row: pd.Series) -> dict[str, Any]:
        record: dict[str, Any] = {}
        for key, value in row.items():
            key_name = str(key)
            if key_name.startswith("_"):
                continue
            safe = self._json_safe(value)
            if key_name == "customer_id" and safe:
                safe = pseudonymize(
                    str(safe),
                    self.settings.hmac_secret.get_secret_value(),
                )
            elif isinstance(safe, str):
                safe = redact_pii(safe)
            record[key_name] = safe
        return record

    @staticmethod
    def _validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
        return [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]

    def _candidate(
        self, row: pd.Series, *, run_id: str, source_name: str
    ) -> dict[str, Any]:
        scalar = self._clean_scalar
        complaint_text_value = scalar(row.get("complaint_text"))
        complaint_text = str(complaint_text_value or "")
        if self.settings.pii_redaction_enabled:
            complaint_text = redact_pii(complaint_text)

        customer_value = scalar(row.get("customer_id"))
        raw_customer_id = str(customer_value or "").strip()
        customer_ref = (
            pseudonymize(
                raw_customer_id,
                self.settings.hmac_secret.get_secret_value(),
            )
            if raw_customer_id
            else ""
        )

        normalized = {
            "complaint_id": scalar(row.get("complaint_id")),
            "date_received": scalar(row.get("date_received")),
            "product": scalar(row.get("product")),
            "sub_product": scalar(row.get("sub_product")),
            "issue": scalar(row.get("issue")),
            "company": scalar(row.get("company")),
            "state": scalar(row.get("state")),
            "channel": scalar(row.get("channel")),
            "amount_disputed": scalar(row.get("amount_disputed")),
            "timely_response": scalar(row.get("timely_response")),
            "status": scalar(row.get("status")),
        }
        content_hash = stable_content_hash(
            [
                normalized["complaint_id"],
                normalized["date_received"],
                customer_ref,
                normalized["product"],
                normalized["sub_product"],
                normalized["issue"],
                normalized["company"],
                normalized["state"],
                normalized["channel"],
                normalized["amount_disputed"],
                normalized["timely_response"],
                normalized["status"],
                complaint_text,
            ]
        )
        return {
            **normalized,
            "customer_ref": customer_ref,
            "complaint_text": complaint_text,
            "source_file": source_name,
            "source_row_number": int(row["_source_row_number"]),
            "content_hash": content_hash,
            "ingestion_run_id": run_id,
        }

    def _write_outputs(
        self,
        *,
        run_id: str,
        source_stem: str,
        records: list[ComplaintRecord],
        rejected: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> tuple[Path, Path]:
        processed_path = self.settings.processed_data_dir / f"{source_stem}_{run_id}_valid.csv"
        rejected_path = self.settings.rejected_data_dir / f"{source_stem}_{run_id}_rejected.csv"
        profile_path = self.settings.processed_data_dir / f"{source_stem}_{run_id}_profile.json"

        processed_rows = []
        for record in records:
            row = record.model_dump(mode="json")
            processed_rows.append({key: sanitize_for_csv(value) for key, value in row.items()})
        pd.DataFrame(processed_rows).to_csv(processed_path, index=False, encoding="utf-8")

        rejected_rows = []
        for item in rejected:
            rejected_rows.append(
                {
                    "source_row_number": item["source_row_number"],
                    "complaint_id": sanitize_for_csv(item.get("complaint_id")),
                    "validation_errors": json.dumps(item["validation_errors"], ensure_ascii=False),
                    "redacted_record": json.dumps(item["redacted_record"], ensure_ascii=False, default=str),
                }
            )
        pd.DataFrame(
            rejected_rows,
            columns=[
                "source_row_number",
                "complaint_id",
                "validation_errors",
                "redacted_record",
            ],
        ).to_csv(rejected_path, index=False, encoding="utf-8")

        with profile_path.open("w", encoding="utf-8") as handle:
            json.dump(profile, handle, indent=2, ensure_ascii=False, default=str)
        return processed_path, rejected_path

    def _vector_documents(self, records: list[ComplaintRecord]) -> list[VectorDocument]:
        if not records:
            return []
        embedding_inputs = [
            (
                f"Product: {record.product}. Issue: {record.issue}. "
                f"Company: {record.company}. Complaint narrative: {record.complaint_text}"
            )
            for record in records
        ]
        vectors = self.embeddings.embed_documents(embedding_inputs)
        if len(vectors) != len(records):
            raise RuntimeError("Embedding provider returned an unexpected number of vectors.")

        return [
            VectorDocument(
                document_id=record.complaint_id,
                complaint_id=record.complaint_id,
                text=record.complaint_text,
                vector=vector,
                metadata={
                    "product": record.product,
                    "company": record.company,
                    "state": record.state,
                    "issue": record.issue,
                    "date_received": record.date_received.isoformat(),
                    "content_hash": record.content_hash,
                },
            )
            for record, vector in zip(records, vectors)
        ]

    def run(self, source_path: Path) -> PipelineSummary:
        source_path = source_path.resolve()
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")
        if source_path.suffix.lower() != ".csv":
            raise ValueError("This first version accepts CSV input only.")
        maximum_bytes = self.settings.max_input_file_mb * 1024 * 1024
        if source_path.stat().st_size > maximum_bytes:
            raise ValueError(
                f"Input file exceeds the {self.settings.max_input_file_mb} MB safety limit."
            )

        self.database.create_schema()
        self.vector_store.initialize()

        run_id = str(uuid.uuid4())
        source_hash = sha256_file(source_path)
        source_name = source_path.name
        self.database.start_ingestion_run(run_id, source_name, source_hash)

        rows_read = rows_valid = rows_rejected = 0
        rows_inserted = rows_updated = vectors_upserted = 0
        processed_path: Path | None = None
        rejected_path: Path | None = None

        try:
            raw = pd.read_csv(
                source_path,
                dtype=str,
                keep_default_na=False,
                encoding="utf-8",
                encoding_errors="replace",
            )
            rows_read = len(raw)
            if rows_read > self.settings.max_input_rows:
                raise ValueError(
                    f"Input contains {rows_read:,} rows, exceeding the "
                    f"{self.settings.max_input_rows:,}-row safety limit."
                )
            profile = profile_dataframe(raw)
            cleaned = clean_dataframe(raw)

            valid_records: list[ComplaintRecord] = []
            rejected: list[dict[str, Any]] = []
            for _, row in cleaned.iterrows():
                source_row_number = int(row["_source_row_number"])
                complaint_id = self._json_safe(row.get("complaint_id"))
                if bool(row["_duplicate_in_file"]):
                    rejected.append(
                        {
                            "source_row_number": source_row_number,
                            "complaint_id": complaint_id,
                            "validation_errors": [
                                {
                                    "field": "complaint_id",
                                    "message": "Duplicate complaint_id within the input file",
                                    "type": "duplicate_record",
                                }
                            ],
                            "redacted_record": self._redacted_raw_record(row),
                        }
                    )
                    continue

                candidate = self._candidate(row, run_id=run_id, source_name=source_name)
                try:
                    valid_records.append(ComplaintRecord.model_validate(candidate))
                except ValidationError as exc:
                    rejected.append(
                        {
                            "source_row_number": source_row_number,
                            "complaint_id": complaint_id,
                            "validation_errors": self._validation_errors(exc),
                            "redacted_record": self._redacted_raw_record(row),
                        }
                    )

            rows_valid = len(valid_records)
            rows_rejected = len(rejected)
            profile.update(
                {
                    "run_id": run_id,
                    "source_sha256": source_hash,
                    "valid_rows": rows_valid,
                    "rejected_rows": rows_rejected,
                    "embedding_model": self.embeddings.model_name,
                    "vector_backend": self.settings.vector_backend,
                }
            )
            processed_path, rejected_path = self._write_outputs(
                run_id=run_id,
                source_stem=source_path.stem,
                records=valid_records,
                rejected=rejected,
                profile=profile,
            )

            self.database.add_rejected_records(run_id, rejected)
            rows_inserted, rows_updated = self.database.upsert_complaints(valid_records)
            vector_documents = self._vector_documents(valid_records)
            vectors_upserted = self.vector_store.upsert(vector_documents)

            status = RunStatus.PARTIAL if rejected else RunStatus.SUCCEEDED
            self.database.complete_ingestion_run(
                run_id,
                status=status,
                rows_read=rows_read,
                rows_valid=rows_valid,
                rows_rejected=rows_rejected,
                rows_inserted=rows_inserted,
                rows_updated=rows_updated,
                vectors_upserted=vectors_upserted,
            )
            LOGGER.info(
                "Ingestion completed",
                extra={
                    "run_id": run_id,
                    "status": status.value,
                    "rows_read": rows_read,
                    "rows_valid": rows_valid,
                    "rows_rejected": rows_rejected,
                },
            )
            return PipelineSummary(
                run_id=run_id,
                status=status,
                source_file=source_name,
                rows_read=rows_read,
                rows_valid=rows_valid,
                rows_rejected=rows_rejected,
                rows_inserted=rows_inserted,
                rows_updated=rows_updated,
                vectors_upserted=vectors_upserted,
                processed_file=str(processed_path),
                rejected_file=str(rejected_path),
            )
        except Exception as exc:
            LOGGER.exception("Ingestion failed", extra={"run_id": run_id})
            error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
            try:
                self.database.complete_ingestion_run(
                    run_id,
                    status=RunStatus.FAILED,
                    rows_read=rows_read,
                    rows_valid=rows_valid,
                    rows_rejected=rows_rejected,
                    rows_inserted=rows_inserted,
                    rows_updated=rows_updated,
                    vectors_upserted=vectors_upserted,
                    error_message=error_message,
                )
            except Exception:
                LOGGER.exception("Could not finalize failed ingestion audit record")
            raise
