class GatewayService:
    """High-level placeholder for the API gateway workflow."""

    def query_cache(self, payload: dict) -> dict:
        return {
            "service": "gateway",
            "action": "cache.query",
            "status": "placeholder",
            "detail": "Gateway query flow is scaffolded. Real replica routing is still TODO.",
            "hit": False,
            "response_text": None,
            "model_id": payload["model_id"],
            "selected_replica_id": None,
            "score": None,
            "cache_status": "not_checked",
        }

    def write_cache(self, payload: dict) -> dict:
        return {
            "service": "gateway",
            "action": "cache.write",
            "status": "placeholder",
            "detail": "Gateway write flow is scaffolded. Real fan-out or coordinator logic is still TODO.",
            "stored": False,
            "replica_id": None,
            "model_id": payload["model_id"],
            "lamport_ts": None,
        }

    def arm_fault(self, replica_id: str, payload: dict) -> dict:
        return {
            "service": "gateway",
            "action": "admin.faults",
            "status": "placeholder",
            "detail": "Gateway fault forwarding is scaffolded. Real replica call is still TODO.",
            "accepted": False,
            "target_replica_id": replica_id,
            "active_fault": payload,
        }

