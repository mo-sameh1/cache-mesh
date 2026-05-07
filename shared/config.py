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
    qdrant_collection: str = "cachemesh_entries"
    inference_adapter_url: str = "http://inference-adapter:8050"


class GatewaySettings(AppSettings):
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000


class NameServiceSettings(AppSettings):
    name_service_host: str = "0.0.0.0"
    name_service_port: int = 8100


class ReplicaSettings(AppSettings):
    replica_id: str = "replica-a"
    replica_host: str = "0.0.0.0"
    replica_port: int = 8201
    qdrant_url: str = "http://qdrant-a:6333"


class InferenceAdapterSettings(AppSettings):
    adapter_host: str = "0.0.0.0"
    adapter_port: int = 8050

