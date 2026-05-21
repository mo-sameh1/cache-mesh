from shared.config import GatewaySettings, InferenceAdapterSettings, ReplicaSettings


def test_gateway_settings_defaults() -> None:
    settings = GatewaySettings()
    assert settings.gateway_port == 8000
    assert settings.project_name == "CacheMesh"
    assert settings.name_service_url == "http://name-service:8100"
    assert settings.inference_request_timeout_sec == 180.0
    assert settings.replica_urls == [
        "http://replica-a:8201",
        "http://replica-b:8202",
        "http://replica-c:8203",
    ]
    assert settings.replica_targets == [
        {"replica_id": "replica-a", "url": "http://replica-a:8201"},
        {"replica_id": "replica-b", "url": "http://replica-b:8202"},
        {"replica_id": "replica-c", "url": "http://replica-c:8203"},
    ]


def test_gateway_replica_urls_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_URLS", "http://replica-a:8201, http://replica-b:8202,,")
    settings = GatewaySettings()
    assert settings.replica_urls == ["http://replica-a:8201", "http://replica-b:8202"]
    monkeypatch.delenv("GATEWAY_REPLICA_URLS", raising=False)


def test_gateway_replica_targets_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "GATEWAY_REPLICA_TARGETS",
        "replica-a=http://192.168.1.10:8201, replica-b=http://192.168.1.11:8202",
    )
    settings = GatewaySettings()
    assert settings.replica_targets == [
        {"replica_id": "replica-a", "url": "http://192.168.1.10:8201"},
        {"replica_id": "replica-b", "url": "http://192.168.1.11:8202"},
    ]
    monkeypatch.delenv("GATEWAY_REPLICA_TARGETS", raising=False)


def test_replica_settings_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("REPLICA_ID", "replica-z")
    monkeypatch.setenv("REPLICA_PORT", "8299")
    monkeypatch.setenv("REPLICA_ADVERTISED_HOST", "replica-z.local")
    monkeypatch.setenv("REPLICA_ADVERTISED_PORT", "8399")
    monkeypatch.setenv("REPLICA_PEER_TARGETS", "replica-z=http://replica-z:8299, replica-y=http://replica-y:8298")
    monkeypatch.setenv("INITIAL_TOKEN_REPLICA_ID", "replica-y")
    settings = ReplicaSettings()
    assert settings.replica_id == "replica-z"
    assert settings.replica_port == 8299
    assert settings.replica_advertised_host == "replica-z.local"
    assert settings.advertised_port == 8399
    assert settings.semantic_embedding_model_id == "sentence-transformers/all-MiniLM-L12-v2"
    assert settings.semantic_embedding_device == "auto"
    assert settings.semantic_vector_size == 384
    assert settings.initial_token_replica_id == "replica-y"
    assert settings.peer_targets == [
        {"replica_id": "replica-z", "url": "http://replica-z:8299"},
        {"replica_id": "replica-y", "url": "http://replica-y:8298"},
    ]
    monkeypatch.delenv("REPLICA_ID", raising=False)
    monkeypatch.delenv("REPLICA_PORT", raising=False)
    monkeypatch.delenv("REPLICA_ADVERTISED_HOST", raising=False)
    monkeypatch.delenv("REPLICA_ADVERTISED_PORT", raising=False)
    monkeypatch.delenv("REPLICA_PEER_TARGETS", raising=False)
    monkeypatch.delenv("INITIAL_TOKEN_REPLICA_ID", raising=False)


def test_inference_settings_defaults() -> None:
    settings = InferenceAdapterSettings()
    assert settings.inference_backend == "stub"
    assert settings.inference_model_id == "Qwen/Qwen2.5-7B-Instruct"
    assert settings.inference_load_in_4bit is True
