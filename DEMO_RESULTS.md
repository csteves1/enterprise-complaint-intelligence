# Demonstration Verification Results

This file records what was actually exercised before the project archive was packaged. It separates verified behavior from adapters that require software or credentials unavailable in the build container.

## Release verification

- Verification date: July 27, 2026 (America/New_York)
- Validation host: Linux container
- Validation interpreter: Python 3.13.5
- Project target: Python 3.11 or later
- Final portable ingestion run ID: `be52f17f-2ac8-459c-b8b6-8fade51fc65e`

## Automated checks

| Check | Result |
|---|---:|
| Pytest behavior tests | 14 passed |
| Python bytecode compilation | Passed |
| Docker Compose YAML parse | Passed |
| GitHub Actions YAML parse | Passed |
| Portable database health | Passed |
| Portable vector-index health | Passed |
| Embedding-provider configuration health | Passed |
| Answer-provider configuration health | Passed |

The tests cover cleaning, required-column enforcement, Pydantic validation, configuration safety, PII masking, HMAC pseudonymization, query normalization, CSV formula-injection protection, end-to-end ingestion, rejection quarantine, SQL persistence, idempotent replay, failed-run auditing, local vector search, metadata filters, and source-grounded output.

## Final end-to-end portable run

| Metric | Result |
|---|---:|
| Source rows read | 87 |
| Valid records | 80 |
| Quarantined records | 7 |
| SQL records inserted | 80 |
| SQL records updated | 0 |
| Vector records upserted | 80 |
| Final run status | `PARTIAL` |

`PARTIAL` is the intended result because the synthetic source intentionally contains seven defective records while the valid records continue through both destinations.

The seven rejection scenarios were:

1. Missing complaint ID
2. Future received date
3. Negative disputed amount
4. Unsupported submission channel
5. Narrative below the minimum length
6. Invalid state value
7. Duplicate complaint ID within the source file

The run produced:

- A SQLite system-of-record database
- An atomic local JSON vector index
- A valid-record CSV
- A redacted rejected-record CSV
- A source-profile JSON file
- Five Power BI-ready CSV exports
- A successful source-grounded cognitive-bot response with complaint IDs

## Retrieval evaluation

The dependency-free local embedding model was evaluated with eight prepared business questions. The expected issue appeared within the top five retrieved records in all eight cases:

- Cases: 8
- Hits at 5: 8
- Hit rate at 5: 100%

The detailed results are saved in `evaluation_results.json`.

This is a small deterministic functional evaluation, not a claim that signed feature hashing equals a production semantic embedding model. OpenAI embeddings are the intended higher-quality option after the complete data flow is understood.

## Privacy regression scan

The synthetic raw source deliberately contains the following identifiers so masking behavior can be tested:

- `customer@example.com`
- `843-555-0142`
- `123-45-6789`
- `4111 1111 1111 1111`
- Rejected-row customer identifier `CUST-BAD-1`

A post-run scan found zero occurrences of those values in:

- Valid processed output
- Rejected output
- Local vector index
- SQLite complaint and rejected-record fields
- Power BI exports

The raw synthetic CSV still contains those deliberate test values by design. Do not replace it with real sensitive data.

## Secret hygiene

- No real `.env` file is included.
- No OpenAI key is included.
- No Weaviate key is included.
- No MySQL password is included.
- `.env.example` and `.env.docker.example` contain placeholders only.
- `scripts/create_env.py` generates local secrets without printing their values.

## Runtime boundaries not exercised in the build container

The portable pipeline was executed end to end. The following adapters were prepared but could not be live-tested in this container:

- **Streamlit UI:** `app.py` compiled successfully, but Streamlit was not installed in the validation container. The pinned dependency and automated Windows installer are included.
- **MySQL and Weaviate Docker profile:** Docker was unavailable. The Compose file parsed successfully, ports are loopback-bound, anonymous Weaviate access is disabled, and local credentials are generated securely.
- **OpenAI adapters:** No API key was provided or requested. Embedding and Responses API adapters compiled, but no paid API call was made.
- **Power BI Desktop:** A native `.pbix` was not authored because Power BI Desktop is a Windows-only proprietary application. Read-only MySQL views, CSV exports, DAX measures, theme, and a complete report-building guide are included.
- **Python 3.11 runtime:** The release was run under Python 3.13.5. The project targets Python 3.11+, the Windows setup explicitly creates a Python 3.11 environment, and the included CI workflow is configured for Python 3.11.
- **Ruff and Bandit locally:** Their quality gates are configured in CI, but the build container could not download them because package-index network access was unavailable.

These boundaries are intentionally explicit so the project does not overstate what was verified.

## Reproduce the verified run

On Windows, from the project directory:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
.\scripts\run_demo.ps1
```

To rerun only the automated checks and portable pipeline after setup:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\bootstrap_demo.py --reset
.\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --top-k 5
.\.venv\Scripts\python.exe -m eci.cli health
```
