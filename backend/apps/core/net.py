"""Network / request helpers shared across apps."""
from __future__ import annotations

from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str | None:
    """Best-effort real client IP extraction.

    Production runs behind exactly one nginx proxy on the same host. Nginx
    sets ``X-Real-IP`` to ``$remote_addr`` (the proxy-connected peer) and
    appends to ``X-Forwarded-For``. A naive ``XFF.split(",")[0]`` is
    spoofable because clients can send any value they like in that header.

    Rules, in priority order:

    1. If ``X-Real-IP`` is set, trust it (Nginx is the only thing in
       front of Gunicorn and it overwrites this header on every request).
    2. Otherwise, take the RIGHTMOST entry of ``X-Forwarded-For``, which
       is the IP that connected to our outermost proxy.
    3. Fall back to ``REMOTE_ADDR``.

    Always returns a stripped string, or ``None`` if nothing is available.
    """
    real_ip = request.META.get("HTTP_X_REAL_IP")
    if real_ip:
        return real_ip.strip()

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]

    remote = request.META.get("REMOTE_ADDR")
    return remote.strip() if remote else None
