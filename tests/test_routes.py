from fastapi.testclient import TestClient

from services.gateway.main import create_app as create_gateway_app
from services.inference_adapter.main import create_app as create_inference_adapter_app
from services.name_service.main import create_app as create_name_service_app
from services.replica.main import create_app as create_replica_app


def test_gateway_routes() -> None:
    client = TestClient(create_gateway_app())
    assert client.get("/health").status_code == 200
    assert client.post("/cache/query", json={"prompt": "hello", "model_id": "demo"}).status_code == 200
    assert client.post("/cache/write", json={"prompt": "hello", "response_text": "world"}).status_code == 200
    assert client.post("/admin/faults/replica-b", json={"mode": "pause_node", "duration_sec": 10, "once": True}).status_code == 200


def test_name_service_routes() -> None:
    client = TestClient(create_name_service_app())
    assert client.get("/health").status_code == 200
    assert client.post("/register", json={"replica_id": "replica-a", "host": "127.0.0.1", "port": 8201}).status_code == 200
    assert client.post("/heartbeat", json={"replica_id": "replica-a", "status": "healthy"}).status_code == 200
    assert client.get("/members").status_code == 200


def test_replica_routes() -> None:
    client = TestClient(create_replica_app())
    assert client.get("/health").status_code == 200
    assert client.post("/cache/read", json={"prompt": "hello"}).status_code == 200
    assert client.post("/cache/write", json={"prompt": "hello", "response_text": "world"}).status_code == 200
    assert client.post("/sync/snapshot", json={"replica_id": "replica-a"}).status_code == 200
    assert client.post("/sync/replay", json={"replica_id": "replica-a", "operation_count": 0}).status_code == 200
    assert client.post("/admin/faults", json={"mode": "pause_node", "duration_sec": 10, "once": True}).status_code == 200


def test_inference_adapter_routes() -> None:
    client = TestClient(create_inference_adapter_app())
    assert client.get("/health").status_code == 200
    assert client.post("/infer", json={"prompt": "hello"}).status_code == 200
