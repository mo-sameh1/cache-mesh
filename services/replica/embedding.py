import hashlib
import math
import re
from typing import Any

from services.replica.config import get_settings
from shared.config import ReplicaSettings


class EmbeddingError(RuntimeError):
    """Raised when the semantic embedding model cannot serve a request."""


class SentenceTransformerEmbedder:
    """Lazy wrapper around a lightweight production embedding model."""

    def __init__(
        self,
        settings: ReplicaSettings | None = None,
        model: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._model = model
        self._resolved_device = "unknown"

    @property
    def vector_size(self) -> int:
        return self.settings.semantic_vector_size

    def embed(self, text: str) -> list[float]:
        model = self._ensure_model()
        try:
            vector = model.encode(text, normalize_embeddings=True)
        except Exception as exc:  # pragma: no cover - depends on runtime backend behavior
            raise EmbeddingError(f"Semantic embedding failed: {exc}") from exc

        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        return [float(component) for component in vector]

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised through local dependency installation
            raise EmbeddingError(
                "sentence-transformers is not installed. Install replica semantic dependencies before serving search."
            ) from exc

        requested_device = self.settings.semantic_embedding_device.lower().strip()
        if requested_device == "cuda":
            device = "cuda"
        elif requested_device == "cpu":
            device = "cpu"
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self._resolved_device = device
        self._model = SentenceTransformer(self.settings.semantic_embedding_model_id, device=device)
        return self._model


class DeterministicTestEmbedder:
    """Deterministic embedder for tests that need semantic behavior without model downloads."""

    _token_pattern = re.compile(r"[a-z0-9]+")

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    @property
    def vector_size(self) -> int:
        return self.dimensions

    def embed(self, text: str) -> list[float]:
        features = self._features(text)
        vector = [0.0] * self.dimensions
        if not features:
            vector[0] = 1.0
            return vector

        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            for index in range(0, 6, 2):
                dimension = digest[index] % self.dimensions
                sign = 1.0 if digest[index + 1] % 2 == 0 else -1.0
                vector[dimension] += sign

        magnitude = math.sqrt(sum(component * component for component in vector))
        if magnitude == 0:
            vector[0] = 1.0
            return vector
        return [component / magnitude for component in vector]

    def _features(self, text: str) -> list[str]:
        normalized = text.lower().strip()
        tokens = self._token_pattern.findall(normalized)
        features = list(tokens)
        features.extend(f"{tokens[index]}_{tokens[index + 1]}" for index in range(len(tokens) - 1))
        compact = re.sub(r"\s+", " ", normalized)
        features.extend(compact[index : index + 3] for index in range(max(0, len(compact) - 2)))
        return features
