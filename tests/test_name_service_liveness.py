from unittest.mock import patch

from shared.config import NameServiceSettings
from services.name_service.registry import MembershipRegistry


def test_membership_registry_thresholds_are_config_driven() -> None:
    settings = NameServiceSettings(
        heartbeat_interval_sec=0.1,
        suspect_after_misses=2,
        unhealthy_after_misses=4,
    )
    registry = MembershipRegistry(settings=settings)

    assert registry.heartbeat_interval == 0.1
    assert registry.suspect_after == 0.2
    assert registry.unhealthy_after == 0.4


def test_register_marks_member_healthy_and_healthy_members_filtering() -> None:
    settings = NameServiceSettings(
        heartbeat_interval_sec=0.1,
        suspect_after_misses=2,
        unhealthy_after_misses=4,
    )
    registry = MembershipRegistry(settings=settings)

    with patch("services.name_service.registry.time.monotonic") as monotonic:
        monotonic.return_value = 100.0
        response = registry.register({"replica_id": "replica-a", "host": "a", "port": 8201})

        assert response["registered"] is True
        assert response["member"]["status"] == "healthy"

        monotonic.return_value = 100.19
        healthy_members = registry.list_members(healthy_only=True)
        assert healthy_members["members"][0]["status"] == "healthy"

        monotonic.return_value = 100.21
        members = registry.list_members()
        assert members["members"][0]["status"] == "suspect"

        monotonic.return_value = 100.41
        members = registry.list_members()
        assert members["members"][0]["status"] == "unhealthy"

        monotonic.return_value = 100.42
        heartbeat_response = registry.heartbeat({"replica_id": "replica-a", "status": "healthy"})
        assert heartbeat_response["member"]["status"] == "healthy"
        assert registry.list_members(healthy_only=True)["members"]


def test_heartbeat_resets_status_to_healthy() -> None:
    settings = NameServiceSettings(
        heartbeat_interval_sec=0.1,
        suspect_after_misses=2,
        unhealthy_after_misses=4,
    )
    registry = MembershipRegistry(settings=settings)

    with patch("services.name_service.registry.time.monotonic") as monotonic:
        monotonic.return_value = 100.0
        registry.register({"replica_id": "replica-a", "host": "a", "port": 8201})

        monotonic.return_value = 100.41
        assert registry.list_members()["members"][0]["status"] == "unhealthy"

        monotonic.return_value = 100.42
        registry.heartbeat({"replica_id": "replica-a", "status": "healthy"})
        assert registry.list_members()["members"][0]["status"] == "healthy"
