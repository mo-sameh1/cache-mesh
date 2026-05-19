from typing import Callable

from qdrant_client import QdrantClient

from services.replica.config import get_settings
from shared.config import ReplicaSettings


class VectorStoreAdapter:
    """Low-level Qdrant shell for connectivity checks and future data operations."""

    def __init__(
        self,
        settings: ReplicaSettings | None = None,
        client_factory: Callable[..., QdrantClient] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client_factory = client_factory or QdrantClient
        self._client: QdrantClient | None = None

    def describe(self) -> dict:
        status = "ok"
        detail = "Qdrant connectivity probe succeeded. Collection management is still deferred."
        try:
            self._ensure_client().get_collections()
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
        }

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

