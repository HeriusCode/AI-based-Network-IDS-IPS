"""Safety validation for destinations and traffic parameters."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

from app.models.traffic_config import TrafficConfig
from app.utils.constants import MAX_PORT, MIN_PORT


class ValidationError(ValueError):
    """Raised when traffic configuration violates a safety rule."""


def parse_ip(value: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise ValidationError("Địa chỉ IP đích không hợp lệ") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValidationError("Phiên bản hiện tại chỉ hỗ trợ IPv4")
    return address


def validate_lab_target(address: str, allowed_networks: Iterable[str]) -> ipaddress.IPv4Address:
    target = parse_ip(address)
    networks = []
    for value in allowed_networks:
        try:
            networks.append(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError as exc:
            raise ValidationError(f"Mạng lab cấu hình không hợp lệ: {value}") from exc
    if not networks:
        raise ValidationError("Chưa cấu hình mạng lab được phép")
    if not any(target in network for network in networks):
        raise ValidationError("IP đích nằm ngoài danh sách mạng lab được phép")
    return target


def validate_port(port: int, approved_ports: Iterable[int], protocol: str) -> None:
    if protocol.upper() == "ICMP":
        return
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValidationError("Cổng đích phải nằm trong khoảng 1–65535")
    approved = {int(item) for item in approved_ports}
    if port not in approved:
        raise ValidationError("Cổng đích chưa nằm trong danh sách được phê duyệt")


def validate_traffic_config(
    config: TrafficConfig,
    allowed_networks: Iterable[str],
    approved_ports: Iterable[int],
) -> TrafficConfig:
    config.normalized()
    errors = config.validate_ranges()
    if errors:
        raise ValidationError("; ".join(errors))
    validate_lab_target(config.destination_ip, allowed_networks)
    validate_port(config.destination_port, approved_ports, config.protocol)
    return config
