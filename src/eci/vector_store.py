"""Vector-store adapters: a portable JSON index and Weaviate v4."""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from eci.config import Settings
from eci.exceptions import VectorStoreError
from eci.schemas import SearchFilters, SearchResult, VectorDocument

LOGGER = logging.getLogger(__name__)


class VectorStore(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, documents: Sequence[VectorDocument]) -> int:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> tuple[bool, str]:
        raise NotImplementedError

    def close(self) -> None:
        return None


class LocalJsonVectorStore(VectorStore):
    """Atomic JSON-backed cosine index for the zero-service demo."""

    FORMAT_VERSION = 1

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write({"version": self.FORMAT_VERSION, "documents": {}})

    def _read(self) -> dict[str, Any]:
        self.initialize()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("version") != self.FORMAT_VERSION:
                raise VectorStoreError("Local vector index format is not supported.")
            return payload
        except (OSError, json.JSONDecodeError) as exc:
            raise VectorStoreError("The local vector index could not be read.") from exc

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise VectorStoreError("The local vector index could not be written.") from exc

    def upsert(self, documents: Sequence[VectorDocument]) -> int:
        if not documents:
            return 0
        with self._lock:
            payload = self._read()
            stored: dict[str, Any] = payload["documents"]
            expected_dimension: int | None = None
            if stored:
                first = next(iter(stored.values()))
                expected_dimension = len(first["vector"])
            for document in documents:
                if expected_dimension is None:
                    expected_dimension = len(document.vector)
                if len(document.vector) != expected_dimension:
                    raise VectorStoreError(
                        "Embedding dimensions changed. Rebuild the vector index before switching models."
                    )
                stored[document.document_id] = document.model_dump(mode="json")
            self._atomic_write(payload)
        return len(documents)

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return -1.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (left_norm * right_norm)))

    @staticmethod
    def _matches(metadata: dict[str, Any], filters: SearchFilters | None) -> bool:
        if filters is None:
            return True
        for key in ("product", "state", "company"):
            expected = getattr(filters, key)
            if expected and str(metadata.get(key, "")).casefold() != expected.casefold():
                return False
        return True

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        with self._lock:
            documents = self._read()["documents"].values()
            ranked: list[SearchResult] = []
            for document in documents:
                if not self._matches(document["metadata"], filters):
                    continue
                score = self._cosine(query_vector, document["vector"])
                ranked.append(
                    SearchResult(
                        complaint_id=document["complaint_id"],
                        text=document["text"],
                        score=score,
                        distance=max(0.0, 1.0 - score),
                        metadata=document["metadata"],
                    )
                )
            ranked.sort(key=lambda item: item.score, reverse=True)
            return ranked[:top_k]

    def health_check(self) -> tuple[bool, str]:
        try:
            count = len(self._read()["documents"])
            return True, f"Local index ready ({count} documents)"
        except VectorStoreError:
            LOGGER.exception("Local vector health check failed")
            return False, "Local vector index is unavailable"


