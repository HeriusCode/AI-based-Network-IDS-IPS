"""Calibrate the detection threshold on a held-out validation day.

The threshold is chosen from the benign score distribution of a validation day
that the model never saw during training. Two modes:

- ``lodo``: leave-one-day-out, where the validation day is the previous day in
  chronological order (cyclic). Reports how calibration generalises across all
  ten capture days.
- ``day``: fixed deployment split (train 14-22/02, validate 23/02, test
  28/02-02/03) and writes a deployable bundle with ``decision_threshold``.
"""

from __future__ import annotations

import argparse
import gc
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    from src.common import (
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        parquet_source_files,
        prepare_features,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )
    from src.train_detection import (
        attack_family,
        attack_labels,
        create_pipeline,
        fmt_metric,
        source_capture_date,
    )
except ModuleNotFoundError:
    from common import (
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        parquet_source_files,
        prepare_features,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )
    from train_detection import (
        attack_family,
        attack_labels,
        create_pipeline,
        fmt_metric,
        source_capture_date,
    )


TARGET_FPRS = (0.001, 0.005, 0.01, 0.02, 0.05)
DEFAULT_CALIBRATED_MODEL = MODEL_DIR / "detection_model_calibrated.joblib"


def read_sources(
    args: argparse.Namespace,
    sources: list[str],
    max_rows: int,
    seed: int,
) -> pd.DataFrame:
    return read_sampled_dataframe(
        args.data,
        max_rows,
        seed,
        filter_values={"source_file": sources},
    )


def fit_pipeline(
    train_frame: pd.DataFrame,
    features: list[str],
    args: argparse.Namespace,
):
    pipeline = create_pipeline(args)
    X = train_frame[features].replace([np.inf, -np.inf], np.nan)
    y = train_frame["target"].astype(int)
    pipeline.fit(X, y)
    return pipeline


