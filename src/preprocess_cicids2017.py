"""Build a metadata-preserving CIC-IDS2017 Parquet dataset.

The ``GeneratedLabelledFlows`` CSVs contain both CICFlowMeter features and the
flow metadata needed for entity aggregation:

    Flow ID, Source IP, Source Port, Destination IP, Destination Port,
    Protocol, Timestamp, ..., Label

The official ``MachineLearningCSV``/``combine.csv`` variant drops those
metadata columns.  This script deliberately reads the metadata-bearing variant,
renames its feature spelling to the CIC-IDS2018 schema used by the rest of the
project, and writes one day-grouped Parquet file.

Important: ``source_file`` is a **day** key, not the original CSV name.  Friday
is split across three CSVs (Bot, DDoS, PortScan) but must remain one LODO day;
otherwise the same capture day leaks between train and test.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

try:
    from src.common import (
        EXCLUDED_COLUMNS,
        LABEL_COLUMN,
        PROJECT_ROOT,
        RESULT_DIR,
        is_benign,
        normalize_label,
        save_json,
    )
except ModuleNotFoundError:  # Allows: python src/preprocess_cicids2017.py
    from common import (
        EXCLUDED_COLUMNS,
        LABEL_COLUMN,
        PROJECT_ROOT,
        RESULT_DIR,
        is_benign,
        normalize_label,
        save_json,
    )


DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "cicids2017" / "raw_metadata"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "cicids2017_with_meta.parquet"
DEFAULT_SUMMARY = RESULT_DIR / "cicids2017_preprocessing_summary.json"

# CIC-IDS2017 uses a few feature names that differ from CIC-IDS2018.
FEATURE_RENAMES = {
    "Total Length of Fwd Packets": "Fwd Packets Length Total",
    "Total Length of Bwd Packets": "Bwd Packets Length Total",
    "Min Packet Length": "Packet Length Min",
    "Max Packet Length": "Packet Length Max",
    "Average Packet Size": "Avg Packet Size",
    "Init_Win_bytes_forward": "Init Fwd Win Bytes",
    "Init_Win_bytes_backward": "Init Bwd Win Bytes",
    "act_data_pkt_fwd": "Fwd Act Data Packets",
    "min_seg_size_forward": "Fwd Seg Size Min",
    "Source IP": "Src IP",
    "Source Port": "Src Port",
    "Destination IP": "Dst IP",
    "Destination Port": "Dst Port",
}

# CIC-IDS2017 has a duplicate header artifact.  It is not part of the 2018
# feature schema and carries no independent signal.
DROP_COLUMNS = {"Fwd Header Length.1"}

METADATA_COLUMNS = ("Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Timestamp")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument(
        "--max-rows-per-file",
        type=int,
        default=None,
        help="Chỉ đọc N dòng mỗi file (dùng để thử nhanh).",
    )
    return parser.parse_args()


def iter_chunks(path: Path, batch_size: int, max_rows: int | None) -> Iterator[pd.DataFrame]:
    """Read CIC-IDS2017 CSVs; they contain cp1252 punctuation, not UTF-8."""
    remaining = max_rows
    for frame in pd.read_csv(
        path,
        low_memory=False,
        chunksize=batch_size,
        encoding="latin-1",
    ):
        if remaining is not None:
            frame = frame.head(remaining)
            remaining -= len(frame)
        if not frame.empty:
            yield frame
        if remaining is not None and remaining <= 0:
            break


def clean_chunk(frame: pd.DataFrame) -> tuple[pd.DataFrame | None, dict[str, int]]:
    """Normalize one CSV chunk, preserving entity metadata."""
    stats = {"blank_rows": 0, "bad_timestamp_rows": 0, "bad_label_rows": 0}
    frame.columns = frame.columns.astype(str).str.strip()
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    stats["blank_rows"] = int(frame.isna().all(axis=1).sum())
    frame = frame.dropna(how="all")
    if LABEL_COLUMN not in frame.columns:
        return None, stats

    # Blank lines in the Thursday Morning CSV are represented as all-null rows;
    # drop them before parsing labels/timestamps.
    frame = frame[frame[LABEL_COLUMN].notna()].copy()
    frame = frame.rename(columns=FEATURE_RENAMES)
    frame = frame.drop(columns=[column for column in DROP_COLUMNS if column in frame])
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()

    labels = (
        frame[LABEL_COLUMN]
        .astype(str)
        .str.replace("\x96", "-", regex=False)
        .str.replace("\x97", "-", regex=False)
        .map(normalize_label)
    )
    frame[LABEL_COLUMN] = labels
    invalid_label = labels.eq("") | labels.eq("nan")
    stats["bad_label_rows"] = int(invalid_label.sum())
    frame = frame[~invalid_label].copy()
    if frame.empty:
        return None, stats

    timestamps = pd.to_datetime(
        frame["Timestamp"],
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )
    bad_timestamp = timestamps.isna()
    stats["bad_timestamp_rows"] = int(bad_timestamp.sum())
    frame = frame[~bad_timestamp].copy()
    timestamps = timestamps[~bad_timestamp]
    if frame.empty:
        return None, stats

    # Friday has three CSVs.  Group by capture date so LODO never puts two
    # files from the same day on opposite sides of the split.
    day_keys = (
        "CICIDS2017-"
        + timestamps.dt.strftime("%d-%m-%Y")
        + "_"
        + timestamps.dt.day_name()
    )
    frame["source_file"] = day_keys.to_numpy()
    frame["target"] = (~frame[LABEL_COLUMN].map(is_benign)).astype("int8")

    for column in frame.columns:
        if column not in EXCLUDED_COLUMNS and column != "target":
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    frame.replace([np.inf, -np.inf], np.nan, inplace=True)
    frame.drop_duplicates(inplace=True)

    # Keep a stable column order.  Missing optional columns are left absent;
    # all CIC-IDS2017 files in this directory have the same header.
    ordered = [
        *[column for column in METADATA_COLUMNS if column in frame.columns],
        LABEL_COLUMN,
        "target",
        "source_file",
        *[
            column
            for column in frame.columns
            if column not in {*METADATA_COLUMNS, LABEL_COLUMN, "target", "source_file"}
        ],
    ]
    return frame.loc[:, ordered], stats


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size phải lớn hơn 0.")

    raw_dir = args.raw_dir.resolve()
    files = sorted(raw_dir.glob("*.csv"))
    output = args.output.resolve()
    if not files:
        raise FileNotFoundError(f"Không tìm thấy CSV trong {raw_dir}.")
    if output.suffix.lower() != ".parquet":
        raise ValueError("Output phải có đuôi .parquet.")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    if temporary.exists():
        temporary.unlink()

    writer: pq.ParquetWriter | None = None
    label_counts: Counter[str] = Counter()
    binary_counts: Counter[int] = Counter()
    file_rows: Counter[str] = Counter()
    day_rows: Counter[str] = Counter()
    day_attacks: Counter[str] = Counter()
    day_ips: dict[str, set[str]] = {}
    total_rows = 0
    total_blank = 0
    total_bad_timestamp = 0
    total_bad_label = 0
    total_duplicates = 0
    missing_values = 0

    try:
        for path in files:
            print(f"Đang đọc: {path.name}")
            file_count = 0
            for raw_chunk in iter_chunks(path, args.batch_size, args.max_rows_per_file):
                before = len(raw_chunk)
                chunk, stats = clean_chunk(raw_chunk)
                total_blank += stats["blank_rows"]
                total_bad_timestamp += stats["bad_timestamp_rows"]
                total_bad_label += stats["bad_label_rows"]
                if chunk is None:
                    continue
                total_duplicates += max(before - len(chunk), 0)
                total_rows += len(chunk)
                file_count += len(chunk)
                missing_values += int(chunk.isna().sum().sum())
                label_counts.update(chunk[LABEL_COLUMN].value_counts().to_dict())
                binary_counts.update(chunk["target"].value_counts().to_dict())
                for day, count in chunk["source_file"].value_counts().items():
                    day_rows[day] += int(count)
                day_attacks.update(
                    chunk.loc[chunk["target"].eq(1), "source_file"]
                    .value_counts()
                    .to_dict()
                )
                for day, group in chunk.groupby("source_file", sort=False):
                    day_ips.setdefault(str(day), set()).update(
                        group["Src IP"].dropna().astype(str).tolist()
                    )

                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                else:
                    table = table.cast(writer.schema)
                writer.write_table(table)
            file_rows[path.name] = file_count
    finally:
        if writer is not None:
            writer.close()

    if writer is None or total_rows == 0:
        if temporary.exists():
            temporary.unlink()
        raise ValueError("Không có dòng dữ liệu hợp lệ để ghi.")

    temporary.replace(output)
    summary = {
        "output": str(output),
        "input_files": len(files),
        "rows": int(total_rows),
        "binary_distribution": {
            "BENIGN": int(binary_counts[0]),
            "ATTACK": int(binary_counts[1]),
        },
        "label_distribution": {
            label: int(count) for label, count in label_counts.most_common()
        },
        "days": {
            day: {
                "rows": int(day_rows[day]),
                "attacks": int(day_attacks[day]),
                "benign": int(day_rows[day] - day_attacks[day]),
                "source_ips": int(len(day_ips.get(day, set()))),
            }
            for day in sorted(day_rows)
        },
        "files": {name: int(rows) for name, rows in sorted(file_rows.items())},
        "blank_rows_skipped": int(total_blank),
        "duplicate_or_invalid_rows_removed": int(total_duplicates),
        "bad_timestamp_rows": int(total_bad_timestamp),
        "bad_label_rows": int(total_bad_label),
        "missing_values": int(missing_values),
    }
    save_json(summary, args.summary.resolve())

    print(f"Đã lưu: {output}")
    print(f"Số dòng: {total_rows:,}")
    print(f"BENIGN: {binary_counts[0]:,}")
    print(f"ATTACK: {binary_counts[1]:,}")
    print(f"Bỏ qua dòng trống: {total_blank:,}")
    print(f"Timestamp lỗi: {total_bad_timestamp:,}")
    print("Theo ngày:")
    for day, rows in sorted(day_rows.items()):
        print(
            f"  {day}: {rows:,} flow, {day_attacks[day]:,} attack, "
            f"{len(day_ips.get(day, set())):,} source IP"
        )
    print(f"Báo cáo: {args.summary.resolve()}")


if __name__ == "__main__":
    main()
