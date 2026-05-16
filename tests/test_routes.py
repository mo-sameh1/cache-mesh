from fastapi.testclient import TestClient

from services.gateway.main import create_app as create_gateway_app
from services.inference_adapter.main import create_app as create_inference_adapter_app
from services.name_service.main import create_app as create_name_service_app
from services.replica.main import create_app as create_replica_app


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
    client = TestClient(create_replica_app())
    assert client.get("/health").status_code == 200

    read_response = client.post("/cache/read", json={"prompt": "hello"})
    assert read_response.status_code == 200
    assert read_response.json()["hit"] is False

    write_response = client.post("/cache/write", json={"prompt": "hello", "response_text": "world"})
    assert write_response.status_code == 200
    assert write_response.json()["stored"] is False

    snapshot_response = client.post("/sync/snapshot", json={"replica_id": "replica-a"})
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["accepted"] is False

    replay_response = client.post("/sync/replay", json={"replica_id": "replica-a", "operation_count": 0})
    assert replay_response.status_code == 200
    assert replay_response.json()["replayed_operations"] == 0

    fault_response = client.post("/admin/faults", json={"mode": "pause_node", "duration_sec": 10, "once": True})
    assert fault_response.status_code == 200
    assert fault_response.json()["accepted"] is True


def test_inference_adapter_routes() -> None:
    client = TestClient(create_inference_adapter_app())
    assert client.get("/health").status_code == 200

    infer_response = client.post("/infer", json={"prompt": "hello"})
    assert infer_response.status_code == 200
    assert infer_response.json()["response_text"] == "placeholder inference response"
