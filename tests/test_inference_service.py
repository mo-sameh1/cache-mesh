from fastapi.testclient import TestClient

from services.inference_adapter.main import create_app as create_inference_adapter_app
from services.inference_adapter.runtime import InferenceResult, InferenceRuntimeError, StreamEvent
from services.inference_adapter.service import InferenceService
from shared.config import InferenceAdapterSettings


class FakeRuntime:
    def __init__(
        self,
        *,
        health_status: str = "ok",
        health_detail: str = "ready",
        fail_infer: bool = False,
        fail_stream: bool = False,
    ) -> None:
        self.health_status = health_status
        self.health_detail = health_detail
        self.fail_infer = fail_infer
        self.fail_stream = fail_stream
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def health(self) -> tuple[str, str]:
        return self.health_status, self.health_detail

    def infer(self, payload: dict) -> InferenceResult:
        if self.fail_infer:
            raise InferenceRuntimeError("sync inference failed")
        return InferenceResult(
            response_text="runtime answer",
            model_id=payload["model_id"],
            provider="fake-runtime",
        )

    def stream(self, payload: dict):
        if self.fail_stream:
            raise InferenceRuntimeError("stream inference failed")
        yield StreamEvent(event="token", data="runtime ")
        yield StreamEvent(
            event="done",
            data='{"response_text":"runtime answer","model_id":"%s","provider":"fake-runtime"}'
            % payload["model_id"],
        )


def test_inference_lifespan_starts_and_stops_runtime() -> None:
    runtime = FakeRuntime()
    service = InferenceService(settings=InferenceAdapterSettings(), runtime=runtime)

    with TestClient(create_inference_adapter_app(inference_service=service)):
        assert runtime.started is True
        assert runtime.stopped is False

    assert runtime.stopped is True


def test_sync_inference_returns_503_on_runtime_error() -> None:
    runtime = FakeRuntime(fail_infer=True)
    service = InferenceService(settings=InferenceAdapterSettings(), runtime=runtime)

    with TestClient(create_inference_adapter_app(inference_service=service)) as client:
        response = client.post("/infer", json={"prompt": "hello", "model_id": "demo"})

    assert response.status_code == 503
    assert response.json()["detail"] == "sync inference failed"


def test_streaming_inference_emits_error_event() -> None:
    runtime = FakeRuntime(fail_stream=True)
    service = InferenceService(settings=InferenceAdapterSettings(), runtime=runtime)

    with TestClient(create_inference_adapter_app(inference_service=service)) as client:
        with client.stream("POST", "/infer/stream", json={"prompt": "hello", "model_id": "demo"}) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: error" in body
    assert "stream inference failed" in body


def test_health_reports_degraded_runtime_state() -> None:
    runtime = FakeRuntime(health_status="degraded", health_detail="model load failed")
    service = InferenceService(settings=InferenceAdapterSettings(), runtime=runtime)

    with TestClient(create_inference_adapter_app(inference_service=service)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["detail"] == "model load failed"
