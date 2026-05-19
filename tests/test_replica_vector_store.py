from services.replica.vector_store import VectorStoreAdapter
from shared.config import ReplicaSettings


class HealthyQdrantClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def get_collections(self) -> dict:
        return {"collections": []}

    def close(self) -> None:
        return None


class FailingQdrantClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def get_collections(self) -> dict:
        raise RuntimeError("connection refused")

    def close(self) -> None:
        return None


def test_vector_store_reports_configured_url_and_collection() -> None:
    settings = ReplicaSettings(qdrant_url="http://qdrant-z:6333", qdrant_collection="entries")
    adapter = VectorStoreAdapter(settings=settings, client_factory=HealthyQdrantClient)

    response = adapter.describe()

    assert response["status"] == "ok"
    assert response["qdrant_url"] == "http://qdrant-z:6333"
    assert response["collection"] == "entries"


def test_vector_store_reports_probe_failure_without_live_qdrant() -> None:
    settings = ReplicaSettings(qdrant_url="http://qdrant-z:6333", qdrant_collection="entries")
    adapter = VectorStoreAdapter(settings=settings, client_factory=FailingQdrantClient)

    response = adapter.describe()

    assert response["status"] == "degraded"
    assert "Qdrant probe failed" in response["detail"]


def test_vector_store_creates_client_lazily_once() -> None:
    settings = ReplicaSettings(qdrant_url="http://qdrant-z:6333", qdrant_collection="entries")
    created: list[dict] = []

    def client_factory(**kwargs) -> HealthyQdrantClient:
        created.append(kwargs)
        return HealthyQdrantClient(**kwargs)

    adapter = VectorStoreAdapter(settings=settings, client_factory=client_factory)

    adapter.describe()
    adapter.describe()

    assert created == [{"url": "http://qdrant-z:6333"}]
