import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from qdrant_client import QdrantClient
from qdrant_client.http import models

from services.replica.config import get_settings
from shared.config import ReplicaSettings


@dataclass
class StoredCacheEntry:
    prompt: str
    response_text: str
    model_id: str
    lamport_ts: int
    replica_origin: str | None = None
    score: float | None = None


class VectorStoreAdapter:
    """Qdrant-backed storage for exact and semantic cache retrieval."""

    def __init__(
        self,
        settings: ReplicaSettings | None = None,
        client_factory: Callable[..., QdrantClient] | None = None,
        vector_size: int | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client_factory = client_factory or QdrantClient
        self._client: QdrantClient | None = None
        self._vector_size = vector_size or self.settings.semantic_vector_size

    def describe(self) -> dict:
        status = "ok"
        detail = "Qdrant connectivity probe succeeded and replica cache collection is ready."
        count = None
        try:
            self.ensure_collection()
            count = self.count_entries()
        except Exception as exc:  # pragma: no cover - client library exception types vary by transport
            status = "degraded"
            detail = f"Qdrant probe failed: {exc}"

        return {
            "service": "replica",
            "action": "vector-store.describe",
            "status": status,
            "detail": detail,
            "qdrant_url": self.settings.qdrant_url,
            "collection": self.settings.qdrant_collection,
            "entry_count": count,
        }

    def ensure_collection(self) -> None:
        client = self._ensure_client()
        if client.collection_exists(self.settings.qdrant_collection):
            return
        client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=self._vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def find_exact(self, prompt: str, model_id: str) -> StoredCacheEntry | None:
        self.ensure_collection()
        records, _ = self._ensure_client().scroll(
            self.settings.qdrant_collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="prompt", match=models.MatchValue(value=prompt)),
                    models.FieldCondition(key="model_id", match=models.MatchValue(value=model_id)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            return None
        return self._record_to_entry(records[0], score=1.0)

    def find_semantic(
        self,
        *,
        model_id: str,
        vector: list[float],
        threshold: float,
    ) -> StoredCacheEntry | None:
        self.ensure_collection()
        response = self._ensure_client().query_points(
            self.settings.qdrant_collection,
            query=vector,
            query_filter=models.Filter(
                must=[models.FieldCondition(key="model_id", match=models.MatchValue(value=model_id))]
            ),
            limit=1,
            score_threshold=threshold,
            with_payload=True,
            with_vectors=False,
        )
        points = getattr(response, "points", response)
        if not points:
            return None
        point = points[0]
        return self._record_to_entry(point, score=float(getattr(point, "score", 0.0)))

    def upsert_entry(
        self,
        *,
        prompt: str,
        response_text: str,
        model_id: str,
        lamport_ts: int,
        vector: list[float],
        replica_origin: str | None = None,
    ) -> None:
        self.ensure_collection()
        point = models.PointStruct(
            id=self._point_id(prompt, model_id),
            vector=vector,
            payload={
                "prompt": prompt,
                "response_text": response_text,
                "model_id": model_id,
                "lamport_ts": lamport_ts,
                "replica_origin": replica_origin,
            },
        )
        self._ensure_client().upsert(self.settings.qdrant_collection, [point], wait=True)

    def count_entries(self) -> int:
        records, _ = self._ensure_client().scroll(
            self.settings.qdrant_collection,
            limit=1024,
            with_payload=False,
            with_vectors=False,
        )
        return len(records)

    def close(self) -> None:
        if self._client is None:
            return
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        self._client = None

    def _ensure_client(self) -> QdrantClient:
        if self._client is None:
            self._client = self._client_factory(url=self.settings.qdrant_url)
        return self._client

    @staticmethod
    def _point_id(prompt: str, model_id: str) -> str:
        digest = hashlib.sha256(f"{model_id}\0{prompt}".encode("utf-8")).hexdigest()
        return digest

    @staticmethod
    def _record_to_entry(record: Any, *, score: float | None) -> StoredCacheEntry:
        payload = getattr(record, "payload", None) or {}
        return StoredCacheEntry(
            prompt=payload["prompt"],
            response_text=payload["response_text"],
            model_id=payload["model_id"],
            lamport_ts=int(payload["lamport_ts"]),
            replica_origin=payload.get("replica_origin"),
            score=score,
        )
