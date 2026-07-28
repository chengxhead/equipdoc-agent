from __future__ import annotations

import socket


def find_available_port(host: str, preferred_port: int, max_attempts: int = 20) -> int:
    """Return the first bindable TCP port, starting with ``preferred_port``."""
    if not 1 <= preferred_port <= 65535:
        raise ValueError("preferred_port must be between 1 and 65535")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    last_port = min(65535, preferred_port + max_attempts - 1)
    for port in range(preferred_port, last_port + 1):
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
        return port

    raise OSError(
        f"No available TCP port in range {preferred_port}-{last_port} on {host}."
    )
