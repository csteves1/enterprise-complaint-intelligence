"""Apply Power BI views after SQLAlchemy has created the application tables."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eci.config import get_settings  # noqa: E402
from eci.database import Database  # noqa: E402


def statements(sql: str) -> list[str]:
    cleaned_lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return [part.strip() for part in "\n".join(cleaned_lines).split(";") if part.strip()]


def main() -> int:
    settings = get_settings()
    if settings.database_dialect != "mysql":
        raise SystemExit("Power BI SQL views are intended for the MySQL profile.")
    database = Database(settings)
    database.create_schema()
    sql = (ROOT / "sql" / "mysql_views.sql").read_text(encoding="utf-8")
    with database.engine.begin() as connection:
        for statement in statements(sql):
            connection.execute(text(statement))
    database.engine.dispose()
    print("Power BI views created or refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