def score_frame(pipeline, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    X = prepare_features(frame, features)
    return pipeline.predict_proba(X)[:, 1]


def thresholds_from_benign(scores: np.ndarray, target_fprs: tuple[float, ...]) -> dict[float, float]:
    """Pick threshold at the (1 - target_fpr) quantile of benign scores."""
    scores = np.asarray(scores)
    if scores.size == 0:
        raise ValueError("Không có flow benign trên ngày validation.")
    return {alpha: float(np.quantile(scores, 1.0 - alpha)) for alpha in target_fprs}


def detection_at(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float | int]:
    y_true = np.asarray(y_true).astype(int)
    predicted = np.asarray(scores) >= threshold
    tp = int(np.sum(predicted & (y_true == 1)))
    fp = int(np.sum(predicted & (y_true == 0)))
    fn = int(np.sum(~predicted & (y_true == 1)))
    tn = int(np.sum(~predicted & (y_true == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total = tp + fp + fn + tn
    return {
        "threshold": float(threshold),
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "alerts": int(predicted.sum()),
    }


def pooled(entries: list[dict[str, object]], threshold_for) -> dict[str, object]:
    if not entries:
        return {}
    ys = [np.asarray(entry["y"]) for entry in entries]
    scores = [np.asarray(entry["scores"]) for entry in entries]
    predictions = [
        np.asarray(entry["scores"]) >= threshold_for(entry) for entry in entries
    ]
    y_true = np.concatenate(ys)
    pred = np.concatenate(predictions)
    tp = int(np.sum(pred & (y_true == 1)))
    fp = int(np.sum(pred & (y_true == 0)))
    fn = int(np.sum(~pred & (y_true == 1)))
    tn = int(np.sum(~pred & (y_true == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "rows": int(len(y_true)),
        "attack_rows": int(y_true.sum()),
        "recall": float(recall),
        "precision": float(precision),
        "f1": float(f1),
        "fpr": float(fp / (fp + tn)) if fp + tn else 0.0,
        "alerts": int(pred.sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def macro_over_folds(fold_rows: list[dict[str, object]], key: str) -> dict[str, float]:
    values = [row[key]["f1"] for row in fold_rows]
    recalls = [row[key]["recall"] for row in fold_rows]
    return {
        "f1_mean": float(np.mean(values)),
        "f1_std": float(np.std(values)),
        "recall_mean": float(np.mean(recalls)),
        "recall_std": float(np.std(recalls)),
    }


def family_group(frame: pd.DataFrame, train_families: set[str]) -> str:
    families = {attack_family(label) for label in attack_labels(frame)}
    return "family_unseen" if families - train_families else "family_seen"


def run_lodo(args: argparse.Namespace) -> None:
    days = sorted(parquet_source_files(args.data), key=source_capture_date)
    selected = days
    if args.only_sources:
        keys = [key.lower() for key in args.only_sources]
        selected = [name for name in days if any(key in name.lower() for key in keys)]
    if not selected:
        raise ValueError("Không có source_file nào khớp --only-sources.")

    entries: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    for index, test_source in enumerate(selected, 1):
        position = days.index(test_source)
        validation_source = days[(position - 1) % len(days)]
        train_sources = [
            name for name in days if name not in (test_source, validation_source)
        ]
        print(
            f"[{index}/{len(selected)}] test={test_source[:12]} "
            f"validation={validation_source[:12]} train_days={len(train_sources)}"
        )

        train_frame = read_sources(args, train_sources, args.max_rows, args.random_state)
        validation_frame = read_sources(
            args, [validation_source], args.max_val_rows, args.random_state + 20_000
        )
        test_frame = read_sources(
            args, [test_source], args.max_test_rows, args.random_state + 10_000
        )

        features = select_numeric_features(train_frame)
        pipeline = fit_pipeline(train_frame, features, args)

        benign_mask = validation_frame["target"].astype(int).eq(0).to_numpy()
        validation_scores = score_frame(pipeline, validation_frame, features)[benign_mask]
        thresholds = thresholds_from_benign(validation_scores, args.target_fpr)

        scores = score_frame(pipeline, test_frame, features)
        y_true = test_frame["target"].astype(int).to_numpy()
        train_families = {attack_family(label) for label in attack_labels(train_frame)}

        entry = {
            "fold": index,
            "test_source": test_source,
            "validation_source": validation_source,
            "y": y_true,
            "scores": scores,
            "thresholds": thresholds,
            "group": family_group(test_frame, train_families),
            "unseen_families": sorted(
                {attack_family(label) for label in attack_labels(test_frame)} - train_families
            ),
        }
        entries.append(entry)

        row = {
            "fold": index,
            "capture_date": source_capture_date(test_source).isoformat(),
            "test_source": test_source,
            "validation_source": validation_source,
            "validation_benign_rows": int(len(validation_scores)),
            "rows": int(len(y_true)),
            "attack_rows": int(y_true.sum()),
            "group": entry["group"],
            "unseen_families": entry["unseen_families"],
            "thresholds": thresholds,
            "at_fixed_0_5": detection_at(y_true, scores, 0.5),
            **{
                f"fpr_{alpha}": detection_at(y_true, scores, thresholds[alpha])
                for alpha in args.target_fpr
            },
        }
        fold_rows.append(row)
        fixed = row["at_fixed_0_5"]
        chosen = row[f"fpr_{args.threshold_fpr}"]
        print(
            f"    fixed@0.5 recall={fixed['recall']:.4f} f1={fixed['f1']:.4f} "
            f"fpr={fixed['fpr']:.4%} | calibrated recall={chosen['recall']:.4f} "
            f"f1={chosen['f1']:.4f} fpr={chosen['fpr']:.4%} "
            f"thr={chosen['threshold']:.4f}"
        )

        del train_frame, validation_frame, test_frame
        gc.collect()

    policies: dict[str, dict[str, object]] = {
        "fixed_0_5": pooled(entries, lambda entry: 0.5)
    }
    for alpha in args.target_fpr:
        policies[f"fpr_{alpha}"] = pooled(
            entries, lambda entry, value=alpha: entry["thresholds"][value]
        )

    by_group: dict[str, dict[str, object]] = {}
    for group in ("family_seen", "family_unseen"):
        group_entries = [entry for entry in entries if entry["group"] == group]
        if not group_entries:
            continue
        by_group[group] = {
            "fixed_0_5": pooled(group_entries, lambda entry: 0.5),
            **{
                f"fpr_{alpha}": pooled(
                    group_entries, lambda entry, value=alpha: entry["thresholds"][value]
                )
                for alpha in args.target_fpr
            },
        }

    macro = {
        "fixed_0_5": macro_over_folds(fold_rows, "at_fixed_0_5"),
        **{
            f"fpr_{alpha}": macro_over_folds(fold_rows, f"fpr_{alpha}")
            for alpha in args.target_fpr
        },
    }

    payload = {
        "mode": "lodo",
        "protocol": (
            "Validation = ngày liền trước theo thời gian (cyclic); train = 8 ngày còn "
            "lại; test = ngày bị giữ. Ngưỡng lấy theo phân vị (1-FPR) của điểm benign "
            "trên ngày validation."
        ),
        "target_fprs": list(args.target_fpr),
        "chosen_fpr": args.threshold_fpr,
        "trees": args.trees,
        "max_rows": args.max_rows,
        "max_val_rows": args.max_val_rows,
        "max_test_rows": args.max_test_rows,
        "folds": fold_rows,
        "pooled": policies,
        "by_group": by_group,
        "macro": macro,
    }
    save_json(payload, RESULT_DIR / "calibration_metrics.json")

    summary_rows = []
    for row in fold_rows:
        chosen = row[f"fpr_{args.threshold_fpr}"]
        summary_rows.append(
            {
                "fold": row["fold"],
                "capture_date": row["capture_date"],
                "test_source": row["test_source"],
                "validation_source": row["validation_source"],
                "group": row["group"],
                "rows": row["rows"],
                "attack_rows": row["attack_rows"],
                "fixed_recall": row["at_fixed_0_5"]["recall"],
                "fixed_f1": row["at_fixed_0_5"]["f1"],
                "fixed_fpr": row["at_fixed_0_5"]["fpr"],
                "calibrated_threshold": chosen["threshold"],
                "calibrated_recall": chosen["recall"],
                "calibrated_precision": chosen["precision"],
                "calibrated_f1": chosen["f1"],
                "calibrated_fpr": chosen["fpr"],
                "unseen_families": "; ".join(row["unseen_families"]),
            }
        )
    pd.DataFrame(summary_rows).to_csv(
        RESULT_DIR / "calibration_summary.csv", index=False, encoding="utf-8-sig"
    )

    write_report(payload, RESULT_DIR / "calibration_report.md")
    print_pooled(payload)


def write_report(payload: dict[str, object], path: Path) -> None:
    alpha = payload["chosen_fpr"]
    policies = payload["pooled"]
    macro = payload["macro"]
    folds = payload["folds"]
    lines = [
        "# Calibration ngưỡng phát hiện",
        "",
        "## Thiết lập",
        "",
        f"- {payload['protocol']}",
        f"- Số fold: {len(folds)}; train tối đa {payload['max_rows']:,} flow; "
        f"validation tối đa {payload['max_val_rows']:,}; test tối đa "
        f"{payload['max_test_rows']:,}.",
        "- Ngưỡng được chọn hoàn toàn trên điểm benign của ngày validation, không dùng "
        "thông tin từ tập test.",
        "",
        "## Kết quả gộp toàn bộ fold",
        "",
        "| Chính sách ngưỡng | Recall | Precision | F1 | FPR thực tế | Số cảnh báo |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {"fixed_0_5": "cố định 0,5"}
    for value in payload["target_fprs"]:
        labels[f"fpr_{value}"] = f"FPR mục tiêu {value:.1%}"
    for key, label in labels.items():
        row = policies[key]
        lines.append(
            f"| {label} | {row['recall']:.4f} | {row['precision']:.4f} | {row['f1']:.4f} | "
            f"{row['fpr']:.4%} | {row['alerts']:,} |"
        )

    lines.extend(
        [
            "",
            "## Theo nhóm fold tại ngưỡng đã chọn",
            "",
            f"Ngưỡng chọn: FPR mục tiêu {alpha:.1%}.",
            "",
            "| Nhóm | Số fold | Attack rows | Recall | Precision | F1 | FPR thực tế |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for group, data in payload["by_group"].items():
        row = data[f"fpr_{alpha}"]
        lines.append(
            f"| {group} | {sum(1 for fold in folds if fold['group'] == group)} | "
            f"{row['attack_rows']:,} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )

    lines.extend(
        [
            "",
            "## Từng fold tại ngưỡng đã chọn",
            "",
            "| Fold | Ngày test | Ngày validation | Nhóm | Recall@0,5 | Recall@cal | F1@cal | FPR@cal | Ngưỡng |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in folds:
        chosen = row[f"fpr_{alpha}"]
        lines.append(
            f"| {row['fold']} | {row['capture_date']} | "
            f"{source_capture_date(row['validation_source']).isoformat()} | {row['group']} | "
            f"{row['at_fixed_0_5']['recall']:.4f} | {chosen['recall']:.4f} | "
            f"{chosen['f1']:.4f} | {chosen['fpr']:.4%} | {chosen['threshold']:.4f} |"
        )

    fixed = policies["fixed_0_5"]
    calibrated = policies[f"fpr_{alpha}"]
    lines.extend(
        [
            "",
            "## Diễn giải",
            "",
            f"Tại ngưỡng 0,5, recall gộp là {fixed['recall']:.2%} với FPR {fixed['fpr']:.2%}. "
            f"Sau calibration ở FPR mục tiêu {alpha:.1%}, recall gộp là "
            f"{calibrated['recall']:.2%}, F1 {calibrated['f1']:.4f}, FPR thực tế "
            f"{calibrated['fpr']:.2%}.",
        ]
    )
    if calibrated["fpr"] > alpha * 1.5:
        lines.append(
            "FPR thực tế trên test cao hơn mục tiêu đáng kể, nghĩa là phân bố điểm benign "
            "của ngày test khác ngày validation (drift). Cần hiệu chỉnh lại ngưỡng theo "
            "một ngày gần tập test hơn hoặc dùng chuẩn hoá theo ngày."
        )
    else:
        lines.append(
            "FPR thực tế bám sát mục tiêu, cho thấy ngưỡng lấy từ ngày validation chuyển "
            "được sang ngày khác mà không làm bùng nổ false positive."
        )
    lines.append(
        "Đây là cận trên thực tế (không dùng test để chọn ngưỡng), khác với cột "
        "`F1 tốt nhất` trong báo cáo LODO vốn chọn ngưỡng trên chính tập test."
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def print_pooled(payload: dict[str, object]) -> None:
    alpha = payload["chosen_fpr"]
    print("")
    print("Chính sách            recall   precision   f1       fpr")
    for key, row in payload["pooled"].items():
        print(
            f"{key:<20} {fmt_metric(row['recall'])}   {fmt_metric(row['precision'])}   "
            f"{fmt_metric(row['f1'])}   {row['fpr']:.4%}"
        )
    for group, data in payload["by_group"].items():
        row = data[f"fpr_{alpha}"]
        print(
            f"{group:<20} recall={row['recall']:.4f} f1={row['f1']:.4f} "
            f"fpr={row['fpr']:.4%} attacks={row['attack_rows']:,}"
        )


def run_day(args: argparse.Namespace) -> None:
    sources = parquet_source_files(args.data)
    test_sources = [
        name for name in sources if source_capture_date(name) >= args.test_start
    ]
    train_sources = [
        name
        for name in sources
        if source_capture_date(name) <= args.train_end
    ]
    validation = [
        name
        for name in sources
        if args.val_source.lower() in name.lower()
    ]
    if len(validation) != 1:
        raise ValueError(
            "--val-source phải khớp đúng một source_file; "
            f"tìm thấy {len(validation)}."
        )
    validation_source = validation[0]
    if validation_source in train_sources:
        train_sources = [name for name in train_sources if name != validation_source]
    if set(train_sources) & (set(test_sources) | set(validation)):
        raise ValueError("Train/validation/test đang chồng lấn source_file.")

    train_frame = read_sources(args, train_sources, args.max_rows, args.random_state)
    validation_frame = read_sources(
        args, [validation_source], args.max_val_rows, args.random_state + 20_000
    )
    test_frame = read_sources(
        args, test_sources, args.max_test_rows, args.random_state + 10_000
    )

    features = select_numeric_features(train_frame)
    pipeline = fit_pipeline(train_frame, features, args)

    benign_mask = validation_frame["target"].astype(int).eq(0).to_numpy()
    validation_scores = score_frame(pipeline, validation_frame, features)[benign_mask]
    thresholds = thresholds_from_benign(validation_scores, args.target_fpr)

    scores = score_frame(pipeline, test_frame, features)
    y_true = test_frame["target"].astype(int).to_numpy()
    chosen_threshold = thresholds[args.threshold_fpr]

    fixed = detection_at(y_true, scores, 0.5)
    calibrated = detection_at(y_true, scores, chosen_threshold)
    per_source = {}
    labels = test_frame["source_file"].reset_index(drop=True)
    for source in sorted(labels.unique()):
        mask = labels.eq(source).to_numpy()
        per_source[source] = detection_at(y_true[mask], scores[mask], chosen_threshold)

    bundle = {
        "pipeline": pipeline,
        "feature_columns": features,
        "task": "binary_detection",
        "classes": {0: "BENIGN", 1: "ATTACK"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split_strategy": "day",
        "random_state": args.random_state,
        "max_rows": args.max_rows,
        "max_test_rows": args.max_test_rows,
        "train_sources": train_sources,
        "test_sources": test_sources,
        "train_end": args.train_end.isoformat(),
        "test_start": args.test_start.isoformat(),
        "decision_threshold": float(chosen_threshold),
        "calibration": {
            "validation_source": validation_source,
            "target_fpr": float(args.threshold_fpr),
            "validation_benign_rows": int(len(validation_scores)),
            "thresholds": {str(key): float(value) for key, value in thresholds.items()},
            "test_metrics_at_threshold": calibrated,
        },
    }
    model_path = Path(args.model)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)

    payload = {
        "mode": "day",
        "protocol": (
            "Train 14-22/02/2018; validation 23/02/2018; test 28/02-02/03/2018. "
            "Ngưỡng lấy từ phân vị benign của ngày validation."
        ),
        "target_fprs": list(args.target_fpr),
        "chosen_fpr": args.threshold_fpr,
        "model": str(model_path),
        "train_sources": train_sources,
        "validation_source": validation_source,
        "test_sources": test_sources,
        "validation_benign_rows": int(len(validation_scores)),
        "thresholds": {str(key): float(value) for key, value in thresholds.items()},
        "fixed_0_5": fixed,
        "calibrated": calibrated,
        "per_source_calibrated": per_source,
        "rows": int(len(y_true)),
        "attack_rows": int(y_true.sum()),
    }
    save_json(payload, RESULT_DIR / "calibration_day.json")

    print(f"Đã lưu model: {model_path.resolve()}")
    print(f"Ngày validation: {validation_source}")
    print(f"Ngưỡng đã chọn: {chosen_threshold:.6f} (FPR mục tiêu {args.threshold_fpr:.1%})")
    print(
        f"Test @0,5      recall={fixed['recall']:.4f} precision={fixed['precision']:.4f} "
        f"f1={fixed['f1']:.4f} fpr={fixed['fpr']:.4%}"
    )
    print(
        f"Test @calibrated recall={calibrated['recall']:.4f} "
        f"precision={calibrated['precision']:.4f} f1={calibrated['f1']:.4f} "
        f"fpr={calibrated['fpr']:.4%}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["lodo", "day"], default="lodo")
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--model", default=str(DEFAULT_CALIBRATED_MODEL))
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--max-rows", type=int, default=500_000)
    parser.add_argument("--max-val-rows", type=int, default=150_000)
    parser.add_argument("--max-test-rows", type=int, default=200_000)
    parser.add_argument(
        "--target-fpr",
        type=float,
        nargs="*",
        default=list(TARGET_FPRS),
        help="Các mức FPR mục tiêu cần quét.",
    )
    parser.add_argument(
        "--threshold-fpr",
        type=float,
        default=0.01,
        help="Mức FPR dùng để chọn ngưỡng triển khai (phải nằm trong --target-fpr).",
    )
    parser.add_argument("--train-end", type=date.fromisoformat, default=date(2018, 2, 22))
    parser.add_argument("--test-start", type=date.fromisoformat, default=date(2018, 2, 28))
    parser.add_argument("--val-source", default="Web2", help="Chuỗi khớp source_file validation.")
    parser.add_argument("--only-sources", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    if args.threshold_fpr not in args.target_fpr:
        raise ValueError("--threshold-fpr phải nằm trong --target-fpr.")
    if args.mode == "lodo":
        run_lodo(args)
    else:
        run_day(args)


if __name__ == "__main__":
    main()
