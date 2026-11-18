"""Unsupervised anomaly detection baseline (Isolation Forest) for new attacks.

The detector is trained on benign flows only, so it can flag attack families the
supervised model never saw. Thresholds are calibrated on the benign score
distribution of a validation day, exactly like ``src/calibrate.py``.

Modes:
- ``lodo``: leave-one-day-out; validation day is the previous day (cyclic);
  train = benign flows of the 8 remaining days.
- ``day``: fixed deployment split (train 14-22/02, validate 23/02, test
  28/02-02/03) and writes ``models/anomaly_model.joblib``.
"""

from __future__ import annotations

import argparse
import gc
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer, RobustScaler, StandardScaler

try:
    from src.calibrate import (
        detection_at,
        pooled,
        read_sources,
        thresholds_from_benign,
    )
    from src.common import (
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        parquet_source_files,
        prepare_features,
        save_json,
        select_numeric_features,
    )
    from src.train_detection import (
        attack_family,
        attack_labels,
        fmt_metric,
        source_capture_date,
    )
except ModuleNotFoundError:
    from calibrate import detection_at, pooled, read_sources, thresholds_from_benign
    from common import (
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        parquet_source_files,
        prepare_features,
        save_json,
        select_numeric_features,
    )
    from train_detection import attack_family, attack_labels, fmt_metric, source_capture_date


TARGET_FPRS = (0.001, 0.005, 0.01, 0.02, 0.05)
DEFAULT_ANOMALY_MODEL = MODEL_DIR / "anomaly_model.joblib"


def make_scaler(args: argparse.Namespace):
    if args.scaler == "quantile":
        return QuantileTransformer(
            n_quantiles=1000,
            subsample=min(200_000, args.max_rows),
            output_distribution="normal",
            random_state=args.random_state,
        )
    if args.scaler == "robust":
        return RobustScaler()
    return StandardScaler()


def build_pipeline(args: argparse.Namespace) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", make_scaler(args)),
            (
                "detector",
                IsolationForest(
                    n_estimators=args.trees,
                    max_samples=args.max_samples,
                    random_state=args.random_state,
                    n_jobs=args.n_jobs,
                ),
            ),
        ]
    )


