"""Pandas transformations that normalize raw data without hiding bad rows."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from eci.exceptions import DataContractError

COLUMN_ALIASES = {
    "complaintid": "complaint_id",
    "complaint_id": "complaint_id",
    "id": "complaint_id",
    "date_received": "date_received",
    "received_date": "date_received",
    "customer_id": "customer_id",
    "customerid": "customer_id",
    "product": "product",
    "sub_product": "sub_product",
    "subproduct": "sub_product",
    "issue": "issue",
    "company": "company",
    "state": "state",
    "submission_channel": "channel",
    "channel": "channel",
    "amount_disputed": "amount_disputed",
    "disputed_amount": "amount_disputed",
    "timely_response": "timely_response",
    "timely": "timely_response",
    "status": "status",
    "company_response": "status",
    "complaint_text": "complaint_text",
    "consumer_complaint_narrative": "complaint_text",
    "narrative": "complaint_text",
}

REQUIRED_COLUMNS = {
    "complaint_id",
    "date_received",
    "customer_id",
    "product",
    "issue",
    "company",
    "channel",
    "timely_response",
    "status",
    "complaint_text",
}

STATE_NAMES = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
}

CHANNEL_MAP = {
    "web": "Web",
    "online": "Web",
    "phone": "Phone",
    "telephone": "Phone",
    "email": "Email",
    "e-mail": "Email",
    "postal mail": "Postal mail",
    "mail": "Postal mail",
    "referral": "Referral",
}

STATUS_MAP = {
    "closed": "Closed",
    "closed with explanation": "Closed with explanation",
    "closed with monetary relief": "Closed with relief",
    "closed with non-monetary relief": "Closed with relief",
    "closed with relief": "Closed with relief",
    "in progress": "In progress",
    "open": "In progress",
}

TRUE_VALUES = {"true", "t", "yes", "y", "1", "timely"}
FALSE_VALUES = {"false", "f", "no", "n", "0", "untimely"}


def normalize_column_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return COLUMN_ALIASES.get(normalized, normalized)


def check_data_contract(frame: pd.DataFrame) -> None:
    normalized = {normalize_column_name(column) for column in frame.columns}
    missing = sorted(REQUIRED_COLUMNS - normalized)
    if missing:
        raise DataContractError(
            "Input file is missing required columns: " + ", ".join(missing)
        )


def _clean_string(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _clean_amount(value: Any) -> Decimal | None:
    text = _clean_string(value)
    if text is None:
        return None
    negative = text.startswith("(") and text.endswith(")")
    normalized = re.sub(r"[^0-9.\-]", "", text)
    if not normalized:
        return None
    try:
        amount = Decimal(normalized)
        return -amount if negative and amount > 0 else amount
    except InvalidOperation:
        return None


def _clean_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _clean_string(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return None


def _clean_state(value: Any) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    upper = text.upper().replace(".", "")
    if upper in STATE_NAMES:
        return STATE_NAMES[upper]
    return upper if len(upper) == 2 and upper.isalpha() else upper


def _mapped_value(value: Any, mapping: dict[str, str]) -> str | None:
    text = _clean_string(value)
    if text is None:
        return None
    return mapping.get(text.lower(), text)


def clean_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized frame while retaining rows for later validation."""
    check_data_contract(frame)
    cleaned = frame.copy()
    cleaned.columns = [normalize_column_name(column) for column in cleaned.columns]

    # Duplicate aliases can map to the same canonical name. Keep the first one
    # deterministically rather than allowing ambiguous downstream behavior.
    cleaned = cleaned.loc[:, ~cleaned.columns.duplicated(keep="first")]

    for column in cleaned.columns:
        if column not in {"date_received", "amount_disputed", "timely_response"}:
            cleaned[column] = cleaned[column].map(_clean_string)

    cleaned["complaint_id"] = cleaned["complaint_id"].map(
        lambda value: value.upper().replace(" ", "_") if value else value
    )
    cleaned["date_received"] = pd.to_datetime(
        cleaned["date_received"], errors="coerce", format="mixed"
    ).dt.date
    cleaned["amount_disputed"] = cleaned.get(
        "amount_disputed", pd.Series([None] * len(cleaned), index=cleaned.index)
    ).map(_clean_amount)
    cleaned["timely_response"] = cleaned["timely_response"].map(
        lambda value: (bool(result) if (result := _clean_boolean(value)) is not None else None)
    ).astype(object)
    cleaned["state"] = cleaned.get(
        "state", pd.Series([None] * len(cleaned), index=cleaned.index)
    ).map(_clean_state)
    cleaned["channel"] = cleaned["channel"].map(
        lambda value: _mapped_value(value, CHANNEL_MAP)
    )
    cleaned["status"] = cleaned["status"].map(
        lambda value: _mapped_value(value, STATUS_MAP)
    )
    if "sub_product" not in cleaned:
        cleaned["sub_product"] = None

    cleaned["_duplicate_in_file"] = cleaned["complaint_id"].duplicated(keep="first")
    cleaned["_source_row_number"] = range(2, len(cleaned) + 2)
    return cleaned


def profile_dataframe(frame: pd.DataFrame) -> dict[str, Any]:
    """Produce lightweight profiling metrics for the operations screen."""
    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "null_counts": {column: int(count) for column, count in frame.isna().sum().items()},
    }
