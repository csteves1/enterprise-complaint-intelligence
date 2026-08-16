"""Create and execute the completely offline, no-secret demonstration profile."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from generate_sample_data import generate  # noqa: E402
from eci.config import Settings  # noqa: E402
from eci.exporting import export_powerbi_files  # noqa: E402
from eci.logging_config import configure_logging  # noqa: E402
from eci.services import build_services  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete prior demo database and vector index")
    args = parser.parse_args()

    database_path = ROOT / "data" / "eci_demo.db"
    vector_path = ROOT / "data" / "vector" / "local_index.json"
    if args.reset:
        database_path.unlink(missing_ok=True)
        vector_path.unlink(missing_ok=True)
        shutil.rmtree(ROOT / "powerbi" / "exports", ignore_errors=True)
        for directory in (ROOT / "data" / "processed", ROOT / "data" / "rejected"):
            directory.mkdir(parents=True, exist_ok=True)
            for artifact in directory.glob("complaints_raw_*"):
                artifact.unlink(missing_ok=True)
        (ROOT / "logs" / "application.log").unlink(missing_ok=True)

    source = generate(ROOT / "data" / "raw" / "complaints_raw.csv")
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url=f"sqlite:///{database_path.as_posix()}",
        vector_backend="local",
        vector_index_path=vector_path,
        embedding_backend="local",
        answer_backend="local",
        log_dir=ROOT / "logs",
        raw_data_dir=ROOT / "data" / "raw",
        processed_data_dir=ROOT / "data" / "processed",
        rejected_data_dir=ROOT / "data" / "rejected",
    )
    configure_logging(settings.log_level, settings.log_dir)
    services = build_services(settings)
    try:
        summary = services.pipeline.run(source)
        exports = export_powerbi_files(services.database, ROOT / "powerbi" / "exports")
        answer = services.rag.ask(
            "What complaints describe a lien release or vehicle title arriving late?",
            top_k=5,
        )
        print("\nDEMO PIPELINE COMPLETE")
        print(summary.model_dump_json(indent=2))
        print("\nSAMPLE COGNITIVE-BOT ANSWER\n")
        print(answer.answer)
        print("\nPower BI-ready exports:")
        for path in exports:
            print(f"- {path}")
        print("\nLaunch the interface after installing requirements:")
        print("  streamlit run app.py")
        return 0
    finally:
        services.close()


if __name__ == "__main__":
    raise SystemExit(main())
