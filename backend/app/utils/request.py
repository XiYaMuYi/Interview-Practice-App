"""Request utilities — extract client IP, etc."""

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Extract client IP address from request, checking forwarded headers."""
    # Check X-Forwarded-For first (proxy/load balancer)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Check X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    # Fallback to direct client
    if request.client:
        return request.client.host
    return None
