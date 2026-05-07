from shared.config import InferenceAdapterSettings


def get_settings() -> InferenceAdapterSettings:
    """Load inference-adapter settings from environment variables."""
    return InferenceAdapterSettings()

