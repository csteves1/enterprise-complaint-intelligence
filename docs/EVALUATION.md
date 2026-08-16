# Retrieval and Answer Evaluation

A RAG demonstration should be evaluated with expected evidence, not judged only by whether one generated answer sounds plausible.

## Included retrieval check

Run:

```powershell
python scripts\evaluate_retrieval.py --top-k 5
```

The script contains eight questions with expected complaint themes. It records:

- Question
- Expected issue
- Whether the issue appears in the top K results
- Retrieved complaint IDs
- Retrieved issue labels
- Aggregate hit rate
- Embedding model name

The output is written to `evaluation_results.json`.

The evaluation is intentionally small and transparent. Expand it when the final dataset and domain are selected.

## Suggested retrieval metrics

- Hit rate at K: at least one expected record or theme appears in the first K results
- Recall at K: fraction of known relevant records retrieved
- Mean reciprocal rank: rewards the first relevant result appearing near the top
- Filter correctness: all returned records satisfy selected metadata filters
- Citation validity: every cited complaint ID was actually retrieved

## Suggested answer checks

For each evaluation question, manually or programmatically record:

1. Grounded: every factual statement is supported by retrieved text.
2. Cited: every material statement has a complaint ID.
3. Citation valid: no ID appears unless it was retrieved.
4. Complete: the answer covers the major recurring themes present in evidence.
5. Calibrated: it says evidence is insufficient when appropriate.
6. Safe: text inside a complaint cannot override system instructions.
7. Concise: the answer is useful without unnecessary narrative.

## Test set discipline

Do not tune prompts indefinitely against the only evaluation questions. Split a larger final set into:

- Development questions for iteration
- Held-out questions for final reporting
- Adversarial questions for prompt injection, insufficient evidence, and ambiguous requests

## Capstone reporting

Include a short table in the README or presentation:

| Layer | Test | Result |
|---|---|---|
| Validation | Deliberately invalid rows quarantined | Pass/fail and count |
| Idempotence | Same file run twice | Insert/update counts |
| Retrieval | Hit rate at 5 | Percentage |
| Filtering | Product/state/company constraints | Pass/fail |
| Citation | No un-retrieved IDs | Pass/fail |
| Privacy | Synthetic PII absent after ingestion boundary | Pass/fail |
| Recovery | Replay after vector failure | Observed behavior |

This turns the project from a feature demo into an evaluated system.
