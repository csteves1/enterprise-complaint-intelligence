# Architecture

## Design goals

The project is designed to demonstrate five capabilities in one coherent business system:

1. Data profiling and deterministic cleaning
2. Enforced data contracts and rejected-record management
3. Relational persistence and business intelligence
4. Semantic search over unstructured text
5. Source-grounded answer generation

The business logic is separated from infrastructure through adapters. The same `PipelineRunner` and `RAGService` operate whether the selected backends are local or external.

## Components

### Configuration

`src/eci/config.py` uses Pydantic Settings. Backend selection and credentials are environment-driven. Cross-field validation prevents an OpenAI or Weaviate mode from starting without the required credentials. Production mode rejects the demonstration HMAC secret.

### Cleaning

`src/eci/cleaning.py` normalizes source columns and values but deliberately avoids deciding that an invalid row is valid. It preserves rows for formal validation.

### Validation

`src/eci/schemas.py` defines the canonical complaint record. It controls allowed enums, lengths, identifier shape, dates, states, amount range, and extra fields.

### Privacy boundary

`src/eci/security.py` masks common PII in free text and replaces raw customer IDs with stable HMAC pseudonyms before records leave the ingestion boundary.

### Relational store

`src/eci/database.py` owns SQLAlchemy models and transactions. MySQL is the intended enterprise system of record; SQLite is the portable learning profile.

### Vector store

`src/eci/vector_store.py` provides two adapters:

- Local JSON index with atomic writes and cosine similarity
- Weaviate v4 collection with self-provided vectors, deterministic UUIDs, filters, and API-key authentication

### Embeddings

`src/eci/embeddings.py` provides:

- A deterministic local signed feature-hashing model for demonstration
- An OpenAI embedding adapter with batching, timeouts, and SDK retries

The local model is useful for learning data flow. It is not represented as a semantic model suitable for production accuracy.

### Retrieval and generation

`src/eci/rag.py` sanitizes and limits the question, embeds it, searches the vector index, calls the answer provider, and optionally stores a privacy-preserving audit record.

`src/eci/answering.py` provides:

- An evidence-only extractive local answer
- An OpenAI Responses API answer that receives retrieved evidence as untrusted data and requires complaint-ID citations

### User interfaces

`app.py` combines:

- Structured dashboard
- Cognitive bot
- File ingestion
- Run audits
- Rejected-record inspection
- Architecture learning notes

Power BI connects separately to read-only MySQL views or imports generated CSV exports.

## Data ownership

MySQL is authoritative. It stores the canonical record, including the redacted complaint narrative. Weaviate stores a search-optimized copy of narrative text, metadata, and the vector. If Weaviate is lost, it can be rebuilt from MySQL or the processed validated extract.

## Identifier strategy

- `run_id`: random UUID for each ingestion attempt
- `complaint_id`: stable business key shared by SQL and vector stores
- `content_hash`: SHA-256 over canonical business content
- Weaviate object ID: UUIDv5 derived from complaint ID
- `customer_ref`: HMAC-SHA256 pseudonym truncated for display and indexing
- `source_sha256`: hash of the original source file

These identifiers support traceability, idempotence, and recovery without persisting the raw customer identifier.

## Ingestion sequence

```text
1. Resolve and validate input path
2. Enforce extension and file-size limit
3. Create schema and initialize vector store
4. Create RUNNING audit record
5. Read CSV with all fields initially treated as text
6. Enforce row-count limit
7. Profile source file
8. Normalize with Pandas
9. Reject in-file duplicates
10. Mask narrative PII and pseudonymize customer ID
11. Validate canonical record with Pydantic
12. Write valid and rejected artifacts
13. Persist rejected diagnostics
14. Transactionally upsert canonical SQL records
15. Batch-create embeddings
16. Upsert vector documents
17. Mark run SUCCEEDED or PARTIAL
18. On any unhandled failure, mark run FAILED and re-raise
```

## Consistency model

The relational and vector stores do not share a distributed transaction. SQL commits before vector indexing. This preserves the system of record and makes failed indexing recoverable.

The recovery mechanism is idempotent replay:

- SQL records with unchanged `content_hash` are skipped.
- Changed SQL records are updated.
- Vector objects use deterministic IDs and are inserted or replaced.
- An ingestion attempt is not marked complete unless vector indexing succeeds.

A larger production system might use an outbox table and worker queue. That is a reasonable capstone extension, but the current pattern is deliberately simpler and visible.

## Deployment boundaries

### Portable

All state is local to the project directory. It is for learning and single-user demonstration.

### Enterprise local

The Python process runs on the host. MySQL and Weaviate run in Docker with persistent volumes and loopback-only ports. OpenAI calls are outbound HTTPS requests from Python when enabled.

### Production direction

A production version would normally add:

- Managed MySQL with TLS and automated backups
- Managed Weaviate or a hardened cluster
- Workload identity or a secret manager
- Reverse proxy and application authentication
- Central log aggregation and metrics
- Asynchronous outbox-based indexing
- Data retention and deletion workflows
- DLP/classification appropriate to the domain
- Formal model and retrieval evaluation
- CI/CD promotion between isolated environments
