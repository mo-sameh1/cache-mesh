from shared.protocol import placeholder_response


class CacheService:
    """Placeholder for exact-match and semantic cache operations."""

    def read(self, payload: dict) -> dict:
        return placeholder_response(
            service="replica",
            action="cache.read",
            detail="Replica read path is scaffolded only. Exact-match and semantic cache lookup are still TODO.",
            received=payload,
        )

    def write(self, payload: dict) -> dict:
        return placeholder_response(
            service="replica",
            action="cache.write",
            detail="Replica write path is scaffolded only. Real Qdrant writes and replicated commit logic are still TODO.",
            received=payload,
        )

