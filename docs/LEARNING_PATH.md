# Learning Path

The project is meant to be changed. Use Git so each experiment can be undone.

## Exercise 1: Trace one record

Choose `CMP-1003` in `data/raw/complaints_raw.csv`.

1. Find it in the raw CSV.
2. Find it in the processed valid CSV.
3. Query it in SQLite or MySQL.
4. Find its object in `data/vector/local_index.json` or Weaviate.
5. Ask a question that retrieves it.
6. Explain which fields exist in each store and why.

Goal: understand lineage and the shared complaint ID.

## Exercise 2: Add a validation rule

Add a rule that `amount_disputed` cannot exceed a limit you choose for one product.

1. Add a failing test first.
2. Add the Pydantic validator.
3. Create one invalid sample row.
4. Run ingestion.
5. Inspect the rejected CSV and audit table.

Goal: understand why cleaning and validation are separate.

## Exercise 3: Repair a rejected row

Correct `CMP-BADCHANNEL` in a copied CSV.

1. Rerun ingestion.
2. Confirm it is now in SQL.
3. Confirm it is in the vector index.
4. Confirm the new run has one fewer rejection.

Goal: understand quarantine and replay.

## Exercise 4: Prove idempotence

Run the same input twice.

- First run should insert records.
- Second run should insert zero and update zero unchanged records.
- Change one narrative and run again.
- The SQL update count should become one and the vector object should be replaced, not duplicated.

Goal: understand content hashes and deterministic vector IDs.

## Exercise 5: Inspect PII controls

Search for the synthetic email and SSN in the raw CSV. Then confirm they do not appear in:

- SQL complaint text
- Processed valid CSV
- Vector index
- Streamlit retrieved evidence

Goal: understand where the privacy boundary sits.

## Exercise 6: Query filtering

Ask the same question with no filter and then with:

- Product filter
- State filter
- Company filter

Read `SearchFilters` and both vector-store implementations.

Goal: understand how semantic search and structured metadata work together.

## Exercise 7: Switch relational stores

Compare the portable SQLite profile with the Docker MySQL profile.

1. Inspect `DATABASE_URL`.
2. Run `eci health` in each profile.
3. Compare the tables.
4. Connect MySQL Workbench.
5. Explain why the application code did not need to change.

Goal: understand repository and adapter patterns.

## Exercise 8: Switch vector stores

Compare local JSON and Weaviate.

1. Inspect object properties and vector dimensions.
2. Search with the same question.
3. Stop Weaviate and observe the health check and safe error.
4. Restart and rerun ingestion.

Goal: understand vector infrastructure and recovery.

## Exercise 9: Add OpenAI embeddings

1. Place the key only in `.env`.
2. Set `EMBEDDING_BACKEND=openai`.
3. Delete and rebuild the existing vector index.
4. Compare retrieval results against the local hashing model.
5. Create a small evaluation table of questions and expected themes.

Goal: understand that embedding quality is measurable, not magic.

## Exercise 10: Add generated answers

Set `ANSWER_BACKEND=openai` after retrieval is working.

Evaluate:

- Does every material claim cite a source ID?
- Does the answer decline when evidence is weak?
- Can you reproduce the claim in the retrieved text?
- Does a narrative containing an instruction alter the bot's policy?

Goal: understand grounding and prompt-injection risk.

## Exercise 11: Build Power BI

Use the CSV exports first, then connect to the MySQL views.

Build:

- KPI row
- Monthly trend
- Product breakdown
- Company breakdown
- State map or bar chart
- Issue drill-through page
- Data-quality page using ingestion runs and rejections

Goal: connect engineering output to business decision support.

## Exercise 12: Present the project

Prepare a five-minute demo:

1. Business problem
2. Architecture
3. Deliberately bad input row
4. Successful pipeline run
5. Power BI insight
6. RAG question with source evidence
7. Security and recovery decision
8. One limitation and next improvement

Goal: show judgment, not just a list of tools.
