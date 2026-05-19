from fastapi.testclient import TestClient

from services.replica.cache_service import CacheService
from services.replica.embedding import DeterministicTestEmbedder
from services.gateway.main import create_app as create_gateway_app
from services.inference_adapter.main import create_app as create_inference_adapter_app
from services.name_service.main import create_app as create_name_service_app
from services.replica.manager import ReplicaManager
from services.replica.main import create_app as create_replica_app
from services.replica.vector_store import VectorStoreAdapter
from shared.config import ReplicaSettings
from tests.replica_fakes import FakeQdrantClient


class FakeNameServiceClient:
    async def register(self, payload: dict) -> dict:
        return {"registered": True, "member": payload}

    async def heartbeat(self, payload: dict) -> dict:
        return {"accepted": True, "member": payload}

    async def close(self) -> None:
        return None


def test_gateway_routes() -> None:
    client = TestClient(create_gateway_app())
    assert client.get("/health").status_code == 200

    query_response = client.post("/cache/query", json={"prompt": "hello", "model_id": "demo"})
    assert query_response.status_code == 200
    assert "cache_status" in query_response.json()

    write_response = client.post("/cache/write", json={"prompt": "hello", "response_text": "world"})
    assert write_response.status_code == 200
    assert "stored" in write_response.json()

    fault_response = client.post("/admin/faults/replica-b", json={"mode": "pause_node", "duration_sec": 10, "once": True})
    assert fault_response.status_code == 200
    assert fault_response.json()["target_replica_id"] == "replica-b"


def test_name_service_routes() -> None:
    client = TestClient(create_name_service_app())
    assert client.get("/health").status_code == 200

    register_response = client.post("/register", json={"replica_id": "replica-a", "host": "127.0.0.1", "port": 8201})
    assert register_response.status_code == 200
    assert register_response.json()["registered"] is True

    heartbeat_response = client.post("/heartbeat", json={"replica_id": "replica-a", "status": "healthy"})
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["accepted"] is True

    members_response = client.get("/members")
    assert members_response.status_code == 200
    assert members_response.json()["members"][0]["replica_id"] == "replica-a"


def test_replica_routes() -> None:
    settings = ReplicaSettings(
        replica_id="replica-a",
        replica_advertised_host="replica-a",
        replica_advertised_port=8201,
        qdrant_url="http://qdrant-a:6333",
        replica_peer_targets="replica-a=http://replica-a:8201",
        semantic_score_threshold=0.18,
    )
    embedder = DeterministicTestEmbedder(dimensions=settings.semantic_vector_size)
    vector_store = VectorStoreAdapter(
        settings=settings,
        client_factory=FakeQdrantClient,
        vector_size=embedder.vector_size,
    )
    manager = ReplicaManager(
        settings=settings,
        cache_service=CacheService(settings=settings, vector_store=vector_store, embedder=embedder),
        name_service_client=FakeNameServiceClient(),
        vector_store=vector_store,
    )
    with TestClient(create_replica_app(replica_manager=manager)) as client:
        assert client.get("/health").status_code == 200

        read_response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})
        assert read_response.status_code == 200
        assert read_response.json()["hit"] is False

        write_response = client.post("/cache/write", json={"prompt": "hello", "response_text": "world", "model_id": "demo"})
        assert write_response.status_code == 200
        assert write_response.json()["stored"] is True
        assert write_response.json()["lamport_ts"] == 1

        hit_response = client.post("/cache/read", json={"prompt": "hello", "model_id": "demo"})
        assert hit_response.status_code == 200
        assert hit_response.json()["hit"] is True
        assert hit_response.json()["response_text"] == "world"

        semantic_seed = client.post(
            "/cache/write",
            json={
                "prompt": "how do i bake bread at home",
                "response_text": "Use flour and yeast.",
                "model_id": "demo",
            },
        )
        assert semantic_seed.status_code == 200

        semantic_hit = client.post(
            "/cache/read",
            json={
                "prompt": "bread baking instructions for beginners",
                "model_id": "demo",
                "semantic_enabled": True,
            },
        )
        assert semantic_hit.status_code == 200
        assert semantic_hit.json()["hit"] is True
        assert semantic_hit.json()["response_text"] == "Use flour and yeast."

        snapshot_response = client.post("/sync/snapshot", json={"replica_id": "replica-a"})
        assert snapshot_response.status_code == 200
        assert snapshot_response.json()["accepted"] is False

        replay_response = client.post("/sync/replay", json={"replica_id": "replica-a", "operation_count": 0})
        assert replay_response.status_code == 200
        assert replay_response.json()["replayed_operations"] == 0

        fault_response = client.post("/admin/faults", json={"mode": "pause_node", "duration_sec": 10, "once": True})
        assert fault_response.status_code == 200
        assert fault_response.json()["accepted"] is True

        vector_store_response = client.get("/vector-store")
        assert vector_store_response.status_code == 200
        assert vector_store_response.json()["status"] == "ok"

        release_response = client.post(
            "/internal/locks/write-finished",
            json={"replica_id": "replica-b"},
        )
        assert release_response.status_code == 200
        assert release_response.json()["accepted"] is True


def test_inference_adapter_routes() -> None:
    client = TestClient(create_inference_adapter_app())
    assert client.get("/health").status_code == 200

    infer_response = client.post("/infer", json={"prompt": "hello"})
    assert infer_response.status_code == 200
    assert infer_response.json()["response_text"] == "placeholder inference response"
