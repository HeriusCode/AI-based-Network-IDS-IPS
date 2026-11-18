"""Shared utilities for model training, evaluation, and inference."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


# Python can inherit a legacy Windows code page that cannot print Vietnamese.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DATA = DATA_DIR / "processed" / "cse_cic_ids2018_clean.parquet"
MODEL_DIR = PROJECT_ROOT / "models"
RESULT_DIR = PROJECT_ROOT / "results"
DETECTION_MODEL = MODEL_DIR / "detection_model.joblib"
PREDICTION_MODEL = MODEL_DIR / "prediction_model.joblib"

LABEL_COLUMN = "Label"
TARGET_COLUMN = "target"
BENIGN_LABELS = {"BENIGN", "BENIGN TRAFFIC", "NORMAL"}

# Identifier/context columns must never become model features.  They are
# optional because the packaged CIC-IDS2018 Parquet files drop them, but when
# the original CSV is available they are needed to aggregate flow alerts into
# source-IP/time-window entities.
MODEL_METADATA_COLUMNS = (
    "Flow ID",
    "Source IP",
    "Src IP",
    "Destination IP",
    "Dst IP",
    "Source Port",
    "Src Port",
    "Destination Port",
    "Dst Port",
    "Timestamp",
)

# Map the alternative spellings found in CIC-IDS files to one stable schema in
# exported score files.
SCORE_METADATA_COLUMNS = {
    "source_ip": ("Source IP", "Src IP"),
    "destination_ip": ("Destination IP", "Dst IP"),
    "source_port": ("Source Port", "Src Port"),
    "destination_port": ("Destination Port", "Dst Port"),
    "flow_id": ("Flow ID",),
    "timestamp": ("Timestamp",),
}

EXCLUDED_COLUMNS = {
    LABEL_COLUMN,
    TARGET_COLUMN,
    "source_file",
    "source_ip",
    "destination_ip",
    "source_port",
    "destination_port",
    "flow_id",
    "timestamp",
    *MODEL_METADATA_COLUMNS,
}


def ensure_output_dirs() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_label(value: object) -> str:
    return " ".join(str(value).strip().split())


def is_benign(value: object) -> bool:
    return normalize_label(value).upper() in BENIGN_LABELS


def select_numeric_features(frame: pd.DataFrame) -> list[str]:
    """Return usable numeric features while excluding identifiers and targets."""
    return [
        column
        for column in frame.select_dtypes(include=[np.number]).columns
        if column not in EXCLUDED_COLUMNS and not frame[column].isna().all()
    ]


def read_dataframe(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Read CSV or Parquet through one interface."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu: {path}")
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
        return frame.head(nrows) if nrows else frame
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False, nrows=nrows)
    raise ValueError(f"Chỉ hỗ trợ file .csv hoặc .parquet: {path}")


def read_sampled_dataframe(
    path: str | Path,
    max_rows: int | None,
    random_state: int,
    batch_size: int = 100_000,
    filter_values: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Load a representative, memory-bounded sample from CSV or Parquet.

    Parquet batches are sampled proportionally, so every source file/day written
    by preprocessing contributes rows instead of taking only the first N rows.
    """
    path = Path(path)
    if path.suffix.lower() != ".parquet":
        frame = read_dataframe(path, nrows=max_rows if max_rows and max_rows > 0 else None)
        for column, values in (filter_values or {}).items():
            frame = frame[frame[column].isin(values)]
        return frame.reset_index(drop=True)

    import pyarrow.dataset as ds

    dataset = ds.dataset(path, format="parquet")
    expression = None
    for column, values in (filter_values or {}).items():
        condition = ds.field(column).isin(values)
        expression = condition if expression is None else expression & condition
    total_rows = dataset.count_rows(filter=expression)
    if total_rows == 0:
        raise ValueError(f"Bộ lọc không khớp dòng dữ liệu nào trong {path}.")
    if not max_rows or max_rows <= 0 or total_rows <= max_rows:
        return dataset.to_table(filter=expression).to_pandas().reset_index(drop=True)

    samples: list[pd.DataFrame] = []
    batches = dataset.scanner(filter=expression, batch_size=batch_size).to_batches()
    for index, batch in enumerate(batches):
        frame = batch.to_pandas()
        take = max(1, round(max_rows * len(frame) / total_rows))
        samples.append(
            frame.sample(n=min(take, len(frame)), random_state=random_state + index)
        )
    result = pd.concat(samples, ignore_index=True)
    if len(result) > max_rows:
        result = result.sample(n=max_rows, random_state=random_state)
    return result.reset_index(drop=True)


def parquet_source_files(path: str | Path) -> list[str]:
    """Read distinct source_file values efficiently from Parquet metadata."""
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(Path(path))
    column_index = parquet.schema_arrow.get_field_index("source_file")
    if column_index < 0:
        raise ValueError("Dữ liệu không có cột source_file. Hãy chạy preprocess.py lại.")

    values: set[str] = set()
    for index in range(parquet.metadata.num_row_groups):
        statistics = parquet.metadata.row_group(index).column(column_index).statistics
        if statistics and statistics.has_min_max and statistics.min == statistics.max:
            values.add(str(statistics.min))
            continue
        column = parquet.read_row_group(index, columns=["source_file"])["source_file"]
        values.update(str(value) for value in column.unique().to_pylist())
    return sorted(values)


def save_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def load_bundle(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy model: {path}. Hãy huấn luyện model trước."
        )
    bundle = joblib.load(path)
    required = {"pipeline", "feature_columns", "task"}
    if not isinstance(bundle, dict) or not required.issubset(bundle):
        raise ValueError(f"File model không đúng định dạng: {path}")
    return bundle


def prepare_features(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Align arbitrary input records with the exact training schema."""
    result = pd.DataFrame(index=frame.index)
    for column in feature_columns:
        if column in frame:
            result[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            result[column] = np.nan
    return result.replace([np.inf, -np.inf], np.nan)


def binary_metrics(y_true: pd.Series, y_pred: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=[0, 1],
            target_names=["BENIGN", "ATTACK"],
            output_dict=True,
            zero_division=0,
        ),
    }
    metrics["roc_auc"] = (
        float(roc_auc_score(y_true, scores)) if pd.Series(y_true).nunique() == 2 else None
    )
    return metrics

