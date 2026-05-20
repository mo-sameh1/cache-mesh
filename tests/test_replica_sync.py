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


def test_sync_replay_route_accepts_snapshot_id_and_replays_state() -> None:
    manager = _build_replica_manager("replica-a", 8201)
    with TestClient(create_replica_app(replica_manager=manager)) as client:
        write_response = client.post(
            "/cache/write",
            json={"prompt": "recover prompt", "response_text": "recover it", "model_id": "demo"},
        )
        assert write_response.status_code == 200

        snapshot_response = client.post("/sync/snapshot", json={"replica_id": "replica-a"})
        assert snapshot_response.status_code == 200
        snapshot_id = snapshot_response.json()["snapshot_id"]

        replay_response = client.post(
            "/sync/replay",
            json={"replica_id": "replica-a", "snapshot_id": snapshot_id, "operation_count": 1},
        )
        assert replay_response.status_code == 200
        assert replay_response.json()["accepted"] is True
        assert replay_response.json()["replayed_operations"] == 1


def test_sync_replay_snapshot_not_found_returns_unavailable() -> None:
    manager = _build_replica_manager("replica-a", 8201)
    with TestClient(create_replica_app(replica_manager=manager)) as client:
        response = client.post(
            "/sync/replay",
            json={"replica_id": "replica-a", "snapshot_id": "missing-snapshot-id", "operation_count": 0},
        )

        assert response.status_code == 200
        assert response.json()["accepted"] is False
        assert response.json()["status"] == "unavailable"


def test_replayed_state_becomes_part_of_future_snapshots() -> None:
    manager_a = _build_replica_manager("replica-a", 8201)
    with TestClient(create_replica_app(replica_manager=manager_a)) as client_a:
        client_a.post(
            "/cache/write",
            json={"prompt": "shared prompt", "response_text": "shared value", "model_id": "demo"},
        )
        snapshot_response = client_a.post("/sync/snapshot", json={"replica_id": "replica-a"})
        snapshot_id = snapshot_response.json()["snapshot_id"]

    manager_b = _build_replica_manager("replica-b", 8202)
    manager_b.sync_service._snapshots[snapshot_id] = list(manager_a.sync_service._snapshots[snapshot_id])
    replay_response = manager_b.replay({"replica_id": "replica-b", "snapshot_id": snapshot_id, "operation_count": 1})
    assert replay_response["accepted"] is True

    manager_b_snapshot = manager_b.sync_service.snapshot({"replica_id": "replica-b"})
    assert len(manager_b_snapshot["snapshot_id"]) > 0
    assert len(manager_b.sync_service._snapshots[manager_b_snapshot["snapshot_id"]]) == 1

    manager_c = _build_replica_manager("replica-c", 8203)
    manager_c.sync_service._snapshots[manager_b_snapshot["snapshot_id"]] = list(manager_b.sync_service._snapshots[manager_b_snapshot["snapshot_id"]])
    replay_response_c = manager_c.replay({"replica_id": "replica-c", "snapshot_id": manager_b_snapshot["snapshot_id"], "operation_count": 1})
    assert replay_response_c["accepted"] is True
    cache_hit = manager_c.read_cache({"prompt": "shared prompt", "model_id": "demo"})
    assert cache_hit["hit"] is True
    assert cache_hit["response_text"] == "shared value"
