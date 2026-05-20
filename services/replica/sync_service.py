from __future__ import annotations

import uuid
from typing import Dict, List, Optional


class SyncService:
    """Snapshot transfer and Lamport-ordered log replay."""

    def __init__(self) -> None:
        self._write_log: List[dict] = []
        self._snapshots: Dict[str, List[dict]] = {}

    def record_write(
        self,
        payload: dict,
        *,
        lamport_ts: int,
        vector: list[float] | None = None,
        replica_origin: str | None = None,
    ) -> None:
        self._write_log.append(
            {
                "prompt": payload["prompt"],
                "response_text": payload["response_text"],
                "model_id": payload["model_id"],
                "lamport_ts": lamport_ts,
                "vector": vector or [],
                "replica_origin": replica_origin,
            }
        )

    def snapshot(self, payload: dict) -> dict:
        since: Optional[int] = payload.get("since_lamport_ts")
        entries = [
            entry for entry in self._write_log if since is None or entry["lamport_ts"] > since
        ]
        snapshot_id = str(uuid.uuid4())
        self._snapshots[snapshot_id] = list(entries)
        return {
            "service": "replica",
            "action": "sync.snapshot",
            "status": "ok",
            "detail": (
                f"Snapshot {snapshot_id!r} created with {len(entries)} entry/entries "
                f"(since_lamport_ts={since})."
            ),
            "accepted": True,
            "replica_id": payload["replica_id"],
            "since_lamport_ts": since,
            "snapshot_id": snapshot_id,
        }

    def replay(self, payload: dict) -> dict:
        snapshot_id: Optional[str] = payload.get("snapshot_id")
        if snapshot_id is not None:
            if snapshot_id not in self._snapshots:
                return {
                    "service": "replica",
                    "action": "sync.replay",
                    "status": "unavailable",
                    "detail": f"Snapshot {snapshot_id!r} not found.",
                    "accepted": False,
                    "replica_id": payload["replica_id"],
                    "replayed_operations": 0,
                }
            entries = list(self._snapshots[snapshot_id])
        else:
            entries = list(self._write_log)

        operation_count: int = payload.get("operation_count", 0)
        if operation_count:
            entries = entries[:operation_count]
        else:
            entries = []

        return {
            "service": "replica",
            "action": "sync.replay",
            "status": "ok",
            "detail": (
                f"Replayed {len(entries)} operation(s) "
                f"for {payload['replica_id']!r}."
            ),
            "accepted": True,
            "replica_id": payload["replica_id"],
            "replayed_operations": len(entries),
            "_replay_entries": entries,
        }
