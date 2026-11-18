"""Discover and download CSE-CIC-IDS2018 processed flow CSVs from the public bucket.

The official bucket exposes the "Processed Traffic Data for ML Algorithms" CSVs.
Most of those files only contain ``Dst Port`` and ``Timestamp``; they do NOT
contain ``Src IP``.  This script checks the header before downloading anything,
so we do not mistake a timestamp-only file for data suitable for entity
aggregation.

Examples:
    python src/fetch_cic_ids2018.py --check
    python src/fetch_cic_ids2018.py --download --only-with-ip
    python src/fetch_cic_ids2018.py --download --key "Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv"

Only the processed CSV area is used.  The original PCAP archives are much
larger (tens of GB per day) and are intentionally not downloaded.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from src.common import PROJECT_ROOT, RESULT_DIR
except ModuleNotFoundError:  # Allows: python src/fetch_cic_ids2018.py
    from common import PROJECT_ROOT, RESULT_DIR


BUCKET = "https://cse-cic-ids2018.s3.amazonaws.com/"
PREFIX = "Processed Traffic Data for ML Algorithms/"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw_with_metadata"
HEADER_BYTES = 4096


def quote_key(key: str) -> str:
    return urllib.parse.quote(key, safe="/")


def list_processed_files() -> list[dict[str, object]]:
    url = f"{BUCKET}?list-type=2&prefix={urllib.parse.quote(PREFIX)}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()
    root = ET.fromstring(payload)
    namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    result: list[dict[str, object]] = []
    for item in root.findall("s3:Contents", namespace):
        key = item.findtext("s3:Key", default="", namespaces=namespace)
        if not key.lower().endswith(".csv"):
            continue
        size = int(item.findtext("s3:Size", default="0", namespaces=namespace))
        result.append({"key": key, "size": size})
    return sorted(result, key=lambda row: str(row["key"]))


def read_header(key: str, byte_count: int = HEADER_BYTES) -> str:
    url = f"{BUCKET}{quote_key(key)}"
    request = urllib.request.Request(url, headers={"Range": f"bytes=0-{byte_count - 1}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace").splitlines()[0]


def inspect_files(files: list[dict[str, object]]) -> list[dict[str, object]]:
    inspected: list[dict[str, object]] = []
    for row in files:
        key = str(row["key"])
        header = read_header(key)
        columns = [column.strip() for column in header.split(",")]
        has_ip = any(column in columns for column in ("Src IP", "Source IP"))
        has_timestamp = "Timestamp" in columns
        inspected.append(
            {
                "key": key,
                "name": Path(key).name,
                "size": int(row["size"]),
                "size_gb": round(int(row["size"]) / 1_000_000_000, 3),
                "has_source_ip": has_ip,
                "has_timestamp": has_timestamp,
                "columns": columns,
            }
        )
        marker = "IP+timestamp" if has_ip and has_timestamp else (
            "timestamp only" if has_timestamp else "no timestamp"
        )
        print(f"{Path(key).name:<65} {int(row['size']) / 1_000_000_000:8.3f} GB  {marker}")
    return inspected


def download(key: str, output_dir: Path, overwrite: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / Path(key).name
    if target.exists() and not overwrite:
        print(f"Bỏ qua (đã có): {target}")
        return target

    url = f"{BUCKET}{quote_key(key)}"
    temporary = target.with_suffix(target.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    print(f"Đang tải: {Path(key).name}")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as handle:
        total = int(response.headers.get("Content-Length", "0"))
        downloaded = 0
        while True:
            chunk = response.read(8 * 1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if total:
                percent = downloaded / total * 100
                print(f"\r  {downloaded / 1_000_000_000:6.2f}/{total / 1_000_000_000:6.2f} GB "
                      f"({percent:5.1f}%)", end="", flush=True)
        print("")
    temporary.replace(target)
    print(f"Đã lưu: {target}")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra header, không tải.")
    parser.add_argument("--download", action="store_true", help="Tải file đã chọn.")
    parser.add_argument("--only-with-ip", action="store_true", help="Chỉ tải file có Source IP/Src IP.")
    parser.add_argument("--key", action="append", default=None, help="Tên file cụ thể (có thể lặp lại).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=RESULT_DIR / "data_acquisition.json",
        help="Nơi ghi inventory/header report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = list_processed_files()
    inspected = inspect_files(files)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {
                "bucket": BUCKET,
                "prefix": PREFIX,
                "files": inspected,
                "files_with_source_ip": [
                    row["name"] for row in inspected if row["has_source_ip"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Đã ghi inventory: {args.report}")

    if not args.download:
        return

    selected = inspected
    if args.key:
        wanted = {Path(value).name.lower() for value in args.key}
        selected = [row for row in selected if str(row["name"]).lower() in wanted]
        if not selected:
            raise ValueError(f"Không tìm thấy file khớp --key: {sorted(wanted)}")
    if args.only_with_ip:
        selected = [row for row in selected if row["has_source_ip"]]

    if not selected:
        print("Không có file nào khớp bộ lọc; không tải gì.")
        return

    total_bytes = sum(int(row["size"]) for row in selected)
    print(f"Sẽ tải {len(selected)} file, tổng {total_bytes / 1_000_000_000:.2f} GB")
    for row in selected:
        download(str(row["key"]), args.output_dir, args.overwrite)


if __name__ == "__main__":
    main()
