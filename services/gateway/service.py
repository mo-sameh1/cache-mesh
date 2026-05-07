from shared.protocol import placeholder_response


class GatewayService:
    """High-level placeholder for the API gateway workflow."""

    def query_cache(self, payload: dict) -> dict:
        return placeholder_response(
            service="gateway",
            action="cache.query",
            detail="Gateway query flow is scaffolded only. Real routing and read logic is still TODO.",
            received=payload,
        )

    def write_cache(self, payload: dict) -> dict:
        return placeholder_response(
            service="gateway",
            action="cache.write",
            detail="Gateway miss-path write flow is scaffolded only. Real coordinator logic is still TODO.",
            received=payload,
        )

    def arm_fault(self, replica_id: str, payload: dict) -> dict:
        return placeholder_response(
            service="gateway",
            action="admin.faults",
            detail="Gateway fault-injection flow is scaffolded only. Real forwarding to replicas is still TODO.",
            replica_id=replica_id,
            received=payload,
        )

