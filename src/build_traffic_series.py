"""Aggregate flow-level CIC-IDS data into a regular traffic time series.

Example (CIC-IDS2017 timestamps have minute resolution, so use 60 seconds):

    python src/build_traffic_series.py ^
        --data data/processed/cicids2017_with_meta.parquet ^
        --interval-seconds 60 ^
        --output data/processed/traffic_series_60s.csv

For a real SDN collector that reports every 5 seconds, pass the same columns
and ``--interval-seconds 5``.  Required input columns are ``Timestamp``,
``Total Fwd Packets``, ``Total Backward Packets``, ``Fwd Packets Length Total``,
``Bwd Packets Length Total``; ``target`` and ``source_file`` are optional but
recommended.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.common import PROJECT_ROOT, RESULT_DIR, save_json
    from src.traffic_features import parse_timestamps
except ModuleNotFoundError:  # Allows: python src/build_traffic_series.py
    from common import PROJECT_ROOT, RESULT_DIR, save_json
    from traffic_features import parse_timestamps


DEFAULT_DATA = PROJECT_ROOT / "data" / "processed" / "cicids2017_with_meta.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument(
        "--day",
        default=None,
        help="Chỉ lấy một source_file, ví dụ CICIDS2017-07-07-2017_Friday.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=RESULT_DIR / "traffic_series_summary.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interval_seconds <= 0:
        raise ValueError("--interval-seconds phải > 0.")
    if not args.data.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu: {args.data}")

    columns = [
        "Timestamp",
        "Total Fwd Packets",
        "Total Backward Packets",
        "Fwd Packets Length Total",
        "Bwd Packets Length Total",
        "target",
        "source_file",
    ]
    import pyarrow.parquet as pq

    available = set(pq.ParquetFile(args.data).schema_arrow.names)
    selected = [column for column in columns if column in available]
    frame = pd.read_parquet(args.data, columns=selected)

    if "Timestamp" not in frame:
        raise ValueError("Dữ liệu thiếu cột Timestamp.")
    if args.day:
        if "source_file" not in frame:
            raise ValueError("Dữ liệu thiếu cột source_file để lọc --day.")
        frame = frame[frame["source_file"].astype(str).eq(args.day)]
        if frame.empty:
            days = sorted(pd.read_parquet(args.data, columns=["source_file"])["source_file"].astype(str).unique())
            raise ValueError(f"Không có ngày {args.day!r}. Các ngày có sẵn: {days}")

    frame = frame.copy()
    frame["timestamp"] = parse_timestamps(frame["Timestamp"])
    frame = frame.dropna(subset=["timestamp"])
    if frame.empty:
        raise ValueError("Không parse được Timestamp.")

    seconds = frame["timestamp"].dt.second
    if args.interval_seconds < 60 and seconds.nunique() == 1 and int(seconds.iloc[0]) == 0:
        print(
            "CẢNH BÁO: Timestamp chỉ có độ phân giải phút. "
            f"Dùng --interval-seconds {args.interval_seconds} sẽ tạo nhiều bucket 0. "
            "Nên dùng 60 giây cho CIC-IDS2017."
        )

    for column in ("Total Fwd Packets", "Total Backward Packets", "Fwd Packets Length Total", "Bwd Packets Length Total"):
        if column not in frame:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    frame["packets"] = frame["Total Fwd Packets"] + frame["Total Backward Packets"]
    frame["bytes"] = frame["Fwd Packets Length Total"] + frame["Bwd Packets Length Total"]
    if "target" not in frame:
        frame["target"] = 0
    frame["target"] = pd.to_numeric(frame["target"], errors="coerce").fillna(0).astype(int)

    bucket = frame["timestamp"].dt.floor(f"{int(args.interval_seconds)}s")
    grouped = frame.groupby(bucket).agg(
        packets=("packets", "sum"),
        bytes=("bytes", "sum"),
        flows=("packets", "size"),
        attacks=("target", "sum"),
    )
    full_index = pd.date_range(
        grouped.index.min(),
        grouped.index.max(),
        freq=f"{int(args.interval_seconds)}s",
    )
    grouped = grouped.reindex(full_index, fill_value=0)
    grouped.index.name = "timestamp"

    grouped["packets_per_second"] = grouped["packets"] / float(args.interval_seconds)
    grouped["bytes_per_second"] = grouped["bytes"] / float(args.interval_seconds)
    grouped["attack_ratio"] = np.where(
        grouped["flows"] > 0,
        grouped["attacks"] / grouped["flows"].replace(0, np.nan),
        0.0,
    )
    grouped = grouped.reset_index()

    output = args.output
    if output is None:
        output = PROJECT_ROOT / "data" / "processed" / f"traffic_series_{int(args.interval_seconds)}s.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_csv(output, index=False)

    summary = {
        "input": str(args.data),
        "output": str(output),
        "day": args.day,
        "interval_seconds": int(args.interval_seconds),
        "rows": int(len(grouped)),
        "start": str(grouped["timestamp"].min()),
        "end": str(grouped["timestamp"].max()),
        "total_flows": int(grouped["flows"].sum()),
        "attack_flows": int(grouped["attacks"].sum()),
        "zero_flow_buckets": int((grouped["flows"] == 0).sum()),
        "max_packets_per_second": float(grouped["packets_per_second"].max()),
        "max_bytes_per_second": float(grouped["bytes_per_second"].max()),
        "mean_packets_per_second": float(grouped["packets_per_second"].mean()),
        "mean_bytes_per_second": float(grouped["bytes_per_second"].mean()),
    }
    save_json(summary, args.summary)
    print(f"Đã ghi {len(grouped):,} bucket vào: {output.resolve()}")
    print(
        f"Khoảng thời gian: {summary['start']} → {summary['end']} "
        f"({summary['interval_seconds']}s)"
    )
    print(
        f"Flow: {summary['total_flows']:,} (attack {summary['attack_flows']:,}); "
        f"bucket rỗng: {summary['zero_flow_buckets']:,}"
    )
    print(f"Đã ghi summary: {args.summary.resolve()}")


if __name__ == "__main__":
    main()
