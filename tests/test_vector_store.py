from __future__ import annotations

from eci.schemas import SearchFilters, VectorDocument
from eci.vector_store import LocalJsonVectorStore


def test_local_vector_store_upserts_searches_and_filters(tmp_path) -> None:
    store = LocalJsonVectorStore(tmp_path / "index.json")
    store.initialize()
    store.upsert(
        [
            VectorDocument(
                document_id="CMP-1",
                complaint_id="CMP-1",
                text="Refund was delayed for two billing cycles.",
                vector=[1.0, 0.0],
                metadata={"product": "Credit card", "state": "SC", "company": "Bank A"},
            ),
            VectorDocument(
                document_id="CMP-2",
                complaint_id="CMP-2",
                text="Mortgage payment was applied to the wrong month.",
                vector=[0.0, 1.0],
                metadata={"product": "Mortgage", "state": "NC", "company": "Bank B"},
            ),
        ]
    )

    result = store.search([1.0, 0.0], top_k=2)
    assert result[0].complaint_id == "CMP-1"

    filtered = store.search(
        [1.0, 0.0],
        top_k=2,
        filters=SearchFilters(product="Mortgage"),
    )
    assert [item.complaint_id for item in filtered] == ["CMP-2"]
