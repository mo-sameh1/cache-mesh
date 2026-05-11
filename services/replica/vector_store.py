from services.replica.config import get_settings


class VectorStoreAdapter:
    """Placeholder adapter for local Qdrant access."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def describe(self) -> dict:
        return {
            "service": "replica",
            "action": "vector-store.describe",
            "status": "placeholder",
            "detail": "Qdrant adapter is scaffolded. Collection setup and point I/O are still TODO.",
            "qdrant_url": self.settings.qdrant_url,
            "collection": self.settings.qdrant_collection,
        }

