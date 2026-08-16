"""Pluggable embedding providers for offline learning and OpenAI production use."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod
from typing import Sequence

from eci.config import Settings
from eci.exceptions import ExternalServiceError

LOGGER = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_LOCAL_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "for", "from", "had", "has", "have", "how", "i", "in", "is",
    "it", "my", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "what", "when", "where", "which", "who",
    "why", "with", "about", "customer", "customers", "reporting",
    "describing", "problem", "problems",
}


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic, dependency-free embeddings for the no-secret demo.

    This uses signed feature hashing over words, word bigrams, and character
    trigrams. It demonstrates vector storage and similarity search but is not a
    replacement for a semantic production embedding model.
    """

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    @property
    def model_name(self) -> str:
        return f"local-signed-hash-{self.dimensions}d"

    @staticmethod
    def _stem(word: str) -> str:
        """Tiny deterministic stemmer used only by the dependency-free demo."""
        for suffix in ("ingly", "edly", "ing", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                return word[: -len(suffix)]
        return word

    def _features(self, text: str) -> list[tuple[str, float]]:
        words = [word for word in _TOKEN_RE.findall(text.lower()) if word not in _LOCAL_STOP_WORDS]
        stems = [self._stem(word) for word in words]
        features: list[tuple[str, float]] = []
        features.extend((f"word:{word}", 2.0) for word in words)
        features.extend((f"stem:{stem}", 3.0) for stem in stems)
        features.extend(
            (f"bigram:{left}_{right}", 4.0)
            for left, right in zip(stems, stems[1:])
        )
        # Character features help tolerate minor spelling variation but receive
        # low weight so they do not overwhelm exact business terminology.
        for word in stems:
            features.extend(
                (f"char:{word[index:index + 3]}", 0.20)
                for index in range(max(0, len(word) - 2))
            )
        return features

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature, weight in self._features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings adapter with SDK-managed retries and timeouts."""

    def __init__(self, settings: Settings) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise ExternalServiceError(
                "The openai package is not installed. Run pip install -r requirements.txt."
            ) from exc

        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),  # type: ignore[union-attr]
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    @property
    def model_name(self) -> str:
        return self.settings.openai_embedding_model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        output: list[list[float]] = []
        batch_size = 100
        try:
            for offset in range(0, len(texts), batch_size):
                batch = [text.replace("\x00", " ") for text in texts[offset : offset + batch_size]]
                response = self.client.embeddings.create(
                    model=self.settings.openai_embedding_model,
                    input=batch,
                    encoding_format="float",
                )
                ordered = sorted(response.data, key=lambda item: item.index)
                output.extend([list(item.embedding) for item in ordered])
            return output
        except Exception as exc:  # SDK exception hierarchy changes over time
            LOGGER.exception("OpenAI embedding request failed")
            raise ExternalServiceError(
                "The embedding service could not process this request. Check API access and billing."
            ) from exc


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_backend == "openai":
        return OpenAIEmbeddingProvider(settings)
    return LocalHashEmbeddingProvider(settings.local_embedding_dimensions)
