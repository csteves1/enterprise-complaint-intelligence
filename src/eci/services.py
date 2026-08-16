"""Application composition root: the one place concrete adapters are selected."""

from __future__ import annotations

from dataclasses import dataclass

from eci.answering import AnswerProvider, build_answer_provider
from eci.config import Settings, get_settings
from eci.database import Database
from eci.embeddings import EmbeddingProvider, build_embedding_provider
from eci.pipeline import PipelineRunner
from eci.rag import RAGService
from eci.vector_store import VectorStore, build_vector_store


@dataclass
class AppServices:
    settings: Settings
    database: Database
    embeddings: EmbeddingProvider
    vector_store: VectorStore
    answers: AnswerProvider
    pipeline: PipelineRunner
    rag: RAGService

    def close(self) -> None:
        self.vector_store.close()
        self.database.engine.dispose()


def build_services(settings: Settings | None = None) -> AppServices:
    resolved = settings or get_settings()
    resolved.ensure_directories()
    database = Database(resolved)
    database.create_schema()
    embeddings = build_embedding_provider(resolved)
    vector_store = build_vector_store(resolved)
    vector_store.initialize()
    answers = build_answer_provider(resolved)
    pipeline = PipelineRunner(resolved, database, embeddings, vector_store)
    rag = RAGService(resolved, database, embeddings, vector_store, answers)
    return AppServices(
        settings=resolved,
        database=database,
        embeddings=embeddings,
        vector_store=vector_store,
        answers=answers,
        pipeline=pipeline,
        rag=rag,
    )
