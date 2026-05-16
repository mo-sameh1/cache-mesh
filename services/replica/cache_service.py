from dataclasses import dataclass
from threading import Lock

from services.replica.config import get_settings
from shared.config import ReplicaSettings
from shared.clock import LamportClock


@dataclass
class CacheEntry:
    prompt: str
    response_text: str
    model_id: str
    lamport_ts: int


class CacheService:
    """In-memory exact-match cache for the first replica milestone."""

    def __init__(
        self,
        settings: ReplicaSettings | None = None,
        clock: LamportClock | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.clock = clock or LamportClock()
        self._entries: dict[tuple[str, str], CacheEntry] = {}
        self._lock = Lock()

    def read(self, payload: dict) -> dict:
        with self._lock:
            entry = self._entries.get(self._key(payload["prompt"], payload["model_id"]))
        if entry is None:
            return {
                "service": "replica",
                "action": "cache.read",
                "status": "ok",
                "detail": "No exact in-memory cache entry found on this replica.",
                "hit": False,
                "response_text": None,
                "replica_id": self.settings.replica_id,
                "model_id": payload["model_id"],
                "score": None,
            }

        return {
            "service": "replica",
            "action": "cache.read",
            "status": "ok",
            "detail": "Exact in-memory cache hit returned by this replica.",
            "hit": True,
            "response_text": entry.response_text,
            "replica_id": self.settings.replica_id,
            "model_id": entry.model_id,
            "score": 1.0,
        }

    def write(self, payload: dict) -> dict:
        with self._lock:
            lamport_ts = self.clock.tick()
            self._entries[self._key(payload["prompt"], payload["model_id"])] = CacheEntry(
                prompt=payload["prompt"],
                response_text=payload["response_text"],
                model_id=payload["model_id"],
                lamport_ts=lamport_ts,
            )

        return {
            "service": "replica",
            "action": "cache.write",
            "status": "ok",
            "detail": "Exact in-memory cache entry stored on this replica.",
            "stored": True,
            "replica_id": self.settings.replica_id,
            "model_id": payload["model_id"],
            "lamport_ts": lamport_ts,
        }

    def size(self) -> int:
        return len(self._entries)

    @staticmethod
    def _key(prompt: str, model_id: str) -> tuple[str, str]:
        return prompt, model_id

