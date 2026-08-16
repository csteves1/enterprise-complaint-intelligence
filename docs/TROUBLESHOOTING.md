# Troubleshooting

## PowerShell blocks the setup script

Use a process-only policy change:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Then run the script again. This does not permanently change the machine policy.

## `py -3.11` is not found

Install Python 3.11 or 3.12 from a trusted distribution and include the Python launcher. Reopen PowerShell after installation.

## The wrong Python interpreter is active in VS Code

Use Command Palette -> `Python: Select Interpreter` -> choose `.venv\Scripts\python.exe`.

## `ModuleNotFoundError`

Activate the virtual environment or invoke its Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Streamlit says no records are loaded

Run:

```powershell
python scripts\bootstrap_demo.py --reset
```

Then refresh the browser.

## A CSV is rejected before row validation

The file is probably missing one or more required logical columns. Compare it with `docs/DATA_DICTIONARY.md` and the included synthetic CSV.

## Too many records are rejected

Open the newest file in `data/rejected`. The `validation_errors` column contains structured field-level reasons. Fix the source or update a documented business rule; do not disable validation merely to increase acceptance.

## Docker port conflict

Another process may already use 3306, 8080, or 50051. Stop the conflicting service or change both the Compose port mapping and the corresponding `.env` URL.

## Docker services do not become healthy

```powershell
docker compose ps
docker compose logs mysql
docker compose logs weaviate
```

Do not paste logs publicly until checking them for sensitive configuration.

## Power BI cannot connect to MySQL

Confirm:

- MySQL is healthy.
- Oracle MySQL Connector/NET is installed on Windows.
- Server is `127.0.0.1:3306`.
- Database is `eci`.
- Credentials are `POWERBI_USER` and `POWERBI_PASSWORD` from your local `.env`.
- `scripts/apply_mysql_views.py` has run.

Use the read-only Power BI account, not root or the application account.

## The bot retrieves irrelevant records in portable mode

The portable embedding is deliberately dependency-free and lexical. Use specific business terms, filters, or enable OpenAI embeddings for semantic quality. The local mode demonstrates the mechanics, audit trail, and source grounding; it is not presented as a production retrieval model.

## The bot answer is extractive

Set `ANSWER_BACKEND=openai` and add a valid local OpenAI key. Retrieval and answer generation are intentionally independent, so you can test each layer separately.
