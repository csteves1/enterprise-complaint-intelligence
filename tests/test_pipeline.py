from __future__ import annotations

from pathlib import Path

import pandas as pd

from eci.schemas import RunStatus
from eci.services import build_services


def _write_input(path: Path) -> Path:
    pd.DataFrame(
        [
            {
                "Complaint ID": "CMP-1",
                "Date Received": "2026-01-10",
                "Customer ID": "CUSTOMER-1",
                "Product": "Credit card",
                "Sub Product": "Retail",
                "Issue": "Refund delay",
                "Company": "Example Bank",
                "State": "SC",
                "Submission Channel": "Web",
                "Amount Disputed": "$125.00",
                "Timely Response": "Yes",
                "Company Response": "Closed with explanation",
                "Consumer Complaint Narrative": "A merchant refund has not appeared after two billing cycles. Contact me at person@example.com.",
            },
            {
                "Complaint ID": "CMP-2",
                "Date Received": "not-a-date",
                "Customer ID": "CUSTOMER-2",
                "Product": "Mortgage",
                "Sub Product": "Servicing",
                "Issue": "Payment processing",
                "Company": "Example Bank",
                "State": "NC",
                "Submission Channel": "Phone",
                "Amount Disputed": "0",
                "Timely Response": "No",
                "Company Response": "In progress",
                "Consumer Complaint Narrative": "The payment was applied to the wrong month and generated collection notices.",
            },
        ]
    ).to_csv(path, index=False)
    return path


def test_pipeline_is_end_to_end_and_idempotent(test_settings, tmp_path: Path) -> None:
    services = build_services(test_settings)
    try:
        source = _write_input(tmp_path / "input.csv")
        first = services.pipeline.run(source)
        assert first.status == RunStatus.PARTIAL
        assert first.rows_read == 2
        assert first.rows_valid == 1
        assert first.rows_rejected == 1
        assert first.rows_inserted == 1
        assert services.database.complaint_count() == 1

        stored = services.database.complaints_dataframe()
        assert "person@example.com" not in stored.loc[0, "complaint_text"]
        assert "[EMAIL_REDACTED]" in stored.loc[0, "complaint_text"]

        rejected = services.database.rejected_records_dataframe()
        serialized_rejection = rejected.to_json()
        assert "CUSTOMER-2" not in serialized_rejection
        assert "cust_" in serialized_rejection

        result = services.rag.ask("Why are customer refunds delayed?", top_k=1)
        assert result.retrieval_count == 1
        assert result.sources[0].complaint_id == "CMP-1"
        assert "CMP-1" in result.answer

        second = services.pipeline.run(source)
        assert second.rows_inserted == 0
        assert second.rows_updated == 0
        assert services.database.complaint_count() == 1
    finally:
        services.close()


def test_pipeline_records_failed_run_when_row_limit_is_exceeded(test_settings, tmp_path: Path) -> None:
    import pytest

    limited = test_settings.model_copy(update={"max_input_rows": 1})
    services = build_services(limited)
    try:
        source = _write_input(tmp_path / "too_many_rows.csv")
        with pytest.raises(ValueError, match="row safety limit"):
            services.pipeline.run(source)
        runs = services.database.ingestion_runs_dataframe()
        assert runs.loc[0, "status"] == "FAILED"
        assert "ValueError" in runs.loc[0, "error_message"]
    finally:
        services.close()
