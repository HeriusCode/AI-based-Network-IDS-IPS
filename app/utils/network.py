"""Local IPv4 discovery without invoking shell commands."""

from __future__ import annotations

import ipaddress
import socket


def local_ipv4_addresses() -> list[str]:
    """Return private/local IPv4 addresses, preferring the active default route."""
    candidates: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            candidates.append(probe.getsockname()[0])
    except OSError:
        pass

    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.append(item[4][0])
    except OSError:
        pass

    unique: list[str] = []
    for value in candidates:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if not isinstance(address, ipaddress.IPv4Address):
            continue
        if (address.is_private or address.is_loopback) and value not in unique:
            unique.append(value)

    unique.sort(key=lambda value: ipaddress.ip_address(value).is_loopback)
    return unique or ["127.0.0.1"]


def primary_local_ipv4() -> str:
    return local_ipv4_addresses()[0]
