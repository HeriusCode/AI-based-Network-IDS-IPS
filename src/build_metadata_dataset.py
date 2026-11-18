"""Build a training Parquet where one day keeps source-IP/timestamp metadata.

The official CSE-CIC-IDS2018 processed CSVs are inconsistent: only the
``Thuesday-20-02-2018`` (DDoS1) file contains ``Src IP``/``Dst IP``/``Src Port``
and ``Flow ID``; the other days only contain ``Dst Port`` and ``Timestamp``.
The packaged clean Parquet dropped even the timestamp.

This script combines:

* the existing clean Parquet for every day except the metadata day;
* one official CSV (normally DDoS1) with its metadata preserved.

Feature columns in the official CSV use the short CICFlowMeter names
(``Tot Fwd Pkts``) while the clean Parquet uses the long names
(``Total Fwd Packets``).  They are aligned by position after removing metadata
columns, and the script verifies that the number of features matches exactly.

The output is intentionally a *partial* metadata dataset.  It is enough to run
a one-day entity case study (DDoS1) through ``train_normalized.py`` and
``evaluate_entities.py``; it is not a substitute for a full 10-day entity LODO.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

try:
    from src.common import (
        EXCLUDED_COLUMNS,
        LABEL_COLUMN,
        MODEL_METADATA_COLUMNS,
        PROCESSED_DATA,
        PROJECT_ROOT,
    )
    from src.preprocess import clean_chunk
except ModuleNotFoundError:
    from common import (
        EXCLUDED_COLUMNS,
        LABEL_COLUMN,
        MODEL_METADATA_COLUMNS,
        PROCESSED_DATA,
        PROJECT_ROOT,
    )
    from preprocess import clean_chunk


DEFAULT_METADATA_CSV = (
    PROJECT_ROOT
    / "data"
    / "raw_with_metadata"
    / "Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data" / "processed" / "cse_cic_ids2018_with_meta_partial.parquet"
)
DEFAULT_SOURCE_FILE = "DDoS1-Tuesday-20-02-2018_TrafficForML_CICFlowMeter.parquet"

# Metadata names that must stay out of the feature matrix.  The clean Parquet
# has none of them; the official CSV has all of them for DDoS1.
METADATA_NAMES = tuple(
    name
    for name in MODEL_METADATA_COLUMNS
    if name in {"Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Timestamp"}
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-data", type=Path, default=PROCESSED_DATA)
    parser.add_argument("--metadata-csv", type=Path, default=DEFAULT_METADATA_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--source-file",
        default=DEFAULT_SOURCE_FILE,
        help="source_file value to assign to the metadata day; must match the "
        "name used by the clean Parquet so leave-one-day-out can identify it.",
    )
    parser.add_argument(
        "--max-csv-rows",
        type=int,
        default=None,
        help="Chỉ đọc N dòng CSV (dùng để thử nhanh).",
    )
    parser.add_argument("--batch-size", type=int, default=100_000)
    return parser.parse_args()


def build_feature_mapping(csv_header: list[str], clean_features: list[str]) -> dict[str, str]:
    """Map official short feature names to the clean Parquet long names."""
    metadata = set(METADATA_NAMES) | {LABEL_COLUMN}
    official_features = [column for column in csv_header if column not in metadata]
    if len(official_features) != len(clean_features):
        raise ValueError(
            "Số feature không khớp: CSV có "
            f"{len(official_features)}, clean Parquet có {len(clean_features)}. "
            "Không thể ghép theo vị trí an toàn."
        )
    mapping = dict(zip(official_features, clean_features))
    # Protocol/Flow Duration should be the first two in both schemas.  This is
    # a cheap sanity check against a silently reordered source file.
    if official_features[:2] != ["Protocol", "Flow Duration"]:
        raise ValueError(
            "Header CSV không bắt đầu bằng Protocol, Flow Duration: "
            f"{official_features[:2]}"
        )
    return mapping


def unified_schema(clean_schema: pa.Schema) -> pa.Schema:
    fields = list(clean_schema)
    existing = {field.name for field in fields}
    for name in METADATA_NAMES:
        if name not in existing:
            fields.append(pa.field(name, pa.string()))
    return pa.schema(fields)


def table_for_clean_day(
    dataset: ds.Dataset,
    source_file: str,
    schema: pa.Schema,
) -> pa.Table:
    table = dataset.to_table(filter=ds.field("source_file") == source_file)
    for name in METADATA_NAMES:
        if name not in table.column_names:
            table = table.append_column(name, pa.nulls(table.num_rows, type=pa.string()))
    return table.select(schema.names).cast(schema)


def table_for_metadata_chunk(
    raw: pd.DataFrame,
    mapping: dict[str, str],
    source_file: str,
    schema: pa.Schema,
) -> pa.Table:
    raw = raw.rename(columns=mapping)
    chunk = clean_chunk(raw, source_file)
    if chunk is None:
        raise ValueError("CSV metadata không có cột Label.")
    for name in METADATA_NAMES:
        if name not in chunk.columns:
            chunk[name] = None
    return pa.Table.from_pandas(chunk, preserve_index=False).select(schema.names).cast(schema)


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size phải > 0.")
    clean_path = args.clean_data.resolve()
    output = args.output.resolve()
    if output == clean_path:
        raise ValueError("Không được ghi đè clean Parquet hiện tại.")
    if not args.metadata_csv.exists():
        raise FileNotFoundError(
            f"Không tìm thấy CSV metadata: {args.metadata_csv}. "
            "Chạy: python src/fetch_cic_ids2018.py --download --only-with-ip"
        )

    clean_parquet = pq.ParquetFile(clean_path)
    clean_schema = clean_parquet.schema_arrow
    clean_features = [
        column for column in clean_schema.names if column not in EXCLUDED_COLUMNS
    ]
    schema = unified_schema(clean_schema)

    csv_header = pd.read_csv(args.metadata_csv, nrows=0).columns.astype(str).str.strip().tolist()
    mapping = build_feature_mapping(csv_header, clean_features)
    print(f"Ghép {len(mapping)} feature theo vị trí; metadata giữ nguyên: {METADATA_NAMES}")

    source_files = (
        ds.dataset(clean_path, format="parquet")
        .to_table(columns=["source_file"])["source_file"]
        .to_pandas()
        .value_counts()
    )
    if args.source_file not in source_files.index:
        raise ValueError(
            f"Không thấy source_file={args.source_file!r} trong clean Parquet. "
            f"Các giá trị hiện có: {sorted(source_files.index)}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    if temporary.exists():
        temporary.unlink()

    dataset = ds.dataset(clean_path, format="parquet")
    writer: pq.ParquetWriter | None = None
    try:
        writer = pq.ParquetWriter(temporary, schema, compression="zstd")
        for source_file in sorted(source_files.index):
            if source_file == args.source_file:
                continue
            table = table_for_clean_day(dataset, str(source_file), schema)
            writer.write_table(table)
            print(f"  clean: {source_file} ({table.num_rows:,} dòng)")

        read_rows = 0
        for raw in pd.read_csv(
            args.metadata_csv,
            low_memory=False,
            chunksize=args.batch_size,
        ):
            if args.max_csv_rows is not None:
                remaining = args.max_csv_rows - read_rows
                if remaining <= 0:
                    break
                raw = raw.head(remaining)
            if raw.empty:
                break
            read_rows += len(raw)
            table = table_for_metadata_chunk(raw, mapping, args.source_file, schema)
            writer.write_table(table)
            print(f"  metadata: {read_rows:,} dòng CSV", end="\r", flush=True)
        print("")
    finally:
        if writer is not None:
            writer.close()

    temporary.replace(output)
    rows = pq.ParquetFile(output).metadata.num_rows
    print(f"Đã lưu: {output}")
    print(f"Tổng số dòng: {rows:,}")
    print(f"Metadata day: {args.source_file}")
    print(
        "Lưu ý: chỉ ngày metadata có source IP; các ngày còn lại vẫn thiếu IP. "
        "Đây là bộ dữ liệu cho case study một ngày, không phải LODO entity đầy đủ."
    )


if __name__ == "__main__":
    main()
