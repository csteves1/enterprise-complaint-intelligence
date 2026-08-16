"""Command-line interface for ingestion, health checks, search, and exports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eci.config import get_settings
from eci.exporting import export_powerbi_files
from eci.health import collect_health
from eci.logging_config import configure_logging
from eci.schemas import SearchFilters
from eci.services import build_services


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eci",
        description="Enterprise Complaint Intelligence Platform",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Run the end-to-end CSV pipeline")
    ingest.add_argument("file", type=Path)

    ask = subparsers.add_parser("ask", help="Ask the indexed complaint narratives a question")
    ask.add_argument("question")
    ask.add_argument("--top-k", type=int, default=None)
    ask.add_argument("--product", default=None)
    ask.add_argument("--state", default=None)
    ask.add_argument("--company", default=None)

    subparsers.add_parser("health", help="Check database and vector dependencies")

    export = subparsers.add_parser("export-powerbi", help="Write Power BI-ready CSV files")
    export.add_argument("--output", type=Path, default=Path("powerbi/exports"))

    subparsers.add_parser("init-db", help="Create database tables")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_dir)
    services = build_services(settings)
    try:
        if args.command == "ingest":
            summary = services.pipeline.run(args.file)
            print(json.dumps(summary.model_dump(mode="json"), indent=2))
        elif args.command == "ask":
            filters = SearchFilters(
                product=args.product,
                state=args.state.upper() if args.state else None,
                company=args.company,
            )
            result = services.rag.ask(args.question, top_k=args.top_k, filters=filters)
            print(result.answer)
            print("\nSources:")
            for source in result.sources:
                print(
                    f"- {source.complaint_id} | score={source.score:.3f} | "
                    f"{source.metadata.get('product')} | {source.metadata.get('company')}"
                )
        elif args.command == "health":
            statuses = collect_health(services)
            for status in statuses:
                marker = "OK" if status.healthy else "FAIL"
                print(f"[{marker}] {status.component}: {status.detail}")
            return 0 if all(status.healthy for status in statuses) else 1
        elif args.command == "export-powerbi":
            paths = export_powerbi_files(services.database, args.output)
            for path in paths:
                print(path.resolve())
        elif args.command == "init-db":
            services.database.create_schema()
            print("Database schema is ready.")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        services.close()


if __name__ == "__main__":
    raise SystemExit(main())