def anomaly_scores(pipeline: Pipeline, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Higher score means more anomalous (negated sklearn decision function)."""
    X = prepare_features(frame, features)
    return -pipeline.decision_function(X)


def fit_detector(
    benign_frame: pd.DataFrame,
    features: list[str],
    args: argparse.Namespace,
) -> Pipeline:
    pipeline = build_pipeline(args)
    X = benign_frame[features].replace([np.inf, -np.inf], np.nan)
    pipeline.fit(X)
    return pipeline


def family_group(frame: pd.DataFrame, train_families: set[str]) -> str:
    families = {attack_family(label) for label in attack_labels(frame)}
    return "family_unseen" if families - train_families else "family_seen"


def evaluate_fold(
    args: argparse.Namespace,
    pipeline: Pipeline,
    validation_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    features: list[str],
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    benign_mask = validation_frame["target"].astype(int).eq(0).to_numpy()
    validation_scores = anomaly_scores(pipeline, validation_frame, features)[benign_mask]
    thresholds = thresholds_from_benign(validation_scores, args.target_fpr)
    scores = anomaly_scores(pipeline, test_frame, features)
    y_true = test_frame["target"].astype(int).to_numpy()
    labels = test_frame["Label"].astype(str).reset_index(drop=True)

    per_label = {}
    for label in sorted(labels.unique()):
        mask = labels.eq(label).to_numpy()
        per_label[label] = {
            "rows": int(mask.sum()),
            "mean_anomaly_score": float(scores[mask].mean()),
            "predicted_attack_rate": float((scores[mask] >= thresholds[args.threshold_fpr]).mean()),
        }

    row = {
        "validation_benign_rows": int(len(validation_scores)),
        "rows": int(len(y_true)),
        "attack_rows": int(y_true.sum()),
        "thresholds": thresholds,
        "at_default": detection_at(y_true, scores, 0.0),
        **{
            f"fpr_{alpha}": detection_at(y_true, scores, thresholds[alpha])
            for alpha in args.target_fpr
        },
        "per_label": per_label,
    }
    if len(np.unique(y_true)) > 1:
        row["auc"] = float(roc_auc_score(y_true, scores))
        precision, recall, curve_thresholds = precision_recall_curve(y_true, scores)
        f1_scores = 2 * precision * recall / (precision + recall + 1e-12)
        best_index = int(np.argmax(f1_scores))
        row["best_f1"] = {
            "threshold": (
                float(curve_thresholds[best_index])
                if best_index < len(curve_thresholds)
                else float(np.max(scores))
            ),
            "f1": float(f1_scores[best_index]),
            "precision": float(precision[best_index]),
            "recall": float(recall[best_index]),
        }
    else:
        row["auc"] = None
        row["best_f1"] = None
    entry = {"y": y_true, "scores": scores, "thresholds": thresholds}
    return entry, row


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
        benign_train = train_frame[train_frame["target"].astype(int).eq(0)]
        validation_frame = read_sources(
            args, [validation_source], args.max_val_rows, args.random_state + 20_000
        )
        test_frame = read_sources(
            args, [test_source], args.max_test_rows, args.random_state + 10_000
        )
        features = select_numeric_features(benign_train)
        pipeline = fit_detector(benign_train, features, args)
        entry, row = evaluate_fold(args, pipeline, validation_frame, test_frame, features)

        train_families = {attack_family(label) for label in attack_labels(train_frame)}
        row.update(
            {
                "fold": index,
                "capture_date": source_capture_date(test_source).isoformat(),
                "test_source": test_source,
                "validation_source": validation_source,
                "group": family_group(test_frame, train_families),
                "unseen_families": sorted(
                    {attack_family(label) for label in attack_labels(test_frame)}
                    - train_families
                ),
                "train_benign_rows": int(len(benign_train)),
                "feature_count": len(features),
            }
        )
        entry["group"] = row["group"]
        entries.append(entry)
        fold_rows.append(row)

        chosen = row[f"fpr_{args.threshold_fpr}"]
        print(
            f"    benign_train={len(benign_train):,} auc={row['auc']:.3f} "
            f"fixed@0 recall={row['at_default']['recall']:.4f} "
            f"f1={row['at_default']['f1']:.4f} fpr={row['at_default']['fpr']:.4%} | "
            f"calibrated recall={chosen['recall']:.4f} f1={chosen['f1']:.4f} "
            f"fpr={chosen['fpr']:.4%} thr={chosen['threshold']:.4f}"
        )

        del train_frame, benign_train, validation_frame, test_frame
        gc.collect()

    policies: dict[str, dict[str, object]] = {"default_0": pooled(entries, lambda entry: 0.0)}
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
            "default_0": pooled(group_entries, lambda entry: 0.0),
            **{
                f"fpr_{alpha}": pooled(
                    group_entries, lambda entry, value=alpha: entry["thresholds"][value]
                )
                for alpha in args.target_fpr
            },
        }

    payload = {
        "mode": "lodo",
        "detector": "IsolationForest",
        "scaler": args.scaler,
        "trees": args.trees,
        "max_samples": args.max_samples,
        "protocol": (
            "Train chỉ trên benign của 8 ngày; validation = ngày liền trước (cyclic); "
            "test = ngày bị giữ. Ngưỡng theo phân vị (1-FPR) điểm benign validation."
        ),
        "target_fprs": list(args.target_fpr),
        "chosen_fpr": args.threshold_fpr,
        "folds": fold_rows,
        "pooled": policies,
        "by_group": by_group,
    }
    save_json(payload, RESULT_DIR / "anomaly_metrics.json")

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
                "train_benign_rows": row["train_benign_rows"],
                "default_recall": row["at_default"]["recall"],
                "default_f1": row["at_default"]["f1"],
                "default_fpr": row["at_default"]["fpr"],
                "calibrated_threshold": chosen["threshold"],
                "calibrated_recall": chosen["recall"],
                "calibrated_precision": chosen["precision"],
                "calibrated_f1": chosen["f1"],
                "calibrated_fpr": chosen["fpr"],
                "auc": row["auc"],
                "best_f1_oracle": row["best_f1"]["f1"] if row["best_f1"] else None,
                "best_f1_threshold": row["best_f1"]["threshold"] if row["best_f1"] else None,
                "unseen_families": "; ".join(row["unseen_families"]),
            }
        )
    pd.DataFrame(summary_rows).to_csv(
        RESULT_DIR / "anomaly_summary.csv", index=False, encoding="utf-8-sig"
    )
    write_report(payload, RESULT_DIR / "anomaly_report.md")
    print_summary(payload)


def write_report(payload: dict[str, object], path: Path) -> None:
    alpha = payload["chosen_fpr"]
    policies = payload["pooled"]
    folds = payload["folds"]
    lines = [
        "# Phát hiện bất thường không giám sát (Isolation Forest)",
        "",
        "## Thiết lập",
        "",
        f"- {payload['protocol']}",
        f"- Detector: IsolationForest ({payload['trees']} cây, "
        f"max_samples={payload['max_samples']}, scaler={payload['scaler']}).",
        f"- {len(folds)} fold; train tối đa {folds[0]['train_benign_rows']:,} flow benign.",
        "- Mô hình chỉ thấy benign nên về lý thuyết có thể bắt họ tấn công chưa từng xuất hiện.",
        "",
        "## Kết quả gộp",
        "",
        "| Chính sách ngưỡng | Recall | Precision | F1 | FPR thực tế |",
        "|---|---:|---:|---:|---:|",
    ]
    labels = {"default_0": "mặc định sklearn (score > 0)"}
    for value in payload["target_fprs"]:
        labels[f"fpr_{value}"] = f"FPR mục tiêu {value:.1%}"
    for key, label in labels.items():
        row = policies[key]
        lines.append(
            f"| {label} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )

    lines.extend(
        [
            "",
            f"## Theo nhóm tại ngưỡng FPR mục tiêu {alpha:.1%}",
            "",
            "| Nhóm | Số fold | Attack rows | Recall | Precision | F1 | FPR |",
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
            "## Từng fold",
            "",
            "| Fold | Ngày test | Nhóm | AUC | Recall@default | Recall@cal | F1@cal | F1 tốt nhất | FPR@cal | Ngưỡng |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in folds:
        chosen = row[f"fpr_{alpha}"]
        best = row["best_f1"]
        lines.append(
            f"| {row['fold']} | {row['capture_date']} | {row['group']} | "
            f"{row['auc']:.3f} | "
            f"{row['at_default']['recall']:.4f} | {chosen['recall']:.4f} | "
            f"{chosen['f1']:.4f} | {best['f1']:.4f} | {chosen['fpr']:.4%} | "
            f"{chosen['threshold']:.4f} |"
        )

    calibrated = policies[f"fpr_{alpha}"]
    fixed = policies["default_0"]
    aucs = [row["auc"] for row in folds if row["auc"] is not None]
    mean_auc = float(np.mean(aucs)) if aucs else float("nan")
    best_f1 = float(np.mean([row["best_f1"]["f1"] for row in folds if row["best_f1"]]))
    lines.extend(
        [
            "",
            "## Diễn giải",
            "",
            f"AUC trung bình theo fold: {mean_auc:.4f}; F1 tốt nhất (oracle, chọn ngưỡng "
            f"trên chính test) trung bình: {best_f1:.4f}.",
            f"Ở ngưỡng mặc định, recall gộp {fixed['recall']:.2%} với FPR {fixed['fpr']:.2%}. "
            f"Sau calibration ở FPR mục tiêu {alpha:.1%}, recall {calibrated['recall']:.2%}, "
            f"F1 {calibrated['f1']:.4f}, FPR thực tế {calibrated['fpr']:.2%}.",
        ]
    )
    unseen = payload["by_group"].get("family_unseen")
    seen = payload["by_group"].get("family_seen")
    if unseen and seen:
        lines.append(
            f"Nhóm họ tấn công mới (`family_unseen`) đạt recall "
            f"{unseen[f'fpr_{alpha}']['recall']:.2%} so với "
            f"{seen[f'fpr_{alpha}']['recall']:.2%} ở nhóm họ đã thấy. Mục tiêu của hướng B là "
            "đẩy con số đầu tiên lên mà không phụ thuộc nhãn tấn công."
        )
    lines.append(
        "So sánh trực tiếp với Random Forest đã calibration: xem "
        "`results/calibration_report.md` (cùng giao thức validation và cùng mức FPR mục tiêu)."
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(payload: dict[str, object]) -> None:
    print("")
    print("Chính sách            recall   precision   f1       fpr")
    for key, row in payload["pooled"].items():
        print(
            f"{key:<20} {fmt_metric(row['recall'])}   {fmt_metric(row['precision'])}   "
            f"{fmt_metric(row['f1'])}   {row['fpr']:.4%}"
        )
    for group, data in payload["by_group"].items():
        row = data[f"fpr_{payload['chosen_fpr']}"]
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
        name for name in sources if source_capture_date(name) <= args.train_end
    ]
    validation = [name for name in sources if args.val_source.lower() in name.lower()]
    if len(validation) != 1:
        raise ValueError("--val-source phải khớp đúng một source_file.")
    validation_source = validation[0]
    train_sources = [name for name in train_sources if name != validation_source]
    if set(train_sources) & (set(test_sources) | set(validation)):
        raise ValueError("Train/validation/test đang chồng lấn source_file.")

    train_frame = read_sources(args, train_sources, args.max_rows, args.random_state)
    benign_train = train_frame[train_frame["target"].astype(int).eq(0)]
    validation_frame = read_sources(
        args, [validation_source], args.max_val_rows, args.random_state + 20_000
    )
    test_frame = read_sources(
        args, test_sources, args.max_test_rows, args.random_state + 10_000
    )
    features = select_numeric_features(benign_train)
    pipeline = fit_detector(benign_train, features, args)

    benign_mask = validation_frame["target"].astype(int).eq(0).to_numpy()
    validation_scores = anomaly_scores(pipeline, validation_frame, features)[benign_mask]
    thresholds = thresholds_from_benign(validation_scores, args.target_fpr)
    scores = anomaly_scores(pipeline, test_frame, features)
    y_true = test_frame["target"].astype(int).to_numpy()
    chosen_threshold = thresholds[args.threshold_fpr]

    bundle = {
        "pipeline": pipeline,
        "feature_columns": features,
        "task": "anomaly_detection",
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
        },
    }
    model_path = Path(args.model)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)

    payload = {
        "mode": "day",
        "detector": "IsolationForest",
        "model": str(model_path),
        "train_sources": train_sources,
        "validation_source": validation_source,
        "test_sources": test_sources,
        "target_fprs": list(args.target_fpr),
        "chosen_fpr": args.threshold_fpr,
        "thresholds": {str(key): float(value) for key, value in thresholds.items()},
        "default_0": detection_at(y_true, scores, 0.0),
        "calibrated": detection_at(y_true, scores, chosen_threshold),
    }
    save_json(payload, RESULT_DIR / "anomaly_day.json")

    print(f"Đã lưu model: {model_path.resolve()}")
    print(f"Ngày validation: {validation_source}")
    print(f"Ngưỡng đã chọn: {chosen_threshold:.6f} (FPR mục tiêu {args.threshold_fpr:.1%})")
    print(
        f"Test @default    recall={payload['default_0']['recall']:.4f} "
        f"f1={payload['default_0']['f1']:.4f} fpr={payload['default_0']['fpr']:.4%}"
    )
    print(
        f"Test @calibrated recall={payload['calibrated']['recall']:.4f} "
        f"f1={payload['calibrated']['f1']:.4f} fpr={payload['calibrated']['fpr']:.4%}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["lodo", "day"], default="lodo")
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--model", default=str(DEFAULT_ANOMALY_MODEL))
    parser.add_argument("--trees", type=int, default=200)
    parser.add_argument("--max-samples", type=int, default=4096)
    parser.add_argument("--scaler", choices=["quantile", "standard", "robust"], default="quantile")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--max-rows", type=int, default=500_000)
    parser.add_argument("--max-val-rows", type=int, default=150_000)
    parser.add_argument("--max-test-rows", type=int, default=200_000)
    parser.add_argument(
        "--target-fpr", type=float, nargs="*", default=list(TARGET_FPRS)
    )
    parser.add_argument("--threshold-fpr", type=float, default=0.01)
    parser.add_argument("--train-end", type=date.fromisoformat, default=date(2018, 2, 22))
    parser.add_argument("--test-start", type=date.fromisoformat, default=date(2018, 2, 28))
    parser.add_argument("--val-source", default="Web2")
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
