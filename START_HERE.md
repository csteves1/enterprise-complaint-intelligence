# Start Here

This project is already populated with a synthetic demonstration dataset and a tested portable database. You can inspect the files immediately, but the best learning experience is to rebuild the system yourself with the commands below.

## What you need for the first run

- Windows 10 or 11
- Python 3.11, including the `py` launcher
- VS Code
- Internet access once, so pip can install the packages

You do not need Docker, MySQL, Weaviate Cloud, an OpenAI key, or Power BI for the first run.


## What you provide at each level

| Level | What you provide | What remains local |
|---|---|---|
| Portable learning demo | Python 3.11, VS Code, and internet access for the one-time package install | SQLite database, local vector index, generated HMAC secret |
| Complete local databases | Docker Desktop | Generated MySQL passwords and Weaviate API key in `.env` |
| OpenAI embeddings and answers | An OpenAI API key entered by you directly into your local `.env` | The key is never sent to this project author, committed, or printed |
| Power BI report | Power BI Desktop and Oracle MySQL Connector/NET | The `.pbix` you build from the supplied guide, views, DAX, and exports |
| Optional Weaviate Cloud | A cluster URL and API key entered locally | The same application code, with `WEAVIATE_MODE=cloud` |

Do not send API keys or passwords through chat. The portable profile is deliberately complete enough to learn the entire workflow before adding any credential.

## Fastest Windows setup

Open PowerShell in this project folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

Then start the application:

```powershell
.\scripts\run_demo.ps1
```

The browser interface has five tabs:

1. Executive Dashboard
2. Cognitive Bot
3. Ingest Data
4. Data Quality and Operations
5. Architecture and Learn

## Manual setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt
pip install -e . --no-deps --no-build-isolation
python scripts\create_env.py --profile portable
pytest
python scripts\bootstrap_demo.py --reset
python -m streamlit run app.py
```

## What the portable mode proves

The portable profile runs the same application workflow with:

- SQLite instead of MySQL
- A local atomic JSON vector index instead of Weaviate
- A deterministic local embedding algorithm instead of OpenAI embeddings
- An extractive source-grounded answer instead of an OpenAI-generated answer

It still performs Pandas cleaning, Pydantic validation, PII masking, customer-ID pseudonymization, rejection quarantine, idempotent SQL upserts, vector search, source citations, operational auditing, Power BI exports, and tests.

## Move to the complete local enterprise stack

After the portable version makes sense, install and start Docker Desktop. Back up or remove the portable `.env`, then run:

```powershell
.\.venv\Scripts\python.exe scripts\create_env.py --profile docker --force
.\scripts\start_enterprise_stack.ps1
.\scripts\run_demo.ps1
```

This switches the system of record to MySQL and the vector index to a secured local Weaviate instance. The script generates local passwords and API keys automatically. It binds both databases only to `127.0.0.1`.

## Add OpenAI last

Never paste an API key into source code, GitHub, screenshots, or chat. Open `.env` locally and set:

```text
OPENAI_API_KEY=your_key_here
EMBEDDING_BACKEND=openai
ANSWER_BACKEND=openai
```

Then rebuild the vector index because changing the embedding model changes vector dimensions and meaning. For the Docker profile, the simplest clean rebuild is:

```powershell
docker compose down -v
.\scripts\start_enterprise_stack.ps1
```

This deletes the local Docker database volumes and reloads the synthetic dataset. Do not run that command against data you need to preserve.

## Power BI

The repository contains CSV exports, a least-privilege MySQL view layer, DAX measures, and a dashboard build guide. A native `.pbix` file is not included because it must be authored and verified with Power BI Desktop on Windows.

Begin with `powerbi/README.md` after the dashboard works in Streamlit.

## Recommended code-reading order

1. `scripts/generate_sample_data.py`
2. `src/eci/cleaning.py`
3. `src/eci/schemas.py`
4. `src/eci/security.py`
5. `src/eci/database.py`
6. `src/eci/embeddings.py`
7. `src/eci/vector_store.py`
8. `src/eci/pipeline.py`
9. `src/eci/rag.py`
10. `src/eci/answering.py`
11. `app.py`

Then use `docs/LEARNING_PATH.md` to make controlled changes and test your understanding.
