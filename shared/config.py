from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "CacheMesh"
    log_level: str = "INFO"
    environment: str = "development"
    request_timeout_sec: float = 2.0
    heartbeat_interval_sec: float = 1.0
    suspect_after_misses: int = 3
    unhealthy_after_misses: int = 5
    fault_mode: str = "disabled"
    fault_duration_sec: int = 10
    name_service_url: str = "http://name-service:8100"
    qdrant_collection: str = "cachemesh_entries"
    inference_adapter_url: str = "http://inference-adapter:8050"


class GatewaySettings(AppSettings):
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    name_service_url: str = "http://name-service:8100"
    gateway_replica_targets: str = (
        "replica-a=http://replica-a:8201,"
        "replica-b=http://replica-b:8202,"
        "replica-c=http://replica-c:8203"
    )
    gateway_replica_urls: str = "http://replica-a:8201,http://replica-b:8202,http://replica-c:8203"

    @property
    def replica_urls(self) -> list[str]:
        return [url.strip() for url in self.gateway_replica_urls.split(",") if url.strip()]

    @property
    def replica_targets(self) -> list[dict[str, str]]:
        targets = []
        for item in self.gateway_replica_targets.split(","):
            if not item.strip():
                continue
            replica_id, url = item.split("=", 1)
            targets.append({"replica_id": replica_id.strip(), "url": url.strip()})

        if targets:
            return targets

        return [{"replica_id": url, "url": url} for url in self.replica_urls]


class NameServiceSettings(AppSettings):
    name_service_host: str = "0.0.0.0"
    name_service_port: int = 8100


class ReplicaSettings(AppSettings):
    replica_id: str = "replica-a"
    replica_host: str = "0.0.0.0"
    replica_port: int = 8201
    replica_advertised_host: str = "replica-a"
    replica_advertised_port: int | None = None
    qdrant_url: str = "http://qdrant-a:6333"
    replica_peer_targets: str = (
        "replica-a=http://replica-a:8201,"
        "replica-b=http://replica-b:8202,"
        "replica-c=http://replica-c:8203"
    )
    semantic_embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_vector_size: int = 384
    semantic_score_threshold: float = 0.72

    @property
    def advertised_port(self) -> int:
        return self.replica_advertised_port or self.replica_port

    @property
    def peer_targets(self) -> list[dict[str, str]]:
        targets = []
        for item in self.replica_peer_targets.split(","):
            if not item.strip():
                continue
            replica_id, url = item.split("=", 1)
            targets.append({"replica_id": replica_id.strip(), "url": url.strip()})
        return targets


class InferenceAdapterSettings(AppSettings):
    adapter_host: str = "0.0.0.0"
    adapter_port: int = 8050

