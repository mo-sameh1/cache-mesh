from collections.abc import Generator

from services.inference_adapter.config import get_settings
from services.inference_adapter.runtime import (
    HFTransformersRuntime,
    InferenceRuntimeError,
    StreamEvent,
    StubInferenceRuntime,
)
from shared.config import InferenceAdapterSettings


class InferenceService:
    def __init__(
        self,
        settings: InferenceAdapterSettings | None = None,
        runtime=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runtime = runtime or self._build_runtime()

    def start(self) -> None:
        self.runtime.start()

    def stop(self) -> None:
        self.runtime.stop()

    def health(self) -> dict:
        status, detail = self.runtime.health()
        return {
            "service": "inference-adapter",
            "status": status,
            "detail": detail,
        }

    def infer(self, payload: dict) -> dict:
        result = self.runtime.infer(payload)
        return {
            "service": "inference-adapter",
            "action": "infer",
            "status": "ok",
            "detail": "Inference completed successfully.",
            "response_text": result.response_text,
            "model_id": result.model_id,
            "provider": result.provider,
        }

    def stream_sse(self, payload: dict) -> Generator[str, None, None]:
        try:
            for event in self.runtime.stream(payload):
                yield self._format_sse(event)
        except InferenceRuntimeError as exc:
            yield self._format_sse(StreamEvent(event="error", data=str(exc)))

    def is_ready(self) -> bool:
        return self.health()["status"] == "ok"

    def _build_runtime(self):
        if self.settings.inference_backend == "hf_transformers":
            return HFTransformersRuntime(self.settings)
        return StubInferenceRuntime(self.settings)

    @staticmethod
    def _format_sse(event: StreamEvent) -> str:
        return f"event: {event.event}\ndata: {event.data}\n\n"
