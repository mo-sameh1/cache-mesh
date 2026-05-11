from services.replica.config import get_settings


class CacheService:
    """Placeholder for exact-match and semantic cache operations."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def read(self, payload: dict) -> dict:
        return {
            "service": "replica",
            "action": "cache.read",
            "status": "placeholder",
            "detail": "Replica read path is scaffolded. Exact-match and semantic lookup are still TODO.",
            "hit": False,
            "response_text": None,
            "replica_id": self.settings.replica_id,
            "model_id": payload["model_id"],
            "score": None,
        }

    def write(self, payload: dict) -> dict:
        return {
            "service": "replica",
            "action": "cache.write",
            "status": "placeholder",
            "detail": "Replica write path is scaffolded. Real Qdrant writes and commit logic are still TODO.",
            "stored": False,
            "replica_id": self.settings.replica_id,
            "model_id": payload["model_id"],
            "lamport_ts": None,
        }

