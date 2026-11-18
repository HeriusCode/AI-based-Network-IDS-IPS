"""Clean CIC-IDS CSV/Parquet files into one memory-efficient Parquet dataset."""

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
        PROCESSED_DATA,
        PROJECT_ROOT,
        RESULT_DIR,
        is_benign,
        normalize_label,
        save_json,
    )
except ModuleNotFoundError:  # Allows: python src/preprocess.py
    from common import (
        EXCLUDED_COLUMNS,
        LABEL_COLUMN,
        PROCESSED_DATA,
        PROJECT_ROOT,
        RESULT_DIR,
        is_benign,
        normalize_label,
        save_json,
    )


DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=PROCESSED_DATA)
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument(
        "--summary",
        type=Path,
        default=RESULT_DIR / "preprocessing_summary.json",
    )
    parser.add_argument(
        "--max-rows-per-file",
        type=int,
        default=None,
        help="Chỉ đọc N dòng mỗi file (dùng để thử nhanh).",
    )
    return parser.parse_args()


def iter_chunks(path: Path, batch_size: int, max_rows: int | None) -> Iterator[pd.DataFrame]:
    remaining = max_rows
    if path.suffix.lower() == ".csv":
        for frame in pd.read_csv(path, low_memory=False, chunksize=batch_size):
            if remaining is not None:
                frame = frame.head(remaining)
                remaining -= len(frame)
            if not frame.empty:
                yield frame
            if remaining is not None and remaining <= 0:
                break
        return

    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=batch_size):
        frame = batch.to_pandas()
        if remaining is not None:
            frame = frame.head(remaining)
            remaining -= len(frame)
        if not frame.empty:
            yield frame
        if remaining is not None and remaining <= 0:
            break


def clean_chunk(frame: pd.DataFrame, source_name: str) -> pd.DataFrame | None:
    frame.columns = frame.columns.astype(str).str.strip()
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    if LABEL_COLUMN not in frame.columns:
        return None

    # Arrow may restore Label as pandas Categorical; normalize through strings so
    # boolean mapping behaves consistently across pandas versions.
    frame[LABEL_COLUMN] = frame[LABEL_COLUMN].astype(str).map(normalize_label)
    frame = frame[frame[LABEL_COLUMN].ne("")].copy()
    for column in frame.columns:
        if column not in EXCLUDED_COLUMNS:
            # Source Parquet files use different integer widths for the same
            # feature. Float64 provides one stable schema across every day.
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    frame.replace([np.inf, -np.inf], np.nan, inplace=True)
    frame["target"] = (~frame[LABEL_COLUMN].map(is_benign)).astype("int8")
    frame["source_file"] = source_name
    frame.drop_duplicates(inplace=True)
    return frame


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size phải lớn hơn 0.")

    raw_dir = args.raw_dir.resolve()
    files = sorted([*raw_dir.rglob("*.csv"), *raw_dir.rglob("*.parquet")])
    output = args.output.resolve()
    files = [path for path in files if path.resolve() != output]
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy CSV/Parquet trong {raw_dir}. Hãy chép dataset vào thư mục này."
        )
    if output.suffix.lower() != ".parquet":
        raise ValueError("Output phải có định dạng .parquet để xử lý dataset lớn an toàn.")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    if temporary.exists():
        temporary.unlink()

    writer: pq.ParquetWriter | None = None
    label_counts: Counter[str] = Counter()
    binary_counts: Counter[int] = Counter()
    total_rows = 0
    dropped_duplicates = 0
    missing_values = 0

    try:
        for path in files:
            print(f"Đang đọc: {path.name}")
            found_label = False
            for raw_chunk in iter_chunks(path, args.batch_size, args.max_rows_per_file):
                before = len(raw_chunk)
                chunk = clean_chunk(raw_chunk, path.name)
                if chunk is None:
                    continue
                found_label = True
                dropped_duplicates += before - len(chunk)
                total_rows += len(chunk)
                missing_values += int(chunk.isna().sum().sum())
                label_counts.update(chunk[LABEL_COLUMN].value_counts().to_dict())
                binary_counts.update(chunk["target"].value_counts().to_dict())

                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                else:
                    table = table.cast(writer.schema)
                writer.write_table(table)
            if not found_label:
                print(f"Bỏ qua file không có cột {LABEL_COLUMN}: {path.name}")
    finally:
        if writer is not None:
            writer.close()

    if writer is None or total_rows == 0:
        if temporary.exists():
            temporary.unlink()
        raise ValueError(f"Không tìm thấy dữ liệu hợp lệ có cột {LABEL_COLUMN}.")
    temporary.replace(output)

    summary = {
        "output": str(output),
        "input_files": len(files),
        "rows": int(total_rows),
        "duplicates_removed_within_batches": int(dropped_duplicates),
        "missing_values": int(missing_values),
        "binary_distribution": {
            "BENIGN": int(binary_counts[0]),
            "ATTACK": int(binary_counts[1]),
        },
        "label_distribution": {
            label: int(count) for label, count in label_counts.most_common()
        },
    }
    save_json(summary, args.summary.resolve())

    print(f"Đã lưu: {output}")
    print(f"Số dòng: {total_rows:,} (loại {dropped_duplicates:,} dòng trùng trong batch)")
    print(f"BENIGN: {binary_counts[0]:,}")
    print(f"ATTACK: {binary_counts[1]:,}")
    print(f"Số giá trị thiếu: {missing_values:,}")
    print("Phân bố nhãn:")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count:,}")
    print(f"Báo cáo: {args.summary.resolve()}")


if __name__ == "__main__":
    main()
