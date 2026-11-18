"""Diagnose whether per-batch score normalisation fixes cross-day threshold drift.

For a few leave-one-day-out folds, compare four label-free policies:

- ``raw``: threshold at the 99th percentile of benign scores of the previous day.
- ``batch_z``: z-normalise scores with the median/MAD of each batch, then use the
  same 99th percentile threshold on the validation day.
- ``top_1`` / ``top_5``: alert on the top 1% / 5% of the day's scores (alert budget).

The point is to separate "the model ranks badly" from "the score scale moves
between days". Only the Random Forest is used because it is the primary model.
"""

from __future__ import annotations

import argparse
import gc

import numpy as np

try:
    from src.calibrate import (
        detection_at,
        fit_pipeline,
        read_sources,
        score_frame,
    )
    from src.common import (
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        parquet_source_files,
        save_json,
        select_numeric_features,
    )
    from src.train_detection import source_capture_date
except ModuleNotFoundError:
    from calibrate import detection_at, fit_pipeline, read_sources, score_frame
    from common import (
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        parquet_source_files,
        save_json,
        select_numeric_features,
    )
    from train_detection import source_capture_date


def batch_location_scale(scores: np.ndarray) -> tuple[float, float]:
    median = float(np.median(scores))
    mad = float(np.median(np.abs(scores - median)))
    scale = 1.4826 * mad
    if scale <= 1e-9:
        scale = float(np.std(scores)) or 1.0
    return median, scale


def oracle(scores: np.ndarray, y_true: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import precision_recall_curve

    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    f1 = 2 * precision * recall / (precision + recall + 1e-12)
    index = int(np.argmax(f1))
    return {
        "f1": float(f1[index]),
        "precision": float(precision[index]),
        "recall": float(recall[index]),
        "threshold": float(thresholds[index]) if index < len(thresholds) else float(np.max(scores)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--max-rows", type=int, default=500_000)
    parser.add_argument("--max-val-rows", type=int, default=150_000)
    parser.add_argument("--max-test-rows", type=int, default=200_000)
    parser.add_argument("--only-sources", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    days = sorted(parquet_source_files(args.data), key=source_capture_date)
    selected = days
    if args.only_sources:
        keys = [key.lower() for key in args.only_sources]
        selected = [name for name in days if any(key in name.lower() for key in keys)]

    rows = []
    for index, test_source in enumerate(selected, 1):
        position = days.index(test_source)
        validation_source = days[(position - 1) % len(days)]
        train_sources = [name for name in days if name not in (test_source, validation_source)]
        print(f"[{index}/{len(selected)}] test={test_source[:14]} validation={validation_source[:14]}")

        train_frame = read_sources(args, train_sources, args.max_rows, args.random_state)
        validation_frame = read_sources(
            args, [validation_source], args.max_val_rows, args.random_state + 20_000
        )
        test_frame = read_sources(
            args, [test_source], args.max_test_rows, args.random_state + 10_000
        )
        features = select_numeric_features(train_frame)
        pipeline = fit_pipeline(train_frame, features, args)

        validation_all = score_frame(pipeline, validation_frame, features)
        y_validation = validation_frame["target"].astype(int).to_numpy()
        validation_benign = validation_all[y_validation == 0]

        validation_median, validation_scale = batch_location_scale(validation_all)
        z_validation_benign = (validation_benign - validation_median) / validation_scale

        raw_threshold = float(np.quantile(validation_benign, 0.99))
        z_threshold = float(np.quantile(z_validation_benign, 0.99))

        scores = score_frame(pipeline, test_frame, features)
        y_true = test_frame["target"].astype(int).to_numpy()
        test_median, test_scale = batch_location_scale(scores)
        z_scores = (scores - test_median) / test_scale

        top_1_threshold = float(np.quantile(scores, 0.99))
        top_5_threshold = float(np.quantile(scores, 0.95))

        row = {
            "fold": index,
            "capture_date": source_capture_date(test_source).isoformat(),
            "test_source": test_source,
            "validation_source": validation_source,
            "rows": int(len(y_true)),
            "attack_rows": int(y_true.sum()),
            "raw_threshold": raw_threshold,
            "z_threshold": z_threshold,
            "raw": detection_at(y_true, scores, raw_threshold),
            "batch_z": detection_at(y_true, z_scores, z_threshold),
            "top_1": detection_at(y_true, scores, top_1_threshold),
            "top_5": detection_at(y_true, scores, top_5_threshold),
            "oracle": oracle(scores, y_true),
        }
        rows.append(row)
        print(
            f"    raw f1={row['raw']['f1']:.4f} fpr={row['raw']['fpr']:.4%} | "
            f"batch_z f1={row['batch_z']['f1']:.4f} fpr={row['batch_z']['fpr']:.4%} | "
            f"top1 f1={row['top_1']['f1']:.4f} rec={row['top_1']['recall']:.4f} | "
            f"oracle f1={row['oracle']['f1']:.4f}"
        )

        del train_frame, validation_frame, test_frame
        gc.collect()

    def pooled(key: str) -> dict[str, float]:
        tp = sum(row[key]["tp"] for row in rows)
        fp = sum(row[key]["fp"] for row in rows)
        fn = sum(row[key]["fn"] for row in rows)
        tn = sum(row[key]["tn"] for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "recall": recall,
            "precision": precision,
            "f1": f1,
            "fpr": fp / (fp + tn) if fp + tn else 0.0,
        }

    payload = {
        "protocol": (
            "3 fold chẩn đoán. raw = phân vị 99% benign ngày validation; batch_z = "
            "chuẩn hoá median/MAD theo từng batch rồi dùng phân vị 99%; top_1/top_5 = "
            "cảnh báo top 1%/5% điểm cao nhất trong ngày."
        ),
        "folds": rows,
        "pooled": {key: pooled(key) for key in ("raw", "batch_z", "top_1", "top_5")},
    }
    save_json(payload, RESULT_DIR / "batch_calibration.json")

    lines = [
        "# Chẩn đoán chuẩn hoá điểm theo batch",
        "",
        payload["protocol"],
        "",
        "| Fold | Ngày test | Recall raw | F1 raw | F1 batch_z | F1 top1% | F1 top5% | F1 oracle |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['fold']} | {row['capture_date']} | {row['raw']['recall']:.4f} | "
            f"{row['raw']['f1']:.4f} | {row['batch_z']['f1']:.4f} | "
            f"{row['top_1']['f1']:.4f} | {row['top_5']['f1']:.4f} | {row['oracle']['f1']:.4f} |"
        )
    lines.extend(["", "## Gộp 3 fold", "", "| Chính sách | Recall | Precision | F1 | FPR |", "|---|---:|---:|---:|---:|"])
    for key, label in (
        ("raw", "raw (validation q99)"),
        ("batch_z", "batch median/MAD z-score"),
        ("top_1", "top 1% trong ngày"),
        ("top_5", "top 5% trong ngày"),
    ):
        row = payload["pooled"][key]
        lines.append(
            f"| {label} | {row['recall']:.4f} | {row['precision']:.4f} | {row['f1']:.4f} | "
            f"{row['fpr']:.4%} |"
        )
    lines.append("")
    (RESULT_DIR / "batch_calibration.md").write_text("\n".join(lines), encoding="utf-8")
    print("")
    for key, row in payload["pooled"].items():
        print(f"{key:<10} recall={row['recall']:.4f} precision={row['precision']:.4f} f1={row['f1']:.4f} fpr={row['fpr']:.4%}")
    print(f"Đã ghi: {(RESULT_DIR / 'batch_calibration.json').resolve()}")


if __name__ == "__main__":
    main()
