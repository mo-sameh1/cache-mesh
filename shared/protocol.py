def placeholder_response(service: str, action: str, detail: str, **payload: object) -> dict:
    """Create a predictable placeholder payload for scaffold endpoints."""
    response = {
        "service": service,
        "action": action,
        "status": "placeholder",
        "detail": detail,
    }
    response.update(payload)
    return response

