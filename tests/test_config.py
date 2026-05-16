from shared.config import GatewaySettings, ReplicaSettings


def test_gateway_settings_defaults() -> None:
    settings = GatewaySettings()
    assert settings.gateway_port == 8000
    assert settings.project_name == "CacheMesh"
    assert settings.name_service_url == "http://name-service:8100"
    assert settings.replica_urls == [
        "http://replica-a:8201",
        "http://replica-b:8202",
        "http://replica-c:8203",
    ]


def test_gateway_replica_urls_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_URLS", "http://replica-a:8201, http://replica-b:8202,,")
    settings = GatewaySettings()
    assert settings.replica_urls == ["http://replica-a:8201", "http://replica-b:8202"]
    monkeypatch.delenv("GATEWAY_REPLICA_URLS", raising=False)


def test_replica_settings_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("REPLICA_ID", "replica-z")
    monkeypatch.setenv("REPLICA_PORT", "8299")
    settings = ReplicaSettings()
    assert settings.replica_id == "replica-z"
    assert settings.replica_port == 8299
    monkeypatch.delenv("REPLICA_ID", raising=False)
    monkeypatch.delenv("REPLICA_PORT", raising=False)
