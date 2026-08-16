"""Create a secure local .env file without exposing secrets in chat or source control."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]


def token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def docker_profile() -> str:
    root_password = token(30)
    app_password = token(30)
    powerbi_password = token(30)
    weaviate_key = token(36)
    hmac_secret = token(48)
    encoded_app_password = quote_plus(app_password)
    return f"""COMPOSE_PROJECT_NAME=eci_capstone
ENVIRONMENT=development
LOG_LEVEL=INFO

MYSQL_ROOT_PASSWORD={root_password}
MYSQL_DATABASE=eci
MYSQL_APP_USER=eci_app
MYSQL_APP_PASSWORD={app_password}
POWERBI_USER=eci_powerbi
POWERBI_PASSWORD={powerbi_password}
DATABASE_URL=mysql+pymysql://eci_app:{encoded_app_password}@127.0.0.1:3306/eci?charset=utf8mb4

VECTOR_BACKEND=weaviate
WEAVIATE_MODE=local
WEAVIATE_URL=http://127.0.0.1:8080
WEAVIATE_USER=eci-root
WEAVIATE_API_KEY={weaviate_key}
WEAVIATE_COLLECTION=ComplaintNarrative

EMBEDDING_BACKEND=local
ANSWER_BACKEND=local
LOCAL_EMBEDDING_DIMENSIONS=1024
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-5.6-luna
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=3

HMAC_SECRET={hmac_secret}
PII_REDACTION_ENABLED=true
STORE_REJECTED_ROWS_IN_DATABASE=true
AUDIT_USER_QUERIES=false
MAX_INPUT_FILE_MB=25
MAX_INPUT_ROWS=100000
MAX_QUERY_CHARACTERS=500
DEFAULT_TOP_K=5
MAX_TOP_K=10
MAX_CONTEXT_CHARACTERS=24000
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60
"""


def portable_profile() -> str:
    return f"""ENVIRONMENT=development
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///data/eci_demo.db
VECTOR_BACKEND=local
VECTOR_INDEX_PATH=data/vector/local_index.json
EMBEDDING_BACKEND=local
ANSWER_BACKEND=local
LOCAL_EMBEDDING_DIMENSIONS=1024
HMAC_SECRET={token(48)}
PII_REDACTION_ENABLED=true
STORE_REJECTED_ROWS_IN_DATABASE=true
AUDIT_USER_QUERIES=false
MAX_INPUT_FILE_MB=25
MAX_INPUT_ROWS=100000
MAX_QUERY_CHARACTERS=500
DEFAULT_TOP_K=5
MAX_TOP_K=10
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("portable", "docker"), default="portable")
    parser.add_argument("--force", action="store_true", help="Replace an existing .env file")
    args = parser.parse_args()

    target = ROOT / ".env"
    if target.exists() and not args.force:
        raise SystemExit(".env already exists. Use --force only when you intend to replace it.")
    content = docker_profile() if args.profile == "docker" else portable_profile()
    target.write_text(content, encoding="utf-8")
    print(f"Created {target}")
    print("Secrets were written locally. Do not commit or paste this file into chat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
