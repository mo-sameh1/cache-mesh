from unittest.mock import patch

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


def _build_replica_manager() -> ReplicaManager:
    settings = ReplicaSettings(
        replica_id="replica-a",
        replica_advertised_host="replica-a",
        replica_advertised_port=8201,
        qdrant_url="http://qdrant-a:6333",
        replica_peer_targets="replica-a=http://replica-a:8201",
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


def test_error_response_fault_returns_503_on_cache_read() -> None:
    manager = _build_replica_manager()
    with TestClient(create_replica_app(replica_manager=manager)) as client:
        client.post("/admin/faults", json={"mode": "error_response", "duration_sec": 10, "once": True})

        response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})
        assert response.status_code == 503
        assert "Fault injection" in response.json()["detail"]


def test_pause_node_fault_delays_cache_read() -> None:
    manager = _build_replica_manager()
    with patch("services.replica.fault_service.time.sleep") as sleep_mock:
        with TestClient(create_replica_app(replica_manager=manager)) as client:
            client.post("/admin/faults", json={"mode": "pause_node", "duration_sec": 5, "once": True})
            response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})

            assert response.status_code == 200
            sleep_mock.assert_called_once_with(5)


def test_slow_response_fault_delays_but_completes() -> None:
    manager = _build_replica_manager()
    with patch("services.replica.fault_service.time.sleep") as sleep_mock:
        with TestClient(create_replica_app(replica_manager=manager)) as client:
            client.post("/admin/faults", json={"mode": "slow_response", "duration_sec": 3, "once": True})
            response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})

            assert response.status_code == 200
            sleep_mock.assert_called_once_with(2)


def test_once_true_fault_only_affects_single_request() -> None:
    manager = _build_replica_manager()

    with patch("services.replica.fault_service.time.sleep") as sleep_mock:
        with TestClient(create_replica_app(replica_manager=manager)) as client:
            client.post("/admin/faults", json={"mode": "slow_response", "duration_sec": 2, "once": True})

            first_response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})
            second_response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})

            assert first_response.status_code == 200
            assert second_response.status_code == 200
            assert sleep_mock.call_count == 1


def test_expired_fault_no_longer_affects_requests() -> None:
    manager = _build_replica_manager()
    with patch("services.replica.fault_service.time.sleep") as sleep_mock:
        with TestClient(create_replica_app(replica_manager=manager)) as client:
            client.post("/admin/faults", json={"mode": "slow_response", "duration_sec": 0, "once": False})
            response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})

            assert response.status_code == 200
            sleep_mock.assert_not_called()


def test_sync_routes_are_affected_by_fault_state() -> None:
    manager = _build_replica_manager()
    with TestClient(create_replica_app(replica_manager=manager)) as client:
        client.post("/admin/faults", json={"mode": "error_response", "duration_sec": 10, "once": True})

        response = client.post("/sync/snapshot", json={"replica_id": "replica-a"})
        assert response.status_code == 503
