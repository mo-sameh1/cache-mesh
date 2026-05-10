class InferenceStubClient:
    """Placeholder for external or local model inference integration."""

    def infer(self, payload: dict) -> dict:
        return {
            "service": "inference-adapter",
            "action": "infer",
            "status": "placeholder",
            "detail": "Inference adapter is scaffolded. Real model inference is still TODO.",
            "response_text": "placeholder inference response",
            "model_id": payload["model_id"],
            "provider": "placeholder",
        }

