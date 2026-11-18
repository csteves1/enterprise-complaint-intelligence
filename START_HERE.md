# Start Here

This repository comes pre-configured with a synthetic demonstration dataset and a runnable portable database.

## Prerequisites (First Run)
- Windows 10 or 11
- Python 3.11 (including the `py` launcher)
- Internet access once to install Python packages

Docker, MySQL, Weaviate Cloud, an OpenAI API key, and Power BI are not required for the initial local run.

## Configuration Profiles

| Profile | What You Provide | What Remains Local |
| :--- | :--- | :--- |
| **Portable local demo** | Python 3.11 and one-time internet access for package install | SQLite database, local vector index, generated HMAC secret |
| **Complete local databases** | Docker Desktop | Generated MySQL passwords and Weaviate API key in `.env` |
| **OpenAI embeddings & answers** | OpenAI API key entered in your local `.env` | Stored locally in `.env` (gitignored); never committed or logged |
| **Power BI report** | Power BI Desktop and Oracle MySQL Connector/NET | Local `.pbix` report connected to the repo's views, DAX, and exports |
| **Optional Weaviate Cloud** | Cluster URL and API key in `.env` | Same application code with `WEAVIATE_MODE=cloud` |

The portable profile executes the full end-to-end pipeline locally with zero external credentials required.

## Fastest Windows Setup
Open PowerShell in the project root and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
