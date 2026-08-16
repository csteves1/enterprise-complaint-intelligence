"""Generate deterministic synthetic complaint data, including deliberate defects."""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PRODUCTS = {
    "Credit card": [
        ("Disputed transaction", "A card transaction was posted that I did not recognize. I reported it immediately, but the temporary credit was removed before the investigation was complete."),
        ("Late fee", "The payment portal failed on the due date and the company charged a late fee even though I tried to pay on time."),
        ("Refund delay", "A merchant issued a refund, but the credit card company has not posted it after several billing cycles."),
    ],
    "Mortgage": [
        ("Payment processing", "My mortgage payment was applied to the wrong month, causing the account to appear delinquent and generating collection notices."),
        ("Escrow", "The escrow analysis increased my monthly payment without a clear explanation, and repeated calls did not resolve the calculation."),
        ("Loan modification", "I submitted all requested loan modification documents, but the servicer repeatedly said the package was incomplete."),
    ],
    "Checking account": [
        ("Account access", "My checking account was frozen after a routine mobile deposit, and customer service could not explain what documents were still required."),
        ("Overdraft fee", "Several overdraft fees were assessed after transactions were reordered, even though the displayed balance had been positive."),
        ("Deposit hold", "A payroll check was held much longer than expected, which caused scheduled bill payments to fail."),
    ],
    "Auto loan": [
        ("Payment allocation", "Extra principal payments were applied as future monthly payments instead of reducing the loan balance."),
        ("Title delay", "The loan was paid in full, but the lien release and vehicle title were not sent within the promised time."),
        ("Repossession dispute", "The lender scheduled repossession despite a confirmed payment arrangement and a recent payment receipt."),
    ],
    "Credit reporting": [
        ("Incorrect account", "An account that does not belong to me appears on my credit report, and the investigation response did not address the documents I supplied."),
        ("Identity theft", "I submitted an identity theft report, but the fraudulent account was reinserted after it had been removed."),
        ("Investigation delay", "The bureau marked my dispute complete without correcting the balance or explaining how the disputed information was verified."),
    ],
}

COMPANIES = ["Harbor National Bank", "Pioneer Financial", "Summit Credit Services", "Blue Ridge Lending"]
STATES = ["SC", "North Carolina", "AL", "Texas", "OH", "Indiana", "GA", "TN"]
CHANNELS = ["Web", "online", "Phone", "E-mail", "Referral", "mail"]
STATUSES = ["Closed", "Closed with explanation", "Closed with monetary relief", "In progress"]


def generate(output: Path, rows: int = 80, seed: int = 2026) -> Path:
    random.seed(seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    today = date.today()
    records: list[dict[str, object]] = []

    product_names = list(PRODUCTS)
    for index in range(rows):
        product = random.choice(product_names)
        issue, narrative = random.choice(PRODUCTS[product])
        company = random.choice(COMPANIES)
        received = today - timedelta(days=random.randint(10, 700))
        date_formats = [
            received.isoformat(),
            received.strftime("%m/%d/%Y"),
            received.strftime("%b %d, %Y"),
        ]
        amount = random.choice(["", "$125.00", "$1,240.50", "85.75", "$3,500", "0"])
        text = (
            f"{narrative} The issue involved {company}. "
            f"I contacted support twice and requested a written explanation."
        )
        if index == 3:
            text += " My email was customer@example.com and my phone was 843-555-0142."
        if index == 9:
            text += " The form contained SSN 123-45-6789 and card 4111 1111 1111 1111."

        records.append(
            {
                "Complaint ID": f"CMP-{1000 + index}",
                "Date Received": random.choice(date_formats),
                "Customer ID": f"CUST-{random.randint(100, 145)}",
                "Product": product,
                "Sub Product": random.choice(["", "Retail", "Servicing", "Consumer"]),
                "Issue": issue,
                "Company": company,
                "State": random.choice(STATES),
                "Submission Channel": random.choice(CHANNELS),
                "Amount Disputed": amount,
                "Timely Response": random.choice(["Yes", "No", "true", "0", "timely"]),
                "Company Response": random.choice(STATUSES),
                "Consumer Complaint Narrative": text,
            }
        )

    # Deliberate data-quality defects demonstrate quarantine and audit behavior.
    records.extend(
        [
            {**records[0], "Complaint ID": "", "Customer ID": "CUST-BAD-1"},
            {**records[1], "Complaint ID": "CMP-BADDATE", "Date Received": "2099-01-01"},
            {**records[2], "Complaint ID": "CMP-NEGAMT", "Amount Disputed": "-$20.00"},
            {**records[3], "Complaint ID": "CMP-BADCHANNEL", "Submission Channel": "Carrier pigeon"},
            {**records[4], "Complaint ID": "CMP-SHORTTEXT", "Consumer Complaint Narrative": "Too short"},
            {**records[5], "Complaint ID": "CMP-BADSTATE", "State": "South Carolina?"},
            {**records[0], "Customer ID": "CUST-DUPLICATE"},
        ]
    )

    pd.DataFrame(records).to_csv(output, index=False, encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw/complaints_raw.csv"))
    parser.add_argument("--rows", type=int, default=80)
    args = parser.parse_args()
    print(generate(args.output, args.rows).resolve())


if __name__ == "__main__":
    main()