class WeaviateVectorStore(VectorStore):
    """Weaviate v4 adapter using self-provided vectors and secure API keys."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Any | None = None

    def _connect(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            import weaviate
            from weaviate.classes.init import AdditionalConfig, Auth, Timeout
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise VectorStoreError(
                "The weaviate-client package is not installed. Run pip install -r requirements.txt."
            ) from exc

        api_key = self.settings.weaviate_api_key.get_secret_value()  # type: ignore[union-attr]
        timeout = AdditionalConfig(
            timeout=Timeout(
                init=self.settings.openai_timeout_seconds,
                query=self.settings.openai_timeout_seconds,
                insert=max(60.0, self.settings.openai_timeout_seconds),
            )
        )
        try:
            if self.settings.weaviate_mode == "cloud":
                self.client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=self.settings.weaviate_url,
                    auth_credentials=Auth.api_key(api_key),
                    additional_config=timeout,
                )
            else:
                parsed = urlparse(self.settings.weaviate_url)
                host = parsed.hostname or "localhost"
                http_secure = parsed.scheme == "https"
                http_port = parsed.port or (443 if http_secure else 8080)
                self.client = weaviate.connect_to_custom(
                    http_host=host,
                    http_port=http_port,
                    http_secure=http_secure,
                    grpc_host=host,
                    grpc_port=50051,
                    grpc_secure=http_secure,
                    auth_credentials=Auth.api_key(api_key),
                    additional_config=timeout,
                )
            return self.client
        except Exception as exc:
            raise VectorStoreError("Could not connect to Weaviate.") from exc

    def initialize(self) -> None:
        client = self._connect()
        try:
            if client.collections.exists(self.settings.weaviate_collection):
                return
            from weaviate.classes.config import Configure, DataType, Property

            client.collections.create(
                name=self.settings.weaviate_collection,
                vector_config=Configure.Vectors.self_provided(),
                properties=[
                    Property(name="complaintId", data_type=DataType.TEXT),
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="product", data_type=DataType.TEXT),
                    Property(name="company", data_type=DataType.TEXT),
                    Property(name="state", data_type=DataType.TEXT),
                    Property(name="issue", data_type=DataType.TEXT),
                    Property(name="dateReceived", data_type=DataType.TEXT),
                    Property(name="contentHash", data_type=DataType.TEXT),
                ],
            )
        except Exception as exc:
            raise VectorStoreError("Could not initialize the Weaviate collection.") from exc

    @staticmethod
    def _uuid(document_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"eci:{document_id}"))

    @staticmethod
    def _properties(document: VectorDocument) -> dict[str, Any]:
        metadata = document.metadata
        return {
            "complaintId": document.complaint_id,
            "text": document.text,
            "product": metadata.get("product") or "",
            "company": metadata.get("company") or "",
            "state": metadata.get("state") or "",
            "issue": metadata.get("issue") or "",
            "dateReceived": str(metadata.get("date_received") or ""),
            "contentHash": metadata.get("content_hash") or "",
        }

    def upsert(self, documents: Sequence[VectorDocument]) -> int:
        if not documents:
            return 0
        self.initialize()
        client = self._connect()
        collection = client.collections.use(self.settings.weaviate_collection)
        try:
            for document in documents:
                object_uuid = self._uuid(document.document_id)
                properties = self._properties(document)
                if collection.data.exists(object_uuid):
                    collection.data.update(
                        uuid=object_uuid,
                        properties=properties,
                        vector=document.vector,
                    )
                else:
                    collection.data.insert(
                        uuid=object_uuid,
                        properties=properties,
                        vector=document.vector,
                    )
            return len(documents)
        except Exception as exc:
            raise VectorStoreError("Weaviate document upsert failed.") from exc

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        self.initialize()
        client = self._connect()
        try:
            from weaviate.classes.query import Filter, MetadataQuery

            where_filter = None
            if filters:
                property_names = {"product": "product", "state": "state", "company": "company"}
                for field, property_name in property_names.items():
                    value = getattr(filters, field)
                    if not value:
                        continue
                    condition = Filter.by_property(property_name).equal(value)
                    where_filter = condition if where_filter is None else where_filter & condition

            collection = client.collections.use(self.settings.weaviate_collection)
            query_arguments: dict[str, Any] = {
                "near_vector": query_vector,
                "limit": top_k,
                "return_metadata": MetadataQuery(distance=True),
            }
            if where_filter is not None:
                query_arguments["filters"] = where_filter
            response = collection.query.near_vector(**query_arguments)
            results: list[SearchResult] = []
            for item in response.objects:
                properties = item.properties
                distance = float(item.metadata.distance) if item.metadata.distance is not None else None
                score = 1.0 - distance if distance is not None else 0.0
                results.append(
                    SearchResult(
                        complaint_id=str(properties.get("complaintId", "")),
                        text=str(properties.get("text", "")),
                        score=max(-1.0, min(1.0, score)),
                        distance=distance,
                        metadata={
                            "product": properties.get("product"),
                            "company": properties.get("company"),
                            "state": properties.get("state"),
                            "issue": properties.get("issue"),
                            "date_received": properties.get("dateReceived"),
                            "content_hash": properties.get("contentHash"),
                        },
                    )
                )
            return results
        except Exception as exc:
            raise VectorStoreError("Weaviate similarity search failed.") from exc

    def health_check(self) -> tuple[bool, str]:
        try:
            client = self._connect()
            if client.is_ready():
                return True, "Weaviate is ready"
            return False, "Weaviate is not ready"
        except VectorStoreError:
            LOGGER.exception("Weaviate health check failed")
            return False, "Weaviate connection failed"

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            finally:
                self.client = None


def build_vector_store(settings: Settings) -> VectorStore:
    if settings.vector_backend == "weaviate":
        return WeaviateVectorStore(settings)
    return LocalJsonVectorStore(settings.vector_index_path)
