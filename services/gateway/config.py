from shared.config import GatewaySettings


def get_settings() -> GatewaySettings:
    """Load gateway settings from environment variables."""
    return GatewaySettings()

