"""Capture packets on one Mininet host veth and emit approximate CIC flow rows.

No synthetic feature values are inferred from the generator's send counters.
The live model still has a domain shift: this lightweight extractor is not
CICFlowMeter, so its predictions are demonstration results, not calibrated IDS.
"""

from __future__ import annotations

import argparse
import json
import select
import signal
import socket
import statistics
import struct
import threading
import time
from datetime import datetime, timezone


STOP = threading.Event()


def _stop(_signum: int, _frame: object) -> None:
    STOP.set()


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def _stats(values: list[float]) -> tuple[float, float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    return min(values), max(values), statistics.mean(values), statistics.pstdev(values)


def parse_packet(frame: bytes, timestamp: float) -> dict | None:
    if len(frame) < 34 or frame[12:14] != b"\x08\x00":
        return None
    ip = frame[14:]
    if ip[0] >> 4 != 4:
        return None
    ihl = (ip[0] & 15) * 4
    if ihl < 20 or len(ip) < ihl + 8:
        return None
    total = min(len(ip), struct.unpack_from("!H", ip, 2)[0])
    proto = ip[9]
    if proto not in (1, 6, 17):
        return None
    source = socket.inet_ntoa(ip[12:16])
    target = socket.inet_ntoa(ip[16:20])
    transport = ip[ihl:total]
    source_port = target_port = flags = window = segment = 0
    header = ihl
    if proto == 6:
        if len(transport) < 20:
            return None
        source_port, target_port = struct.unpack_from("!HH", transport)
        segment = (transport[12] >> 4) * 4
        if segment < 20 or segment > len(transport):
            return None
        flags = transport[13]
        window = struct.unpack_from("!H", transport, 14)[0]
        header += segment
    elif proto == 17:
        if len(transport) < 8:
            return None
        source_port, target_port = struct.unpack_from("!HH", transport)
        header += 8
    else:
        header += 8
    return {
        "time": timestamp, "source": source, "target": target, "protocol": proto,
        "source_port": source_port, "target_port": target_port,
        "length": max(0, total - header), "header": header,
        "flags": flags, "window": window, "segment": segment,
    }


class Flow:
    def __init__(self, packet: dict, source_ip: str, target_ip: str, session_id: str) -> None:
        forward = packet["source"] == source_ip
        self.source_ip = source_ip
        self.target_ip = target_ip
        self.source_port = packet["source_port"] if forward else packet["target_port"]
        self.target_port = packet["target_port"] if forward else packet["source_port"]
        self.protocol = packet["protocol"]
        self.session_id = session_id
        self.forward: list[dict] = []
        self.backward: list[dict] = []
        self.first = packet["time"]
        self.last = packet["time"]
        self.changed = False
        self.add(packet)

    @property
    def flow_id(self) -> str:
        return f"{self.source_ip}:{self.source_port}>{self.target_ip}:{self.target_port}/{self.protocol}"

    def add(self, packet: dict) -> None:
        self.last = packet["time"]
        (self.forward if packet["source"] == self.source_ip else self.backward).append(packet)
        self.changed = True

    def record(self) -> dict:
        fwd, bwd = self.forward, self.backward
        all_packets = sorted(fwd + bwd, key=lambda item: item["time"])
        fwd_len = [float(item["length"]) for item in fwd]
        bwd_len = [float(item["length"]) for item in bwd]
        lengths = fwd_len + bwd_len
        fmin, fmax, fmean, fstd = _stats(fwd_len)
        bmin, bmax, bmean, bstd = _stats(bwd_len)
        pmin, pmax, pmean, pstd = _stats(lengths)
        delta = max(1e-6, self.last - self.first)
        duration = delta * 1_000_000

        def gaps(packets: list[dict]) -> list[float]:
            return [(b["time"] - a["time"]) * 1_000_000 for a, b in zip(packets, packets[1:])]

        all_gaps, fwd_gaps, bwd_gaps = gaps(all_packets), gaps(fwd), gaps(bwd)
        imin, imax, imean, istd = _stats(all_gaps)
        fimin, fimax, fimean, fistd = _stats(fwd_gaps)
        bimin, bimax, bimean, bistd = _stats(bwd_gaps)
        flag_count = {bit: sum(bool(item["flags"] & bit) for item in all_packets) for bit in (1, 2, 4, 8, 16, 32, 64, 128)}
        idle = [gap for gap in all_gaps if gap > 1_000_000]
        active: list[float] = []
        if all_packets:
            burst_start = all_packets[0]["time"]
            previous = burst_start
            for item in all_packets[1:]:
                if (item["time"] - previous) > 1:
                    active.append((previous - burst_start) * 1_000_000)
                    burst_start = item["time"]
                previous = item["time"]
            active.append((previous - burst_start) * 1_000_000)
        amin, amax, amean, astd = _stats(active)
        dmin, dmax, dmean, dstd = _stats(idle)
        first_fwd_win = fwd[0]["window"] if fwd and self.protocol == 6 else -1
        first_bwd_win = bwd[0]["window"] if bwd and self.protocol == 6 else -1
        features = {
            "Protocol": self.protocol, "Flow Duration": duration,
            "Total Fwd Packets": len(fwd), "Total Backward Packets": len(bwd),
            "Fwd Packets Length Total": sum(fwd_len), "Bwd Packets Length Total": sum(bwd_len),
            "Fwd Packet Length Max": fmax, "Fwd Packet Length Min": fmin,
            "Fwd Packet Length Mean": fmean, "Fwd Packet Length Std": fstd,
            "Bwd Packet Length Max": bmax, "Bwd Packet Length Min": bmin,
            "Bwd Packet Length Mean": bmean, "Bwd Packet Length Std": bstd,
            "Flow Bytes/s": sum(lengths) / delta,
            "Flow Packets/s": len(all_packets) / delta,
            "Flow IAT Mean": imean, "Flow IAT Std": istd,
            "Flow IAT Max": imax, "Flow IAT Min": imin,
            "Fwd IAT Total": sum(fwd_gaps), "Fwd IAT Mean": fimean,
            "Fwd IAT Std": fistd, "Fwd IAT Max": fimax, "Fwd IAT Min": fimin,
            "Bwd IAT Total": sum(bwd_gaps), "Bwd IAT Mean": bimean,
            "Bwd IAT Std": bistd, "Bwd IAT Max": bimax, "Bwd IAT Min": bimin,
            "Fwd PSH Flags": sum(bool(item["flags"] & 8) for item in fwd),
            "Bwd PSH Flags": sum(bool(item["flags"] & 8) for item in bwd),
            "Fwd URG Flags": sum(bool(item["flags"] & 32) for item in fwd),
            "Bwd URG Flags": sum(bool(item["flags"] & 32) for item in bwd),
            "Fwd Header Length": sum(item["header"] for item in fwd),
            "Bwd Header Length": sum(item["header"] for item in bwd),
            "Fwd Packets/s": len(fwd) / delta, "Bwd Packets/s": len(bwd) / delta,
            "Packet Length Min": pmin, "Packet Length Max": pmax,
            "Packet Length Mean": pmean, "Packet Length Std": pstd,
            "Packet Length Variance": pstd * pstd,
            "FIN Flag Count": flag_count[1], "SYN Flag Count": flag_count[2],
            "RST Flag Count": flag_count[4], "PSH Flag Count": flag_count[8],
            "ACK Flag Count": flag_count[16], "URG Flag Count": flag_count[32],
            "CWE Flag Count": flag_count[128], "ECE Flag Count": flag_count[64],
            "Down/Up Ratio": len(bwd) / max(1, len(fwd)),
            "Avg Packet Size": pmean, "Avg Fwd Segment Size": fmean,
            "Avg Bwd Segment Size": bmean,
            "Fwd Avg Bytes/Bulk": 0, "Fwd Avg Packets/Bulk": 0, "Fwd Avg Bulk Rate": 0,
            "Bwd Avg Bytes/Bulk": 0, "Bwd Avg Packets/Bulk": 0, "Bwd Avg Bulk Rate": 0,
            "Subflow Fwd Packets": len(fwd), "Subflow Fwd Bytes": sum(fwd_len),
            "Subflow Bwd Packets": len(bwd), "Subflow Bwd Bytes": sum(bwd_len),
            "Init Fwd Win Bytes": first_fwd_win, "Init Bwd Win Bytes": first_bwd_win,
            "Fwd Act Data Packets": sum(item["length"] > 0 for item in fwd),
            "Fwd Seg Size Min": min((item["segment"] for item in fwd), default=0),
            "Active Mean": amean, "Active Std": astd, "Active Max": amax, "Active Min": amin,
            "Idle Mean": dmean, "Idle Std": dstd, "Idle Max": dmax, "Idle Min": dmin,
        }
        return {
            "source": "mininet-packet-capture", "session_id": self.session_id,
            "flow_id": self.flow_id,
            "timestamp": datetime.fromtimestamp(self.first, timezone.utc).isoformat(),
            "source_ip": self.source_ip, "destination_ip": self.target_ip,
            "source_port": self.source_port, "destination_port": self.target_port,
            "protocol": {1: "ICMP", 6: "TCP", 17: "UDP"}[self.protocol],
            "packets": len(all_packets), "feature_quality": "approximate",
            "features": features,
        }


def capture(args: argparse.Namespace) -> None:
    protocol = {"ICMP": 1, "TCP": 6, "UDP": 17}[args.protocol]
    ports = {int(port) for port in args.ports.split(",") if port}
    if not ports:
        raise ValueError("Capture cần ít nhất một port")
    flows: dict[str, Flow] = {}
    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as raw:
        raw.bind((args.interface, 0))
        raw.setblocking(False)
        print(json.dumps({"event": "ready"}), flush=True)
        last_emit = time.monotonic()
        while not STOP.is_set():
            readable, _, _ = select.select([raw], [], [], 0.2)
            if readable:
                packet = parse_packet(raw.recv(65535), time.time())
                if packet is not None and packet["protocol"] == protocol:
                    forward = packet["source"] == args.source_ip and packet["target"] == args.target_ip
                    backward = packet["source"] == args.target_ip and packet["target"] == args.source_ip
                    port_ok = protocol == 1 or (
                        forward and packet["target_port"] in ports
                    ) or (backward and packet["source_port"] in ports)
                    if (forward or backward) and port_ok:
                        source_port = packet["source_port"] if forward else packet["target_port"]
                        target_port = packet["target_port"] if forward else packet["source_port"]
                        key = f"{source_port}/{target_port}/{protocol}"
                        if key not in flows:
                            if len(flows) >= 500:
                                oldest = flows.pop(next(iter(flows)))
                                if oldest.changed:
                                    print(json.dumps({"event": "flow", "flow": oldest.record()}), flush=True)
                            flows[key] = Flow(packet, args.source_ip, args.target_ip, args.session_id)
                        else:
                            flows[key].add(packet)
            if time.monotonic() - last_emit >= 2:
                for flow in flows.values():
                    if flow.changed:
                        print(json.dumps({"event": "flow", "flow": flow.record()}), flush=True)
                        flow.changed = False
                last_emit = time.monotonic()
        for flow in flows.values():
            if flow.changed:
                print(json.dumps({"event": "flow", "flow": flow.record()}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", required=True)
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--target-ip", required=True)
    parser.add_argument("--protocol", choices=("TCP", "UDP", "ICMP"), required=True)
    parser.add_argument("--ports", required=True)
    parser.add_argument("--session-id", required=True)
    capture(parser.parse_args())
