"""Dependency health reporting used by the CLI and Streamlit sidebar."""

from __future__ import annotations

from eci.schemas import ComponentHealth
from eci.services import AppServices


def collect_health(services: AppServices) -> list[ComponentHealth]:
    db_healthy, db_detail = services.database.health_check()
    vector_healthy, vector_detail = services.vector_store.health_check()
    return [
        ComponentHealth(component="Relational database", healthy=db_healthy, detail=db_detail),
        ComponentHealth(component="Vector store", healthy=vector_healthy, detail=vector_detail),
        ComponentHealth(
            component="Embeddings",
            healthy=True,
            detail=f"Configured: {services.embeddings.model_name}",
        ),
        ComponentHealth(
            component="Answer provider",
            healthy=True,
            detail=f"Configured: {services.answers.model_name}",
        ),
    ]
