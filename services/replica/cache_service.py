from dataclasses import dataclass
from typing import Protocol

from services.replica.config import get_settings
from services.replica.embedding import SentenceTransformerEmbedder
from services.replica.vector_store import StoredCacheEntry, VectorStoreAdapter
from shared.config import ReplicaSettings


class Embedder(Protocol):
    @property
    def vector_size(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


@dataclass
class CacheWriteResult:
    lamport_ts: int
    vector: list[float]


class CacheService:
    """Local replica cache behavior backed by Qdrant persistence."""

    def __init__(
        self,
        settings: ReplicaSettings | None = None,
        vector_store: VectorStoreAdapter | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedder = embedder or SentenceTransformerEmbedder(settings=self.settings)
        self.vector_store = vector_store or VectorStoreAdapter(
            settings=self.settings,
            vector_size=self.embedder.vector_size,
        )

    def read(self, payload: dict) -> dict:
        exact = self.vector_store.find_exact(payload["prompt"], payload["model_id"])
        if exact is not None:
            return self._hit_response(
                exact,
                detail="Exact cache hit returned by this replica.",
                score=1.0,
            )

        if payload.get("semantic_enabled", True):
            query_vector = self.embedder.embed(payload["prompt"])
            semantic = self.vector_store.find_semantic(
                model_id=payload["model_id"],
                vector=query_vector,
                threshold=self.settings.semantic_score_threshold,
            )
            if semantic is not None:
                return self._hit_response(
                    semantic,
                    detail="Semantic cache hit returned by this replica.",
                    score=semantic.score,
                )

        return {
            "service": "replica",
            "action": "cache.read",
            "status": "ok",
            "detail": "No cache entry matched this prompt on the replica.",
            "hit": False,
            "response_text": None,
            "replica_id": self.settings.replica_id,
            "model_id": payload["model_id"],
            "score": None,
        }

    def prepare_vector(self, prompt: str) -> list[float]:
        return self.embedder.embed(prompt)

    def apply_write(
        self,
        payload: dict,
        *,
        lamport_ts: int,
        vector: list[float] | None = None,
        replica_origin: str | None = None,
    ) -> CacheWriteResult:
        resolved_vector = vector or self.prepare_vector(payload["prompt"])
        self.vector_store.upsert_entry(
            prompt=payload["prompt"],
            response_text=payload["response_text"],
            model_id=payload["model_id"],
            lamport_ts=lamport_ts,
            vector=resolved_vector,
            replica_origin=replica_origin or self.settings.replica_id,
        )
        return CacheWriteResult(lamport_ts=lamport_ts, vector=resolved_vector)

    def size(self) -> int:
        return self.vector_store.count_entries()

    def _hit_response(self, entry: StoredCacheEntry, *, detail: str, score: float | None) -> dict:
        return {
            "service": "replica",
            "action": "cache.read",
            "status": "ok",
            "detail": detail,
            "hit": True,
            "response_text": entry.response_text,
            "replica_id": self.settings.replica_id,
            "model_id": entry.model_id,
            "score": score,
        }
