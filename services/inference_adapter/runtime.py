from dataclasses import dataclass
from threading import Thread
from typing import Generator

from shared.config import InferenceAdapterSettings


class InferenceRuntimeError(Exception):
    """Raised when the inference runtime cannot serve a request."""


@dataclass
class InferenceResult:
    response_text: str
    model_id: str
    provider: str


@dataclass
class StreamEvent:
    event: str
    data: str


class StubInferenceRuntime:
    provider = "stub"

    def __init__(self, settings: InferenceAdapterSettings) -> None:
        self.settings = settings
        self._ready = False

    def start(self) -> None:
        self._ready = True

    def stop(self) -> None:
        self._ready = False

    def health(self) -> tuple[str, str]:
        if self._ready:
            return "ok", "Inference stub backend is ready."
        return "degraded", "Inference stub backend is not ready."

    def infer(self, payload: dict) -> InferenceResult:
        text = "stub inference response"
        return InferenceResult(
            response_text=text,
            model_id=payload["model_id"],
            provider=self.provider,
        )

    def stream(self, payload: dict) -> Generator[StreamEvent, None, None]:
        chunks = ["stub ", "inference ", "response"]
        aggregated = ""
        for chunk in chunks:
            aggregated += chunk
            yield StreamEvent(event="token", data=chunk)
        yield StreamEvent(
            event="done",
            data=_json_data(
                {
                    "response_text": aggregated,
                    "model_id": payload["model_id"],
                    "provider": self.provider,
                }
            ),
        )


class HFTransformersRuntime:
    provider = "huggingface-transformers"

    def __init__(self, settings: InferenceAdapterSettings) -> None:
        self.settings = settings
        self._model = None
        self._tokenizer = None
        self._streamer_cls = None
        self._ready = False
        self._last_error: str | None = None

    def start(self) -> None:
        try:
            self._ensure_loaded()
            self._ready = True
            self._last_error = None
        except Exception as exc:  # pragma: no cover - exercised through service-level failure tests
            self._ready = False
            self._last_error = str(exc)

    def stop(self) -> None:
        self._model = None
        self._tokenizer = None
        self._ready = False

    def health(self) -> tuple[str, str]:
        if self._ready:
            return "ok", f"HF transformers runtime is ready for {self.settings.inference_model_id}."
        if self._last_error:
            return "degraded", f"HF transformers runtime is unavailable: {self._last_error}"
        return "degraded", "HF transformers runtime has not been initialized."

    def infer(self, payload: dict) -> InferenceResult:
        aggregated = ""
        for event in self.stream(payload):
            if event.event == "token":
                aggregated += event.data
            elif event.event == "done":
                done = _parse_json_data(event.data)
                aggregated = done["response_text"]
        return InferenceResult(
            response_text=aggregated,
            model_id=payload["model_id"],
            provider=self.provider,
        )

    def stream(self, payload: dict) -> Generator[StreamEvent, None, None]:
        if not self._ready:
            raise InferenceRuntimeError(self.health()[1])

        tokenizer, model, streamer_cls = self._ensure_loaded()
        prompt = self._format_prompt(tokenizer, payload["prompt"])
        inputs = tokenizer(prompt, return_tensors="pt")
        if self.settings.inference_device == "cpu":
            inputs = {key: value.to("cpu") for key, value in inputs.items()}
        elif hasattr(model, "device"):
            inputs = {key: value.to(model.device) for key, value in inputs.items()}

        streamer = streamer_cls(tokenizer, skip_prompt=True, skip_special_tokens=True)
        generated_chunks: list[str] = []
        generation_error: list[Exception] = []
        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": self.settings.inference_max_new_tokens,
            "temperature": self.settings.inference_temperature,
            "top_p": self.settings.inference_top_p,
            "do_sample": self.settings.inference_temperature > 0,
        }

        def run_generation() -> None:
            try:
                model.generate(**generation_kwargs)
            except Exception as exc:  # pragma: no cover - depends on backend runtime behavior
                generation_error.append(exc)

        thread = Thread(target=run_generation, daemon=True)
        thread.start()

        for chunk in streamer:
            generated_chunks.append(chunk)
            yield StreamEvent(event="token", data=chunk)

        thread.join()
        if generation_error:
            raise InferenceRuntimeError(str(generation_error[0]))

        yield StreamEvent(
            event="done",
            data=_json_data(
                {
                    "response_text": "".join(generated_chunks),
                    "model_id": payload["model_id"],
                    "provider": self.provider,
                }
            ),
        )

    def _load_backend(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TextIteratorStreamer
        except ImportError as exc:
            raise InferenceRuntimeError(
                "HF transformers backend dependencies are not installed. Use the dedicated inference runtime lane."
            ) from exc

        model_kwargs = {}
        if self.settings.inference_load_in_4bit and torch.cuda.is_available():
            model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
            model_kwargs["device_map"] = "auto"
        elif torch.cuda.is_available():
            model_kwargs["device_map"] = "auto"
        elif self.settings.inference_device == "cpu":
            model_kwargs["device_map"] = None

        tokenizer = AutoTokenizer.from_pretrained(self.settings.inference_model_id)
        model = AutoModelForCausalLM.from_pretrained(
            self.settings.inference_model_id,
            **model_kwargs,
        )
        self._tokenizer = tokenizer
        self._model = model
        self._streamer_cls = TextIteratorStreamer
        return tokenizer, model, TextIteratorStreamer

    def _ensure_loaded(self):
        if self._model is not None and self._tokenizer is not None and self._streamer_cls is not None:
            return self._tokenizer, self._model, self._streamer_cls
        return self._load_backend()

    @staticmethod
    def _format_prompt(tokenizer, prompt: str) -> str:
        if hasattr(tokenizer, "apply_chat_template"):
            return tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
        return prompt


def _json_data(payload: dict) -> str:
    import json

    return json.dumps(payload)


def _parse_json_data(payload: str) -> dict:
    import json

    return json.loads(payload)
