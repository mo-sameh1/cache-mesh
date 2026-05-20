from fastapi.testclient import TestClient

from services.replica.clients import ReplicaPeerClient
from services.replica.main import create_app as create_replica_app
from services.replica.manager import ReplicaManager
from services.replica.vector_store import VectorStoreAdapter
from shared.config import ReplicaSettings
from tests.replica_fakes import FakeQdrantClient
from services.replica.cache_service import CacheService
from services.replica.embedding import DeterministicTestEmbedder


class NoOpAsyncNameServiceClient:
    async def register(self, payload: dict) -> dict:
        return {"registered": True, "member": payload}

    async def heartbeat(self, payload: dict) -> dict:
        return {"accepted": True, "member": payload}

    async def close(self) -> None:
        return None


def _build_replica_manager(replica_id: str, port: int) -> ReplicaManager:
    settings = ReplicaSettings(
        replica_id=replica_id,
        replica_advertised_host=replica_id,
        replica_advertised_port=port,
        qdrant_url=f"http://qdrant-{replica_id[-1]}:6333",
        replica_peer_targets=f"{replica_id}=http://{replica_id}:{port}",
    )
    embedder = DeterministicTestEmbedder(dimensions=settings.semantic_vector_size)
    vector_store = VectorStoreAdapter(settings=settings, client_factory=FakeQdrantClient, vector_size=embedder.vector_size)
    cache_service = CacheService(settings=settings, vector_store=vector_store, embedder=embedder)
    return ReplicaManager(
        settings=settings,
        cache_service=cache_service,
        name_service_client=NoOpAsyncNameServiceClient(),
        vector_store=vector_store,
        peer_client=ReplicaPeerClient(timeout_sec=2.0, transport=None),
    )


def test_snapshot_returns_real_state_after_writes() -> None:
    manager = _build_replica_manager("replica-a", 8201)
    with TestClient(create_replica_app(replica_manager=manager)) as client:
        response = client.post(
            "/cache/write",
            json={"prompt": "build a tiny cache", "response_text": "store it", "model_id": "demo"},
        )
        assert response.status_code == 200

        snapshot = manager.sync_service.snapshot({"replica_id": "replica-a"})
        assert snapshot["accepted"] is True
        assert snapshot["snapshot_id"] is not None
        assert len(manager.sync_service._snapshots[snapshot["snapshot_id"]]) == 1


def test_replay_restores_state_on_new_manager() -> None:
    manager_a = _build_replica_manager("replica-a", 8201)
    with TestClient(create_replica_app(replica_manager=manager_a)) as client_a:
        client_a.post(
            "/cache/write",
            json={"prompt": "build a tiny cache", "response_text": "store it", "model_id": "demo"},
        )
        snapshot_response = manager_a.sync_service.snapshot({"replica_id": "replica-a"})
        snapshot_id = snapshot_response["snapshot_id"]

    manager_b = _build_replica_manager("replica-b", 8202)
    manager_b.sync_service._snapshots[snapshot_id] = list(manager_a.sync_service._snapshots[snapshot_id])
    replay_response = manager_b.replay({"replica_id": "replica-b", "snapshot_id": snapshot_id, "operation_count": 1})

    assert replay_response["accepted"] is True
    assert replay_response["replayed_operations"] == 1
    assert manager_b.read_cache({"prompt": "build a tiny cache", "model_id": "demo"})["hit"] is True


def test_replay_preserves_overwrite_ordering() -> None:
    manager_a = _build_replica_manager("replica-a", 8201)
    with TestClient(create_replica_app(replica_manager=manager_a)) as client_a:
        client_a.post(
            "/cache/write",
            json={"prompt": "unique prompt", "response_text": "first", "model_id": "demo"},
        )
        client_a.post(
            "/cache/write",
            json={"prompt": "unique prompt", "response_text": "second", "model_id": "demo"},
        )
        snapshot_response = manager_a.sync_service.snapshot({"replica_id": "replica-a"})
        snapshot_id = snapshot_response["snapshot_id"]

    manager_b = _build_replica_manager("replica-b", 8202)
    manager_b.sync_service._snapshots[snapshot_id] = list(manager_a.sync_service._snapshots[snapshot_id])
    replay_response = manager_b.replay({"replica_id": "replica-b", "snapshot_id": snapshot_id, "operation_count": 2})

    assert replay_response["replayed_operations"] == 2
    result = manager_b.read_cache({"prompt": "unique prompt", "model_id": "demo"})
    assert result["hit"] is True
    assert result["response_text"] == "second"
