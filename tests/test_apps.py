from services.gateway.main import create_app as create_gateway_app
from services.inference_adapter.main import create_app as create_inference_adapter_app
from services.name_service.main import create_app as create_name_service_app
from services.replica.main import create_app as create_replica_app


def test_gateway_app_creation() -> None:
    assert create_gateway_app().title.endswith("Gateway")


def test_name_service_app_creation() -> None:
    assert create_name_service_app().title.endswith("Name Service")


def test_replica_app_creation() -> None:
    assert "Replica" in create_replica_app().title


def test_inference_adapter_app_creation() -> None:
    assert create_inference_adapter_app().title.endswith("Inference Adapter")

