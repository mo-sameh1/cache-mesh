from shared.config import NameServiceSettings


def get_settings() -> NameServiceSettings:
    """Load name-service settings from environment variables."""
    return NameServiceSettings()

