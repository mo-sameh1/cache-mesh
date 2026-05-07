from shared.protocol import placeholder_response


class InferenceStubClient:
    """Placeholder for external or local model inference integration."""

    def infer(self, payload: dict) -> dict:
        return placeholder_response(
            service="inference-adapter",
            action="infer",
            detail="Inference adapter is scaffolded only. Real model inference is still TODO.",
            received=payload,
        )

