# Enterprise Complaint Intelligence Platform

An end-to-end capstone system that cleans and validates mixed-format complaint data, preserves an authoritative relational record, creates a semantic search index, and exposes both structured analytics and source-grounded question answering.

## Business story

Traditional business intelligence is good at counting complaints, response times, amounts, products, states, and companies. It is much weaker at helping an analyst investigate thousands of narrative descriptions. This project serves both needs:

- The relational path supports executive and operational reporting.
- The vector path supports semantic retrieval over unstructured narratives.
- The RAG layer answers questions only from retrieved evidence and cites complaint IDs.

The one-sentence interview description is:

> A Python enterprise data pipeline uses Pandas and Pydantic to clean and validate mixed-format complaint records, stores the authoritative records in MySQL for Power BI, indexes PII-redacted narratives in Weaviate, and provides source-grounded retrieval and question answering through Streamlit and OpenAI.

## Architecture

```text
Raw CSV
   |
   v
File size and row-count controls
   |
   v
Pandas profiling and normalization
   |
   v
Pydantic data contract
   |---------------- invalid ----------------> redacted quarantine + audit
   |
   v
Validated and PII-redacted records
   |                                      |
   v                                      v
SQL system of record                 Embedding provider
SQLite or MySQL                           |
   |                                      v
   |                               Vector store
   |                               Local or Weaviate
   |                                      |
   v                                      v
Streamlit dashboard / Power BI       Evidence retrieval
                                          |
                                          v
                                  Grounded answer provider
                                  Local or OpenAI Responses API
                                          |
                                          v
                                  Answer plus source IDs
```

A stable `complaint_id` connects the SQL record and vector record. MySQL is the source of truth; Weaviate is a rebuildable semantic index.

## Two runnable profiles

| Profile | Relational store | Vector store | Embeddings | Answer generation | Secrets required |
|---|---|---|---|---|---|
| Portable | SQLite | Atomic local JSON index | Local signed feature hashing | Local extractive answer | None |
| Enterprise local | MySQL 8.4 | Secured Weaviate 1.38 | Local or OpenAI | Local or OpenAI | Generated locally; OpenAI key optional |

The portable profile is not a fake UI. It executes the complete application flow and is designed so a student can inspect every artifact without first solving infrastructure and billing.

## Implemented controls

### Data quality

- Required-column contract before transformation
- Deterministic column aliases and value normalization
- Strict Pydantic types, lengths, ranges, enums, date bounds, and extra-field rejection
- In-file duplicate detection
- Stable content hashes for change detection
- Invalid-record quarantine with field-level reasons
- Source file SHA-256 and ingestion run IDs
- Idempotent SQL and vector upserts

### Privacy and application security

- Email, phone, SSN, and payment-card pattern masking before persistence and embedding
- HMAC pseudonymization of customer identifiers
- Secrets represented with `SecretStr`
- Secrets loaded from `.env`, never required in source code
- Log redaction for keys, passwords, bearer tokens, and common secret patterns
- CSV formula-injection protection for exported diagnostics
- Query control-character removal and maximum lengths
- Upload file-size and row-count limits
- In-process rate limiting for the single-user Streamlit demonstration
- Retrieved text treated as untrusted evidence, not executable instructions
- No raw user question stored by default; optional audit stores only its SHA-256 hash
- MySQL Power BI account receives `SELECT` only
- Local database ports bind to loopback rather than all network interfaces
- Weaviate anonymous access disabled and API-key authentication plus RBAC enabled

### Reliability and operations

- SQL transactions with rollback
- Connection pre-ping and pool recycling
- Rotating JSON logs
- Database and vector health checks
- Audit tables for ingestion, rejection, and optional queries
- Atomic local vector-file replacement
- Retry and timeout configuration for OpenAI
- Restart-safe cross-store recovery through deterministic identifiers and idempotent writes
- Automated tests and CI quality gates

See `docs/SECURITY.md` for the threat model and limitations. This is enterprise-style engineering, not a claim of HIPAA, PCI DSS, SOC 2, FedRAMP, or production certification.

## Quick start

Read `START_HERE.md`. On Windows, the normal first run is:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
.\scripts\run_demo.ps1
```

The setup script creates `.venv`, installs dependencies, creates a local `.env`, runs tests, rebuilds the demonstration database, creates vector records, and exports Power BI-ready CSVs.

## Common commands

After activating `.venv`, make sure the project itself has been installed once with `pip install -e . --no-deps --no-build-isolation`. The automated setup script does this for you.

```powershell
# Rebuild the portable demonstration
python scripts\bootstrap_demo.py --reset

# Ingest a CSV
python -m eci.cli ingest data\raw\complaints_raw.csv

# Ask a question
python -m eci.cli ask "What complaints describe a lien release or vehicle title arriving late?" --top-k 5

# Run health checks
python -m eci.cli health

# Export Power BI files
python -m eci.cli export-powerbi --output powerbi\exports

# Run tests
pytest

