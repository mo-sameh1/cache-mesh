import httpx
import pytest

from services.gateway.clients import InferenceClient, NameServiceClient, ReplicaClient
from shared.http_client import ServiceClientError


def test_name_service_client_lists_members() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "http://name-service:8100/members"
        return httpx.Response(200, json={"members": []})

    client = NameServiceClient("http://name-service:8100", 2.0, transport=httpx.MockTransport(handler))
    assert client.list_members() == {"members": []}


def test_replica_client_reads_and_writes_cache() -> None:
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/cache/read":
            return httpx.Response(200, json={"hit": False})
        return httpx.Response(200, json={"stored": True})

    client = ReplicaClient(2.0, transport=httpx.MockTransport(handler))

    assert client.read_cache("http://replica-a:8201", {"prompt": "hello"}) == {"hit": False}
    assert client.write_cache("http://replica-a:8201", {"prompt": "hello", "response_text": "world"}) == {"stored": True}
    assert seen_paths == ["/cache/read", "/cache/write"]


def test_inference_client_infers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/infer"
        return httpx.Response(200, json={"response_text": "world"})

    client = InferenceClient("http://inference-adapter:8050", 2.0, transport=httpx.MockTransport(handler))
    assert client.infer({"prompt": "hello"}) == {"response_text": "world"}


def test_client_raises_on_remote_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = ReplicaClient(2.0, transport=httpx.MockTransport(handler))

    with pytest.raises(ServiceClientError):
        client.read_cache("http://replica-a:8201", {"prompt": "hello"})
