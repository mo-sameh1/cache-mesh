import uuid

from services.replica.embedding import DeterministicTestEmbedder
from services.replica.vector_store import VectorStoreAdapter
from shared.config import ReplicaSettings
from tests.replica_fakes import FakeQdrantClient


class FailingQdrantClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def get_collections(self) -> dict:
        raise RuntimeError("connection refused")

    def collection_exists(self, collection_name: str, **kwargs) -> bool:
        raise RuntimeError("connection refused")

    def close(self) -> None:
        return None


def test_vector_store_reports_configured_url_and_collection() -> None:
    settings = ReplicaSettings(qdrant_url="http://qdrant-z:6333", qdrant_collection="entries")
    adapter = VectorStoreAdapter(settings=settings, client_factory=FakeQdrantClient, vector_size=384)

    response = adapter.describe()

    assert response["status"] == "ok"
    assert response["qdrant_url"] == "http://qdrant-z:6333"
    assert response["collection"] == "entries"
    assert response["entry_count"] == 0


def test_vector_store_reports_probe_failure_without_live_qdrant() -> None:
    settings = ReplicaSettings(qdrant_url="http://qdrant-z:6333", qdrant_collection="entries")
    adapter = VectorStoreAdapter(settings=settings, client_factory=FailingQdrantClient, vector_size=384)

    response = adapter.describe()

    assert response["status"] == "degraded"
    assert "Qdrant probe failed" in response["detail"]


def test_vector_store_creates_client_lazily_once() -> None:
    settings = ReplicaSettings(qdrant_url="http://qdrant-z:6333", qdrant_collection="entries")
    created: list[dict] = []

    def client_factory(**kwargs) -> FakeQdrantClient:
        created.append(kwargs)
        return FakeQdrantClient(**kwargs)

    adapter = VectorStoreAdapter(settings=settings, client_factory=client_factory, vector_size=384)

    adapter.describe()
    adapter.describe()

    assert created == [{"url": "http://qdrant-z:6333"}]


def test_vector_store_generates_qdrant_compatible_point_ids() -> None:
    point_id = VectorStoreAdapter._point_id("hello world", "demo")

    assert str(uuid.UUID(point_id)) == point_id


def test_vector_store_supports_exact_lookup_and_overwrite() -> None:
    settings = ReplicaSettings(qdrant_collection="entries")
    adapter = VectorStoreAdapter(settings=settings, client_factory=FakeQdrantClient, vector_size=384)
    embedder = DeterministicTestEmbedder(dimensions=384)

    adapter.upsert_entry(
        prompt="hello world",
        response_text="first",
        model_id="demo",
        lamport_ts=1,
        vector=embedder.embed("hello world"),
        replica_origin="replica-a",
    )
    adapter.upsert_entry(
        prompt="hello world",
        response_text="second",
        model_id="demo",
        lamport_ts=2,
        vector=embedder.embed("hello world"),
        replica_origin="replica-b",
    )

    entry = adapter.find_exact("hello world", "demo")

    assert entry is not None
    assert entry.response_text == "second"
    assert entry.lamport_ts == 2
    assert adapter.count_entries() == 1


def test_vector_store_supports_semantic_lookup_for_same_model() -> None:
    settings = ReplicaSettings(qdrant_collection="entries")
    adapter = VectorStoreAdapter(settings=settings, client_factory=FakeQdrantClient, vector_size=384)
    embedder = DeterministicTestEmbedder(dimensions=384)

    adapter.upsert_entry(
        prompt="how do i bake bread at home",
        response_text="Use flour, yeast, and time.",
        model_id="demo",
        lamport_ts=1,
        vector=embedder.embed("how do i bake bread at home"),
        replica_origin="replica-a",
    )
    adapter.upsert_entry(
        prompt="capital city of france",
        response_text="Paris",
        model_id="demo",
        lamport_ts=2,
        vector=embedder.embed("capital city of france"),
        replica_origin="replica-a",
    )
    adapter.upsert_entry(
        prompt="how do i bake bread at home",
        response_text="wrong model",
        model_id="other",
        lamport_ts=3,
        vector=embedder.embed("how do i bake bread at home"),
        replica_origin="replica-a",
    )

    semantic = adapter.find_semantic(
        model_id="demo",
        vector=embedder.embed("bread baking instructions for beginners"),
        threshold=0.18,
    )

    assert semantic is not None
    assert semantic.response_text == "Use flour, yeast, and time."
    assert semantic.model_id == "demo"
    assert semantic.score is not None
