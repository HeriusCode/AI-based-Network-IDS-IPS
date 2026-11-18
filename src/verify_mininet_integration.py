"""Run a small end-to-end Mininet -> IDS/IPS -> AI verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-project", type=Path, default=Path(r"D:\Traffic Generator"))
    parser.add_argument("--ids-url", default="http://192.168.1.21:8000")
    args = parser.parse_args()
    sys.path.insert(0, str(args.traffic_project.resolve()))

    from PySide6.QtCore import QCoreApplication

    from app.config import AppConfig
    from app.models.traffic_config import TrafficConfig
    from app.services.remote_traffic_worker import RemoteTrafficWorker

    app = QCoreApplication.instance() or QCoreApplication([])
    del app
    app_config = AppConfig(
        server_ip="192.168.1.21",
        api_port=8000,
        vm_ip="192.168.201.129",
        vm_ssh_user="root",
        vm_agent_port=9000,
        connection_timeout=3.0,
    )
    scenarios = [
        TrafficConfig(
            "10.0.0.3", 8080, protocol="TCP", scenario="NORMAL",
            duration=5, packet_rate=15, packet_size=192,
            source_host="h1", target_host="h3",
        ),
        TrafficConfig(
            "10.0.0.3", 8080, protocol="TCP", scenario="DOS",
            duration=5, packet_rate=100, packet_size=40,
            source_host="h1", target_host="h3",
        ),
        TrafficConfig(
            "10.0.0.3", 8080, protocol="UDP", scenario="DDOS",
            duration=5, packet_rate=200, packet_size=512,
            source_host="h2", target_host="h3",
        ),
        TrafficConfig(
            "10.0.0.3", 8080, protocol="TCP", scenario="PORT_SCAN",
            duration=5, packet_rate=7, packet_size=40,
            source_host="h2", target_host="h3",
        ),
    ]
    session_ids: list[str] = []
    for config in scenarios:
        completed = []
        worker = RemoteTrafficWorker(config, app_config)
        worker.session_finished.connect(completed.append)
        worker.run()
        if not completed:
            raise RuntimeError(f"Không nhận được kết quả {config.scenario}")
        session = completed[0]
        print(f"{config.scenario}: status={session.status} session={session.session_id}")
        if session.status != "Completed":
            raise RuntimeError(session.error_message or f"{config.scenario} thất bại")
        session_ids.append(session.session_id)

    with urlopen(f"{args.ids_url}/api/flows", timeout=10) as response:
        payload = json.load(response)
    selected = [item for item in payload.get("flows", []) if item.get("session_id") in session_ids]
    if not selected:
        raise RuntimeError("IDS/IPS không trả flow của các session vừa chạy")
    summary: dict[str, dict[str, object]] = {}
    for session_id in session_ids:
        rows = [item for item in selected if item.get("session_id") == session_id]
        summary[session_id] = {
            "labels": sorted({str(item.get("label")) for item in rows}),
            "attack_types": sorted({str(item.get("attack_type")) for item in rows}),
            "max_attack_score": max(float(item.get("attack_score", 0)) for item in rows),
            "flow_count": len(rows),
        }
    expected = dict(zip(session_ids, [config.scenario for config in scenarios], strict=True))
    expected_family = {
        "DOS": "DoS",
        "DDOS": "DDoS",
        "PORT_SCAN": "Port Scan",
    }
    for session_id, scenario in expected.items():
        item = summary[session_id]
        if scenario == "NORMAL":
            if item["labels"] != ["BENIGN"]:
                raise RuntimeError(f"Normal bị phân loại sai: {item}")
        elif item["labels"] != ["ATTACK"] or expected_family[scenario] not in item["attack_types"]:
            raise RuntimeError(f"{scenario} bị phân loại sai: {item}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
