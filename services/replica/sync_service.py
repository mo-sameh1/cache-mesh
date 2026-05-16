import time


class SyncService:

    def __init__(self):
        self.snapshots = []

    def save_snapshot(self, cache_data):
        snapshot = {
            "timestamp": time.time(),
            "data": cache_data
        }

        self.snapshots.append(snapshot)

        return {
            "status": "snapshot saved",
            "count": len(self.snapshots)
        }

    def replay_snapshots(self):
        return {
            "snapshots": self.snapshots
        }

    def latest_snapshot(self):
        if not self.snapshots:
            return None

        return self.snapshots[-1]