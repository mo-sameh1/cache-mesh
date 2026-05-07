from shared.protocol import placeholder_response


class SyncService:
    """Placeholder for snapshot transfer and log replay."""

    def snapshot(self, payload: dict) -> dict:
        return placeholder_response(
            service="replica",
            action="sync.snapshot",
            detail="Snapshot transfer is scaffolded only. Real state serialization is still TODO.",
            received=payload,
        )

    def replay(self, payload: dict) -> dict:
        return placeholder_response(
            service="replica",
            action="sync.replay",
            detail="Log replay is scaffolded only. Real Lamport-ordered recovery is still TODO.",
            received=payload,
        )

