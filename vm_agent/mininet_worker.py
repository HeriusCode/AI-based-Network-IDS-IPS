"""Bounded traffic sender and receiver executed inside Mininet host namespaces.

The agent starts this script with mnexec.  It never accepts shell commands or
arbitrary destination addresses from the desktop UI.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor


STOP = threading.Event()


def _stop(_signum: int, _frame: object) -> None:
    STOP.set()


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def emit(event: str, **values: object) -> None:
    print(json.dumps({"event": event, **values}), flush=True)


def receiver(protocol: str, port: int) -> None:
    kind = socket.SOCK_STREAM if protocol == "TCP" else socket.SOCK_DGRAM
    received_bytes = 0
    received_messages = 0
    with socket.socket(socket.AF_INET, kind) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", port))
        listener.settimeout(0.2)
        if protocol == "TCP":
            listener.listen(64)
        emit("ready")
        while not STOP.is_set():
            try:
                if protocol == "UDP":
                    data, _ = listener.recvfrom(65535)
                    received_bytes += len(data)
                    received_messages += 1
                    continue
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            with connection:
                connection.settimeout(0.2)
                while not STOP.is_set():
                    try:
                        data = connection.recv(65535)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    received_bytes += len(data)
                    received_messages += 1
    emit("receiver_stopped", received_bytes=received_bytes, received_messages=received_messages)


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def icmp_packet(size: int, sequence: int) -> bytes:
    payload = os.urandom(size - 8)
    header = struct.pack("!BBHHH", 8, 0, 0, os.getpid() & 0xFFFF, sequence & 0xFFFF)
    return struct.pack(
        "!BBHHH", 8, 0, checksum(header + payload), os.getpid() & 0xFFFF, sequence & 0xFFFF
    ) + payload


def tcp_syn_packet(source_ip: str, target_ip: str, source_port: int, target_port: int, sequence: int) -> bytes:
    """One real-source SYN with valid IPv4/TCP checksums; no spoofed address."""
    source = socket.inet_aton(source_ip)
    target = socket.inet_aton(target_ip)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, sequence & 0xFFFF,
                     0, 64, 6, 0, source, target)
    ip = ip[:10] + struct.pack("!H", checksum(ip)) + ip[12:]
    tcp = struct.pack("!HHLLBBHHH", source_port, target_port, sequence & 0xFFFFFFFF,
                      0, 5 << 4, 0x02, 64240, 0, 0)
    pseudo = source + target + struct.pack("!BBH", 0, 6, len(tcp))
    tcp = tcp[:16] + struct.pack("!H", checksum(pseudo + tcp)) + tcp[18:]
    return ip + tcp


def burst_rate(base: int, elapsed: float, duration: int) -> int:
    progress = min(1.0, elapsed / duration)
    if progress < 0.25:
        factor = 0.5 + progress * 2
    elif progress < 0.75:
        factor = 2.0
    else:
        factor = max(0.5, 2.0 - (progress - 0.75) * 6)
    return max(1, min(1000, int(base * factor)))


def sender(args: argparse.Namespace) -> None:
    started = time.monotonic()
    last_sample = started
    last_packets = 0
    last_bytes = 0
    packets = 0
    bytes_sent = 0
    successful = 0
    failed = 0
    payload = os.urandom(args.packet_size)

    def snapshot() -> dict[str, float | int]:
        nonlocal last_sample, last_packets, last_bytes
        now = time.monotonic()
        delta = max(0.001, now - last_sample)
        result: dict[str, float | int] = {
            "total_packets": packets,
            "total_bytes": bytes_sent,
            "packets_per_second": (packets - last_packets) / delta,
            "bytes_per_second": (bytes_sent - last_bytes) / delta,
            "successful_connections": successful,
            "failed_connections": failed,
            "elapsed_seconds": now - started,
        }
        last_sample, last_packets, last_bytes = now, packets, bytes_sent
        return result

    if args.scenario == "PORT_SCAN":
        ports = [int(port) for port in args.ports.split(",") if port]
        next_send = started
        while not STOP.is_set() and time.monotonic() - started < args.duration:
            now = time.monotonic()
            if now < next_send:
                STOP.wait(min(0.02, next_send - now))
                continue
            port = ports[packets % len(ports)]
            try:
                with socket.create_connection((args.target_ip, port), timeout=0.2):
                    successful += 1
            except OSError:
                failed += 1
            packets += 1
            bytes_sent += 40  # one TCP SYN attempt, excluding any retransmission
            next_send = max(next_send + 1 / args.packet_rate, time.monotonic())
            if time.monotonic() - last_sample >= 0.25:
                emit("stats", stats=snapshot())
    elif args.scenario in {"BRUTE_FORCE", "WEB_ATTACK", "BOTNET"}:
        def application_payload(sequence: int) -> bytes:
            if args.scenario == "BRUTE_FORCE":
                base = f"USER admin\r\nPASS lab-{sequence:04d}\r\n".encode()
            elif args.scenario == "WEB_ATTACK":
                probes = (
                    "/login?user=admin%27%20OR%201%3D1--",
                    "/search?q=%3Cscript%3Ealert(1)%3C/script%3E",
                )
                base = (
                    f"GET {probes[sequence % len(probes)]} HTTP/1.1\r\n"
                    f"Host: mininet-lab\r\nConnection: close\r\n\r\n"
                ).encode()
            else:
                base = json.dumps(
                    {"agent": "mininet-lab", "sequence": sequence, "event": "heartbeat"}
                ).encode() + b"\n"
            requested = max(len(base), args.packet_size)
            return (base + b"." * requested)[:requested]

        next_send = started
        while not STOP.is_set() and time.monotonic() - started < args.duration:
            now = time.monotonic()
            if now < next_send:
                STOP.wait(min(0.02, next_send - now))
                continue
            body = application_payload(packets)
            try:
                with socket.create_connection((args.target_ip, args.port), timeout=0.5) as conn:
                    conn.sendall(body)
                successful += 1
                packets += 1
                bytes_sent += len(body)
            except OSError:
                failed += 1
            interval = 1 / args.packet_rate
            if args.scenario == "BOTNET":
                interval = max(interval, 0.25)
            next_send = max(next_send + interval, time.monotonic())
            if time.monotonic() - last_sample >= 0.25:
                emit("stats", stats=snapshot())
    elif args.scenario == "CONNECTION_BURST":
        def connect_once() -> bool:
            try:
                with socket.create_connection((args.target_ip, args.port), timeout=0.5) as conn:
                    conn.sendall(payload)
                return True
            except OSError:
                return False

        next_batch = started
        with ThreadPoolExecutor(max_workers=args.connections) as pool:
            while not STOP.is_set() and time.monotonic() - started < args.duration:
                now = time.monotonic()
                if now < next_batch:
                    STOP.wait(min(0.05, next_batch - now))
                    continue
                for success in pool.map(lambda _index: connect_once(), range(args.connections)):
                    successful += int(success)
                    failed += int(not success)
                    if success:
                        packets += 1
                        bytes_sent += len(payload)
                emit("stats", stats=snapshot())
                next_batch = time.monotonic() + 1
    else:
        transport: socket.socket | None = None
        next_send = started
        try:
            if args.scenario == "SYN_FLOOD":
                transport = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
                transport.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            elif args.protocol == "UDP":
                transport = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            elif args.protocol == "ICMP":
                transport = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            while not STOP.is_set() and time.monotonic() - started < args.duration:
                now = time.monotonic()
                if now < next_send:
                    STOP.wait(min(0.02, next_send - now))
                    continue
                elapsed = now - started
                rate = (
                    burst_rate(args.packet_rate, elapsed, args.duration)
                    if args.scenario in {"UDP_FLOOD", "ICMP_FLOOD"} else args.packet_rate
                )
                try:
                    if args.scenario == "SYN_FLOOD":
                        assert transport is not None
                        packet = tcp_syn_packet(
                            args.source_ip, args.target_ip, 40000 + packets % 16,
                            args.port, packets * 104729 + os.getpid(),
                        )
                        sent = transport.sendto(packet, (args.target_ip, args.port))
                    elif args.protocol == "TCP":
                        if transport is None:
                            transport = socket.create_connection((args.target_ip, args.port), timeout=0.5)
                            transport.settimeout(0.5)
                            successful += 1
                        transport.sendall(payload)
                        sent = len(payload)
                    elif args.protocol == "UDP":
                        assert transport is not None
                        sent = transport.sendto(payload, (args.target_ip, args.port))
                    else:
                        assert transport is not None
                        sent = transport.sendto(icmp_packet(args.packet_size, packets), (args.target_ip, 0))
                    packets += 1
                    bytes_sent += sent
                except OSError:
                    failed += 1
                    if args.protocol == "TCP" and transport is not None:
                        transport.close()
                        transport = None
                    STOP.wait(0.05)
                next_send = max(next_send + 1 / rate, time.monotonic())
                if time.monotonic() - last_sample >= 0.25:
                    emit("stats", stats=snapshot())
        finally:
            if transport is not None:
                transport.close()
    emit("finished", status="Stopped" if STOP.is_set() else "Completed", stats=snapshot())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("send", "receive"))
    parser.add_argument("--protocol", choices=("TCP", "UDP", "ICMP"), required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--target-ip", default="")
    parser.add_argument("--scenario", choices=(
        "NORMAL", "SYN_FLOOD", "UDP_FLOOD", "ICMP_FLOOD", "PORT_SCAN", "CONNECTION_BURST",
        "BRUTE_FORCE", "WEB_ATTACK", "BOTNET"
    ), default="NORMAL")
    parser.add_argument("--source-ip", default="")
    parser.add_argument("--ports", default="")
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--packet-rate", type=int, default=10)
    parser.add_argument("--packet-size", type=int, default=64)
    parser.add_argument("--connections", type=int, default=1)
    args = parser.parse_args()
    if args.mode == "receive":
        receiver(args.protocol, args.port)
    else:
        sender(args)


if __name__ == "__main__":
    main()
