"""Snapshot transfer and Lamport-ordered log replay for a replica.

Every cache write is recorded in a Lamport-ordered write log.  snapshot()
serialises entries from that log (optionally since a given Lamport timestamp)
into an in-memory snapshot store and returns a snapshot_id.  replay() walks
the full write log in timestamp order, updating the clock to reflect the
highest timestamp seen.

This gives the gateway enough information to reconstruct the causal order of
writes across replicas without a centralised sequencer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from shared.clock import LamportClock


@dataclass
class WriteEntry:
    """A single logged cache write with its Lamport timestamp."""

    lamport_ts: int
    prompt: str
    response_text: str
    model_id: str


class SyncService:
    """Snapshot transfer and Lamport-ordered log replay."""

    def __init__(self) -> None:
        self.clock: LamportClock = LamportClock()
        # Ordered write log — entries are always appended with monotonically
        # increasing Lamport timestamps produced by self.clock.tick().
        self._write_log: List[WriteEntry] = []
        # Stored snapshots keyed by snapshot_id (UUID str).
        self._snapshots: Dict[str, List[WriteEntry]] = {}

    # ------------------------------------------------------------------
    # write-path integration (called by route handlers after a cache write)

    def record_write(self, prompt: str, response_text: str, model_id: str) -> int:
        """Append a write to the log and return its Lamport timestamp."""
        ts = self.clock.tick()
        self._write_log.append(WriteEntry(ts, prompt, response_text, model_id))
        return ts

    def update_clock(self, remote_ts: int) -> int:
        """Merge a remote Lamport timestamp into our clock (used on read hits)."""
        return self.clock.update(remote_ts)

    # ------------------------------------------------------------------
    # sync API — called by routes

    def snapshot(self, payload: dict) -> dict:
        """Serialise write-log entries into a named snapshot.

        If since_lamport_ts is provided, only entries with a strictly greater
        timestamp are included, enabling incremental sync.
        """
        since: Optional[int] = payload.get("since_lamport_ts")
        entries = (
            [e for e in self._write_log if e.lamport_ts > since]
            if since is not None
            else list(self._write_log)
        )
        snap_id = str(uuid.uuid4())
        self._snapshots[snap_id] = entries
        return {
            "service": "replica",
            "action": "sync.snapshot",
            "status": "ok",
            "detail": (
                f"Snapshot {snap_id!r} created with {len(entries)} entry/entries "
                f"(since_lamport_ts={since})."
            ),
            "accepted": True,
            "replica_id": payload["replica_id"],
            "since_lamport_ts": since,
            "snapshot_id": snap_id,
        }

    def replay(self, payload: dict) -> dict:
        """Replay all write-log entries in Lamport order.

        Updates the local clock to the highest Lamport timestamp seen so
        that subsequent writes are causally ordered after all replayed ops.
        """
        replica_id: str = payload["replica_id"]
        # Entries are stored in insertion order which equals Lamport order
        # because record_write always calls clock.tick() first.
        ops = list(self._write_log)
        if ops:
            self.clock.update(ops[-1].lamport_ts)
        count = len(ops)
        return {
            "service": "replica",
            "action": "sync.replay",
            "status": "ok",
            "detail": (
                f"Replayed {count} operation(s) for {replica_id!r} "
                f"in Lamport order. Clock is now {self.clock.value}."
            ),
            "accepted": True,
            "replica_id": replica_id,
            "replayed_operations": count,
        }
