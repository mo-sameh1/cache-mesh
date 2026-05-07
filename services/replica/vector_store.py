from shared.protocol import placeholder_response


class VectorStoreAdapter:
    """Placeholder adapter for local Qdrant access."""

    def describe(self) -> dict:
        return placeholder_response(
            service="replica",
            action="vector-store.describe",
            detail="Qdrant adapter is scaffolded only. Real collection setup and point I/O are still TODO.",
        )

