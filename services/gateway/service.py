from services.gateway.clients import InferenceClient, NameServiceClient, ReplicaClient
from services.gateway.config import get_settings
from shared.http_client import ServiceClientError


class GatewayService:
    """Coordinates gateway calls to the other CacheMesh services."""

    def __init__(
        self,
        name_service_client: NameServiceClient | None = None,
        replica_client: ReplicaClient | None = None,
        inference_client: InferenceClient | None = None,
    ) -> None:
        self.settings = get_settings()
        self.name_service_client = name_service_client or NameServiceClient(
            self.settings.name_service_url,
            self.settings.request_timeout_sec,
        )
        self.replica_client = replica_client or ReplicaClient(self.settings.request_timeout_sec)
        self.inference_client = inference_client or InferenceClient(
            self.settings.inference_adapter_url,
            self.settings.request_timeout_sec,
        )

    def query_cache(self, payload: dict) -> dict:
        for replica in self._replica_targets():
            try:
                read_response = self.replica_client.read_cache(replica["url"], self._read_payload(payload))
            except ServiceClientError:
                continue

            if read_response.get("hit"):
                return self._query_response(
                    payload,
                    status="ok",
                    detail="Cache hit returned by replica.",
                    hit=True,
                    response_text=read_response.get("response_text"),
                    selected_replica_id=read_response.get("replica_id") or replica["replica_id"],
                    score=read_response.get("score"),
                    cache_status="hit",
                )

            return self._query_miss(payload, replica)

        return self._query_response(
            payload,
            status="unavailable",
            detail="No usable replica was available for cache query.",
            cache_status="replicas_unavailable",
        )

    def write_cache(self, payload: dict) -> dict:
        for replica in self._replica_targets():
            try:
                response = self.replica_client.write_cache(replica["url"], payload)
                return self._write_response(
                    payload,
                    status="ok",
                    detail="Gateway wrote cache entry through a replica.",
                    stored=bool(response.get("stored")),
                    replica_id=response.get("replica_id") or replica["replica_id"],
                    lamport_ts=response.get("lamport_ts"),
                )
            except ServiceClientError:
                continue

        return self._write_response(
            payload,
            status="unavailable",
            detail="No usable replica was available for cache write.",
        )

    def arm_fault(self, replica_id: str, payload: dict) -> dict:
        replica = self._replica_target_for_id(replica_id)
        if replica is None:
            return self._fault_response(
                replica_id,
                payload,
                detail="Target replica was not found.",
            )

        try:
            response = self.replica_client.arm_fault(replica["url"], payload)
        except ServiceClientError:
            return self._fault_response(
                replica_id,
                payload,
                detail="Target replica was unavailable for fault forwarding.",
            )

        return self._fault_response(
            replica_id,
            response.get("active_fault") or payload,
            status="ok",
            detail="Gateway forwarded fault request to replica.",
            accepted=bool(response.get("accepted")),
        )

    def _fault_response(
        self,
        replica_id: str,
        payload: dict,
        *,
        detail: str,
        status: str = "unavailable",
        accepted: bool = False,
    ) -> dict:
        return {
            "service": "gateway",
            "action": "admin.faults",
            "status": status,
            "detail": detail,
            "accepted": accepted,
            "target_replica_id": replica_id,
            "active_fault": payload,
        }

    def _query_miss(self, payload: dict, replica: dict[str, str]) -> dict:
        try:
            inference_response = self.inference_client.infer(
                {"prompt": payload["prompt"], "model_id": payload["model_id"]}
            )
        except ServiceClientError:
            return self._query_response(
                payload,
                status="unavailable",
                detail="Cache miss occurred, but inference was unavailable.",
                selected_replica_id=replica["replica_id"],
                cache_status="inference_unavailable",
            )

        response_text = inference_response["response_text"]
        write_payload = {
            "prompt": payload["prompt"],
            "response_text": response_text,
            "model_id": payload["model_id"],
        }
        try:
            self.replica_client.write_cache(replica["url"], write_payload)
            cache_status = "miss_generated"
            detail = "Cache miss generated through inference and write was attempted successfully."
        except ServiceClientError:
            cache_status = "miss_generated_write_failed"
            detail = "Cache miss generated through inference, but cache write failed."

        return self._query_response(
            payload,
            status="ok",
            detail=detail,
            response_text=response_text,
            selected_replica_id=replica["replica_id"],
            cache_status=cache_status,
        )

    def _replica_targets(self) -> list[dict[str, str]]:
        member_targets = self._member_replica_targets()
        if member_targets is not None:
            return member_targets
        return self.settings.replica_targets

    def _replica_target_for_id(self, replica_id: str) -> dict[str, str] | None:
        member_targets = self._member_replica_targets(healthy_only=False)
        if member_targets is not None:
            for target in member_targets:
                if target["replica_id"] == replica_id:
                    return target

        for target in self.settings.replica_targets:
            if target["replica_id"] == replica_id:
                return target
        return None

    def _member_replica_targets(self, *, healthy_only: bool = True) -> list[dict[str, str]] | None:
        try:
            response = self.name_service_client.list_members()
        except ServiceClientError:
            return None

        members = response.get("members", [])
        if not members:
            return None

        return [
            {
                "replica_id": member["replica_id"],
                "url": f"http://{member['host']}:{member['port']}",
            }
            for member in members
            if not healthy_only or member.get("status") == "healthy"
        ]

    def _read_payload(self, payload: dict) -> dict:
        return {
            "prompt": payload["prompt"],
            "model_id": payload["model_id"],
            "semantic_enabled": payload["semantic_enabled"],
        }

    def _query_response(
        self,
        payload: dict,
        *,
        status: str,
        detail: str,
        hit: bool = False,
        response_text: str | None = None,
        selected_replica_id: str | None = None,
        score: float | None = None,
        cache_status: str,
    ) -> dict:
        return {
            "service": "gateway",
            "action": "cache.query",
            "status": status,
            "detail": detail,
            "hit": hit,
            "response_text": response_text,
            "model_id": payload["model_id"],
            "selected_replica_id": selected_replica_id,
            "score": score,
            "cache_status": cache_status,
        }

    def _write_response(
        self,
        payload: dict,
        *,
        status: str,
        detail: str,
        stored: bool = False,
        replica_id: str | None = None,
        lamport_ts: int | None = None,
    ) -> dict:
        return {
            "service": "gateway",
            "action": "cache.write",
            "status": status,
            "detail": detail,
            "stored": stored,
            "replica_id": replica_id,
            "model_id": payload["model_id"],
            "lamport_ts": lamport_ts,
        }

