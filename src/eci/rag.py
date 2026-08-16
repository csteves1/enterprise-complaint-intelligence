"""Retrieval-augmented question-answering orchestration."""

from __future__ import annotations

import hashlib
import logging
import time

from eci.answering import AnswerProvider
from eci.config import Settings
from eci.database import Database
from eci.embeddings import EmbeddingProvider
from eci.schemas import AnswerResult, SearchFilters
from eci.security import sanitize_query
from eci.vector_store import VectorStore

LOGGER = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        answers: AnswerProvider,
    ) -> None:
        self.settings = settings
        self.database = database
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.answers = answers

    def ask(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: SearchFilters | None = None,
    ) -> AnswerResult:
        cleaned_query = sanitize_query(query, self.settings.max_query_characters)
        requested_top_k = top_k or self.settings.default_top_k
        requested_top_k = max(1, min(requested_top_k, self.settings.max_top_k))
        query_hash = hashlib.sha256(cleaned_query.encode("utf-8")).hexdigest()
        started = time.perf_counter()
        sources = []
        try:
            query_vector = self.embeddings.embed_query(cleaned_query)
            sources = self.vector_store.search(
                query_vector, top_k=requested_top_k, filters=filters
            )
            answer = self.answers.answer(cleaned_query, sources)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self.database.record_query_audit(
                query_hash=query_hash,
                vector_backend=self.settings.vector_backend,
                answer_backend=self.settings.answer_backend,
                model_name=self.answers.model_name,
                retrieved_ids=[source.complaint_id for source in sources],
                duration_ms=elapsed_ms,
                succeeded=True,
                error_class=None,
            )
            return AnswerResult(
                answer=answer,
                sources=sources,
                model_name=self.answers.model_name,
                retrieval_count=len(sources),
                query=cleaned_query,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self.database.record_query_audit(
                query_hash=query_hash,
                vector_backend=self.settings.vector_backend,
                answer_backend=self.settings.answer_backend,
                model_name=self.answers.model_name,
                retrieved_ids=[source.complaint_id for source in sources],
                duration_ms=elapsed_ms,
                succeeded=False,
                error_class=type(exc).__name__,
            )
            LOGGER.exception("RAG request failed")
            raise