# Start Streamlit
python -m streamlit run app.py
```

## Complete MySQL and Weaviate profile

1. Install Docker Desktop.
2. Generate a secure Docker profile:

```powershell
python scripts\create_env.py --profile docker --force
```

3. Start and load the services:

```powershell
.\scripts\start_enterprise_stack.ps1
```

4. Start Streamlit:

```powershell
.\scripts\run_demo.ps1
```

The Docker profile uses:

- MySQL application user for read/write pipeline operations
- Separate read-only Power BI user
- Secured Weaviate root user for this local development instance
- Persistent Docker volumes
- Loopback-only port publication

For a true production deployment, use a managed database, TLS, a secret manager, network controls, centralized identity, monitoring, backups, vulnerability management, and narrower Weaviate application roles.

## OpenAI profile

Edit `.env` locally:

```text
OPENAI_API_KEY=your_key_here
EMBEDDING_BACKEND=openai
ANSWER_BACKEND=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-5.6-luna
```

The Python application owns both embedding and response-generation calls. Weaviate is configured for self-provided vectors, so the OpenAI key is not stored in Weaviate.

Changing the embedding provider or model requires rebuilding the vector index. Never mix document vectors from one model with query vectors from another.

### Optional Weaviate Cloud profile

The same adapter supports Weaviate Cloud. Replace only these local settings in `.env`:

```text
VECTOR_BACKEND=weaviate
WEAVIATE_MODE=cloud
WEAVIATE_URL=your_cloud_rest_endpoint
WEAVIATE_API_KEY=your_cloud_api_key
```

Keep `OPENAI_API_KEY` separate. The application sends self-provided vectors to Weaviate, so the Weaviate service does not need the OpenAI credential. Do not paste either key into chat or commit `.env`.

## Input contract

The first release accepts CSV files containing these logical fields. Friendly aliases such as `Complaint ID` and `Consumer Complaint Narrative` are normalized automatically.

Required:

- complaint_id
- date_received
- customer_id
- product
- issue
- company
- channel
- timely_response
- status
- complaint_text

Optional:

- sub_product
- state
- amount_disputed

See `docs/DATA_DICTIONARY.md` for exact validation rules.

## Repository map

```text
app.py                          Streamlit UI
src/eci/config.py               Typed settings and backend selection
src/eci/cleaning.py             Pandas normalization
src/eci/schemas.py              Pydantic data contracts
src/eci/security.py             PII, pseudonyms, limits, hashing
src/eci/database.py             SQLAlchemy models and transactions
src/eci/embeddings.py           Local and OpenAI embeddings
src/eci/vector_store.py         Local and Weaviate vector adapters
src/eci/pipeline.py             End-to-end ingestion orchestrator
src/eci/rag.py                  Retrieval orchestration and audit
src/eci/answering.py            Local and OpenAI grounded answers
src/eci/exporting.py            Power BI extracts
scripts/                        Setup, data generation, and operations
sql/mysql_views.sql             Least-data Power BI view layer
powerbi/                        Dashboard build guide and DAX
tests/                          Automated behavior checks
docs/                           Architecture, security, operations, learning
```

## Cross-store failure behavior

MySQL and Weaviate cannot participate in one ordinary ACID transaction. The pipeline therefore uses a recoverable pattern:

1. Validate everything first.
2. Commit authoritative SQL records transactionally.
3. Upsert vector documents with deterministic IDs.
4. Mark the ingestion run complete only after both stages finish.
5. On failure, retain a failed audit record.
6. Rerun safely. Unchanged SQL records are skipped and vector records are replaced by deterministic ID.

This is intentionally visible in the design because discussing distributed consistency is stronger than pretending two databases can share one transaction.

## Demonstration dataset

`scripts/generate_sample_data.py` creates synthetic financial complaints with recurring themes and seven deliberate defects:

- Missing complaint ID
- Future date
- Negative disputed amount
- Unsupported channel
- Narrative below minimum length
- Invalid state value
- Duplicate complaint ID

It also includes synthetic email, phone, SSN, and payment-card patterns so the masking behavior can be verified without using real personal data.

## Power BI

Start with `powerbi/README.md`. The repository contains:

- Ready-to-import CSV extracts
- MySQL views that exclude customer pseudonyms and narrative text
- DAX measures
- Date-table instructions
- Visual and interaction plan
- Read-only database account setup

A native `.pbix` is intentionally not fabricated outside Power BI Desktop. Building that final report yourself is also an important PL-300 learning exercise.

## Tests

The automated tests verify cleaning, validation, PII masking, pseudonym stability, safe querying, idempotent ingestion, SQL persistence, vector retrieval, source citations, and rejection behavior.

The included portable release was exercised end to end before packaging. See `DEMO_RESULTS.md` for the exact run summary.

## Learning plan

Do not read every file passively. Run one controlled experiment at a time:

1. Change a raw date format and rerun.
2. Add a Pydantic business rule and test its rejection.
3. Correct a rejected row and watch it enter both stores.
4. Run the same input twice and inspect idempotence.
5. Change a narrative and observe an update.
6. Filter retrieval by state or product.
7. Switch SQLite to MySQL.
8. Switch local vectors to Weaviate.
9. Switch local embeddings to OpenAI.
10. Build the Power BI report from the same source-of-truth data.

Detailed exercises are in `docs/LEARNING_PATH.md`.
