"""Collect labelled flow snapshots and rate telemetry from the Mininet lab.

The collector intentionally uses the same VM agent and packet feature extractor
as the desktop demo.  Each run is a separate group so model evaluation can hold
out whole sessions instead of leaking snapshots from one flow across splits.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


SCENARIOS: tuple[str, ...] = (
    "NORMAL",
    "SYN_FLOOD",
    "UDP_FLOOD",
    "ICMP_FLOOD",
    "PORT_SCAN",
    "CONNECTION_BURST",
    "BRUTE_FORCE",
    "WEB_ATTACK",
    "BOTNET",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-project", type=Path, default=Path(r"D:\Traffic Generator"))
    parser.add_argument("--host", default="192.168.201.129")
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--runs", type=int, default=8, help="Số session cho mỗi scenario.")
    parser.add_argument("--run-offset", type=int, default=0)
    parser.add_argument("--scenarios", nargs="*", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--output", type=Path, default=Path("data/mininet/lab_flows.jsonl"))
    parser.add_argument("--series", type=Path, default=Path("data/mininet/lab_series.csv"))
    return parser.parse_args()


def scenario_payload(scenario: str, run: int, duration: int) -> dict[str, Any]:
    source = "h1" if run % 2 == 0 else "h2"
    common: dict[str, Any] = {
        "source": source,
        "target": "h3",
        "scenario": scenario,
        "duration": duration,
        "destination_port": 8080,
        "scan_ports": [],
        "number_connections": 1,
    }
    if scenario == "NORMAL":
        protocols = ("TCP", "UDP", "ICMP")
        protocol = protocols[run % len(protocols)]
        common.update(
            protocol=protocol,
            packet_rate=(8, 12, 20, 30)[run % 4],
            packet_size=(64, 128, 256, 512)[run % 4],
        )
    elif scenario == "SYN_FLOOD":
        common.update(protocol="TCP", packet_rate=(50, 80, 120, 160)[run % 4], packet_size=40)
    elif scenario == "UDP_FLOOD":
        common.update(
            protocol="UDP",
            packet_rate=(100, 150, 220, 300)[run % 4],
            packet_size=(128, 256, 512, 1024)[run % 4],
        )
    elif scenario == "ICMP_FLOOD":
        common.update(
            protocol="ICMP",
            packet_rate=(50, 80, 120, 160)[run % 4],
            packet_size=(64, 96, 128, 256)[run % 4],
        )
    elif scenario == "PORT_SCAN":
        common.update(
            protocol="TCP",
            packet_rate=(4, 6, 8, 10)[run % 4],
            packet_size=40,
            scan_ports=[22, 53, 80, 443, 8000, 8080],
        )
    elif scenario == "CONNECTION_BURST":
        common.update(
            protocol="TCP",
            packet_rate=1,
            packet_size=64,
            number_connections=(3, 5, 8, 10)[run % 4],
        )
    elif scenario == "BRUTE_FORCE":
        common.update(
            protocol="TCP", destination_port=22,
            packet_rate=(8, 12, 16, 20)[run % 4],
            packet_size=(64, 96, 128, 192)[run % 4],
        )
    elif scenario == "WEB_ATTACK":
        common.update(
            protocol="TCP", destination_port=8080,
            packet_rate=(6, 10, 14, 18)[run % 4],
            packet_size=(160, 256, 384, 512)[run % 4],
        )
    elif scenario == "BOTNET":
        common.update(
            protocol="TCP", destination_port=8000,
            packet_rate=(2, 3, 4, 5)[run % 4],
            packet_size=(96, 128, 160, 192)[run % 4],
        )
    else:  # pragma: no cover - guarded by SCENARIOS
        raise ValueError(f"Scenario không hỗ trợ: {scenario}")
    return common


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def append_series(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def collect_session(client: Any, payload: dict[str, Any], poll_seconds: float) -> tuple[list[dict], list[dict]]:
    started = client.start(payload)
    session_id = str(started["session_id"])
    sequence = 0
    flow_rows: list[dict[str, Any]] = []
    series_rows: list[dict[str, Any]] = []
    terminal_seen = False
    while True:
        status = client.status()
        if str(status.get("session_id")) != session_id:
            raise RuntimeError("Mininet agent đã thay session trong lúc thu dữ liệu")
        stats = status.get("stats") or {}
        series_rows.append(
            {
                "session_id": session_id,
                "scenario": payload["scenario"],
                "protocol": payload["protocol"],
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": float(stats.get("elapsed_seconds", 0.0)),
                "packets_per_second": float(stats.get("packets_per_second", 0.0)),
                "bytes_per_second": float(stats.get("bytes_per_second", 0.0)),
                "total_packets": int(stats.get("total_packets", 0)),
                "total_bytes": int(stats.get("total_bytes", 0)),
            }
        )
        captured = client.flows(sequence)
        for item in captured.get("flows", []):
            sequence = max(sequence, int(item["sequence"]))
            flow = item.get("flow")
            if not isinstance(flow, dict):
                continue
            flow_rows.append(
                {
                    "scenario": payload["scenario"],
                    "binary_label": "BENIGN" if payload["scenario"] == "NORMAL" else "ATTACK",
                    "session_id": session_id,
                    "sequence": int(item["sequence"]),
                    "parameters": payload,
                    "flow": flow,
                }
            )
        state = str(status.get("status", "Error"))
        if state in {"Completed", "Stopped", "Error"}:
            if state == "Error":
                raise RuntimeError(str(status.get("error_message") or "Mininet session lỗi"))
            if terminal_seen:
                break
            terminal_seen = True
        time.sleep(poll_seconds if not terminal_seen else 0.35)
    return flow_rows, series_rows


def main() -> None:
    args = parse_args()
    traffic_project = args.traffic_project.resolve()
    if not (traffic_project / "app" / "services" / "mininet_client.py").exists():
        raise FileNotFoundError(f"Không tìm thấy Traffic Generator tại {traffic_project}")
    sys.path.insert(0, str(traffic_project))
    from app.services.mininet_client import MininetClient

    # A fresh collection avoids silently mixing incompatible extractor versions.
    if not args.append:
        for path in (args.output, args.series):
            if path.exists():
                path.unlink()

    total_sessions = args.runs * len(args.scenarios)
    completed = 0
    with MininetClient(args.host, args.user, args.port) as client:
        print(f"VM health: {client.health()}", flush=True)
        for run in range(args.run_offset, args.run_offset + args.runs):
            for scenario in args.scenarios:
                payload = scenario_payload(scenario, run, args.duration)
                print(
                    f"[{completed + 1}/{total_sessions}] {scenario} "
                    f"{payload['protocol']} rate={payload['packet_rate']}",
                    flush=True,
                )
                flows, series = collect_session(client, payload, args.poll_seconds)
                append_jsonl(args.output, flows)
                append_series(args.series, series)
                completed += 1
                print(f"  session={series[0]['session_id']} flow_snapshots={len(flows)}", flush=True)

    print(f"Đã thu {completed} sessions vào {args.output} và {args.series}")


if __name__ == "__main__":
    main()
