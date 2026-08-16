"""Run a small deterministic retrieval evaluation against the loaded demo index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eci.config import get_settings  # noqa: E402
from eci.services import build_services  # noqa: E402

CASES = [
    {
        "question": "What complaints describe merchant refunds that did not post?",
        "expected_issue": "Refund delay",
    },
    {
        "question": "Which customers say a mortgage payment was applied to the wrong month?",
        "expected_issue": "Payment processing",
    },
    {
        "question": "What problems involve a lien release or vehicle title arriving late?",
        "expected_issue": "Title delay",
    },
    {
        "question": "What complaints describe an account frozen after a mobile deposit?",
        "expected_issue": "Account access",
    },
    {
        "question": "What records involve a fraudulent account returning after an identity theft report?",
        "expected_issue": "Identity theft",
    },
    {
        "question": "What complaints describe unexplained escrow payment increases?",
        "expected_issue": "Escrow",
    },
    {
        "question": "What complaints say extra principal was applied as future payments?",
        "expected_issue": "Payment allocation",
    },
    {
        "question": "What complaints describe a credit report account that does not belong to the consumer?",
        "expected_issue": "Incorrect account",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation_results.json")
    args = parser.parse_args()

    services = build_services(get_settings())
    results = []
    try:
        hits = 0
        for case in CASES:
            answer = services.rag.ask(case["question"], top_k=args.top_k)
            issues = [str(source.metadata.get("issue")) for source in answer.sources]
            hit = case["expected_issue"] in issues
            hits += int(hit)
            results.append(
                {
                    **case,
                    "hit": hit,
                    "retrieved_ids": [source.complaint_id for source in answer.sources],
                    "retrieved_issues": issues,
                }
            )
        payload = {
            "top_k": args.top_k,
            "cases": len(CASES),
            "hits": hits,
            "hit_rate": hits / len(CASES),
            "embedding_model": services.embeddings.model_name,
            "results": results,
        }
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0 if hits == len(CASES) else 1
    finally:
        services.close()


if __name__ == "__main__":
    raise SystemExit(main())
