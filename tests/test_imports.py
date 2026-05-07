def test_shared_imports() -> None:
    import shared.clock  # noqa: F401
    import shared.config  # noqa: F401
    import shared.constants  # noqa: F401
    import shared.faults  # noqa: F401
    import shared.logging  # noqa: F401
    import shared.models  # noqa: F401
    import shared.protocol  # noqa: F401


def test_service_imports() -> None:
    import services.gateway.main  # noqa: F401
    import services.inference_adapter.main  # noqa: F401
    import services.name_service.main  # noqa: F401
    import services.replica.main  # noqa: F401

