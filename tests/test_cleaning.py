from __future__ import annotations

from decimal import Decimal

import pandas as pd

from eci.cleaning import clean_dataframe


def test_cleaning_normalizes_aliases_and_values() -> None:
    raw = pd.DataFrame(
        [
            {
                "Complaint ID": " cmp 100 ",
                "Date Received": "01/20/2026",
                "Customer ID": " customer-1 ",
                "Product": "Credit card",
                "Issue": "Refund delay",
                "Company": "Example Bank",
                "State": "South Carolina",
                "Submission Channel": "online",
                "Amount Disputed": "$1,240.50",
                "Timely Response": "yes",
                "Company Response": "closed with monetary relief",
                "Consumer Complaint Narrative": " A sufficiently long complaint narrative for validation. ",
            }
        ]
    )

    cleaned = clean_dataframe(raw)
    assert cleaned.loc[0, "complaint_id"] == "CMP_100"
    assert cleaned.loc[0, "state"] == "SC"
    assert cleaned.loc[0, "channel"] == "Web"
    assert cleaned.loc[0, "amount_disputed"] == Decimal("1240.50")
    assert cleaned.loc[0, "timely_response"] is True
    assert cleaned.loc[0, "status"] == "Closed with relief"


def test_missing_required_column_fails_contract() -> None:
    import pytest

    from eci.exceptions import DataContractError

    with pytest.raises(DataContractError):
        clean_dataframe(pd.DataFrame([{"Complaint ID": "CMP-1"}]))
