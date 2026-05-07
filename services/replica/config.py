from shared.config import ReplicaSettings


def get_settings() -> ReplicaSettings:
    """Load replica settings from environment variables."""
    return ReplicaSettings()

