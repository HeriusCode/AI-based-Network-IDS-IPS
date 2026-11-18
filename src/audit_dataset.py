"""Audit a CSV/Parquet file for IDS entity metadata.

CIC-IDS2017 is distributed in two very different shapes:

* ``MachineLearningCSV`` / ``combine.csv``: 79 flow features + ``Label``; no
  ``Flow ID``, source IP, destination IP, ports or timestamp.
* ``GeneratedLabelledFlows`` / ``TrafficLabelling``: per-day flows with
  ``Flow ID``, ``Source IP``, ``Source Port``, ``Destination IP``,
  ``Destination Port``, ``Protocol`` and ``Timestamp``.

Only the second shape supports source-IP/time-window entity aggregation and
day-based LODO.  This script makes the distinction explicit before any
preprocessing or training is attempted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

try:
    from src.common import save_json
except ModuleNotFoundError:  # Allows: python src/audit_dataset.py
    from common import save_json


METADATA_ALIASES: dict[str, tuple[str, ...]] = {
    "flow_id": ("Flow ID", "flow_id"),
    "source_ip": ("Source IP", "Src IP", "source_ip", "src_ip"),
    "source_port": ("Source Port", "Src Port", "source_port", "src_port"),
    "destination_ip": (
        "Destination IP",
        "Dst IP",
        "destination_ip",
        "dst_ip",
    ),
    "destination_port": (
        "Destination Port",
        "Dst Port",
        "destination_port",
        "dst_port",
    ),
    "protocol": ("Protocol", "protocol"),
    "timestamp": ("Timestamp", "timestamp", "Time", "time"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Chỉ đọc N dòng CSV để kiểm tra nhanh; 0 = đếm toàn bộ.",
    )
    return parser.parse_args()


def read_columns(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return [
            str(column).strip()
            for column in pq.ParquetFile(path).schema_arrow.names
        ]
    return (
        pd.read_csv(path, nrows=0)
        .columns.astype(str)
        .str.strip()
        .tolist()
    )


def count_rows(path: Path, max_rows: int) -> int:
    if path.suffix.lower() == ".parquet":
        return int(pq.ParquetFile(path).metadata.num_rows)
    if max_rows > 0:
        return int(len(pd.read_csv(path, nrows=max_rows, low_memory=False)))
    rows = 0
    for chunk in pd.read_csv(path, chunksize=250_000, low_memory=False):
        rows += len(chunk)
    return rows


def main() -> None:
    args = parse_args()
    path = args.input.resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    columns = read_columns(path)
    normalized = {column.strip(): column for column in columns}
    found: dict[str, str | None] = {}
    for canonical, aliases in METADATA_ALIASES.items():
        found[canonical] = next(
            (normalized[alias] for alias in aliases if alias in normalized),
            None,
        )

    label_column = next(
        (normalized[name] for name in ("Label", "label") if name in normalized),
        None,
    )
    has_entity_metadata = bool(found["source_ip"] and found["timestamp"])
    has_day_metadata = bool(found["timestamp"])
    rows = count_rows(path, args.max_rows)

    payload = {
        "input": str(path),
        "bytes": path.stat().st_size,
        "rows": rows,
        "columns_count": len(columns),
        "columns": columns,
        "label_column": label_column,
        "metadata": found,
        "has_source_ip": found["source_ip"] is not None,
        "has_timestamp": found["timestamp"] is not None,
        "supports_source_entity": has_entity_metadata,
        "supports_day_lodo": has_day_metadata,
        "verdict": (
            "Có thể chạy entity source IP + cửa sổ thời gian và LODO theo ngày."
            if has_entity_metadata
            else "Thiếu source IP/timestamp: không thể chạy entity source IP."
            if not has_day_metadata
            else "Có timestamp nhưng thiếu source IP: chỉ có thể gộp theo service/cửa sổ."
        ),
    }

    if args.report is not None:
        save_json(payload, args.report)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
