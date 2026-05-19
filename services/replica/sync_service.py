class SyncService:
    """Placeholder for snapshot transfer and log replay."""

    def snapshot(self, payload: dict) -> dict:
        return {
            "service": "replica",
            "action": "sync.snapshot",
            "status": "placeholder",
            "detail": "Snapshot transfer is scaffolded. Real state serialization is still TODO.",
            "accepted": False,
            "replica_id": payload["replica_id"],
            "since_lamport_ts": payload.get("since_lamport_ts"),
            "snapshot_id": None,
        }

    def replay(self, payload: dict) -> dict:
        return {
            "service": "replica",
            "action": "sync.replay",
            "status": "placeholder",
            "detail": "Log replay is scaffolded. Real Lamport-ordered recovery is still TODO.",
            "accepted": False,
            "replica_id": payload["replica_id"],
            "replayed_operations": 0,
        }
