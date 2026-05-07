from shared.config import GatewaySettings, ReplicaSettings


def test_gateway_settings_defaults() -> None:
    settings = GatewaySettings()
    assert settings.gateway_port == 8000
    assert settings.project_name == "CacheMesh"


def test_replica_settings_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("REPLICA_ID", "replica-z")
    monkeypatch.setenv("REPLICA_PORT", "8299")
    settings = ReplicaSettings()
    assert settings.replica_id == "replica-z"
    assert settings.replica_port == 8299
    monkeypatch.delenv("REPLICA_ID", raising=False)
    monkeypatch.delenv("REPLICA_PORT", raising=False)
