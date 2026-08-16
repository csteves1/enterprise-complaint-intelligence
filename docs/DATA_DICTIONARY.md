# Data Dictionary

## Canonical complaint record

| Field | Type | Required | Rule | Destination |
|---|---|---:|---|---|
| complaint_id | string | yes | 4-64 chars; uppercase letters, digits, `_`, `-`; primary key | SQL and vector metadata |
| date_received | date | yes | 2000-01-01 through tomorrow | SQL and vector metadata |
| customer_ref | string | yes | HMAC pseudonym, never raw customer ID | SQL only |
| product | string | yes | 2-120 chars | SQL and vector metadata |
| sub_product | string | no | up to 120 chars | SQL |
| issue | string | yes | 3-200 chars | SQL and vector metadata |
| company | string | yes | 2-200 chars | SQL and vector metadata |
| state | string | no | two uppercase letters | SQL and vector metadata |
| channel | enum | yes | Web, Phone, Email, Postal mail, Referral | SQL |
| amount_disputed | decimal | no | 0 through 10,000,000 | SQL |
| timely_response | boolean | yes | normalized from common true/false values | SQL |
| status | enum | yes | Closed, Closed with explanation, Closed with relief, In progress | SQL |
| complaint_text | string | yes | 20-8000 chars; PII-masked before validation and storage | SQL and vector text |
| source_file | string | yes | basename of ingested file | SQL |
| source_row_number | integer | yes | CSV row number, starting at 2 | SQL |
| content_hash | string | yes | SHA-256 of canonical business content | SQL and vector metadata |
| ingestion_run_id | UUID string | yes | links record to an audit run | SQL |

## Accepted column aliases

Examples include:

- `Complaint ID`, `complaint_id`, `id`
- `Date Received`, `received_date`
- `Submission Channel`, `channel`
- `Company Response`, `status`
- `Consumer Complaint Narrative`, `narrative`, `complaint_text`

See `COLUMN_ALIASES` in `src/eci/cleaning.py` for the authoritative list.

## Normalization examples

| Raw value | Canonical value |
|---|---|
| ` cmp 100 ` | `CMP_100` |
| `South Carolina` | `SC` |
| `online` | `Web` |
| `E-mail` | `Email` |
| `closed with monetary relief` | `Closed with relief` |
| `$1,240.50` | decimal `1240.50` |
| `yes`, `true`, `timely`, `1` | boolean true |
| `no`, `false`, `untimely`, `0` | boolean false |

## Rejection behavior

A row is quarantined when it is a duplicate in the current file or when the canonical Pydantic record fails validation. The rejection output includes:

- Source row number
- Complaint ID when available
- One or more structured validation errors
- Redacted source record

A row is never silently repaired into compliance when the intended value is ambiguous. For example, `Carrier pigeon` is not guessed into a valid channel.
