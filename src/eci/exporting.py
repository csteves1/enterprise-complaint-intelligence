"""Generate clean CSV extracts that mirror the future Power BI model."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from eci.database import Database
from eci.security import sanitize_for_csv


def export_powerbi_files(database: Database, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    complaints = database.complaints_dataframe()
    if complaints.empty:
        raise ValueError("No complaint records are available. Run ingestion first.")

    complaints["date_received"] = pd.to_datetime(complaints["date_received"])
    complaints["month"] = complaints["date_received"].dt.to_period("M").astype(str)
    for column in complaints.select_dtypes(include=["object"]).columns:
        complaints[column] = complaints[column].map(sanitize_for_csv)

    detail_path = output_dir / "complaints_detail.csv"
    complaints.to_csv(detail_path, index=False)

    monthly = (
        complaints.groupby("month", dropna=False)
        .agg(
            complaint_count=("complaint_id", "count"),
            timely_response_rate=("timely_response", "mean"),
            disputed_amount=("amount_disputed", "sum"),
        )
        .reset_index()
    )
    monthly["timely_response_rate"] = monthly["timely_response_rate"] * 100
    monthly_path = output_dir / "monthly_metrics.csv"
    monthly.to_csv(monthly_path, index=False)

    products = (
        complaints.groupby("product", dropna=False)
        .agg(
            complaint_count=("complaint_id", "count"),
            timely_response_rate=("timely_response", "mean"),
            disputed_amount=("amount_disputed", "sum"),
        )
        .reset_index()
        .sort_values("complaint_count", ascending=False)
    )
    products["timely_response_rate"] = products["timely_response_rate"] * 100
    product_path = output_dir / "product_metrics.csv"
    products.to_csv(product_path, index=False)

    runs = database.ingestion_runs_dataframe(limit=500)
    runs_path = output_dir / "ingestion_runs.csv"
    runs.to_csv(runs_path, index=False)

    rejections = database.rejected_records_dataframe(limit=10_000)
    rejection_path = output_dir / "rejected_records.csv"
    if not rejections.empty:
        # Keep the Power BI extract diagnostic but privacy-minimized. The full
        # redacted source record remains in the operational table and CSV.
        rejections = rejections.drop(columns=["redacted_record"], errors="ignore")
    rejections.to_csv(rejection_path, index=False)

    return [detail_path, monthly_path, product_path, runs_path, rejection_path]
