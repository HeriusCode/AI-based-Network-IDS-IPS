"""Train binary IDS detection with day-based, leave-one-day-out, or random holdout."""

from __future__ import annotations

import argparse
import gc
import re
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

try:
    from src.common import (
        DETECTION_MODEL,
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        binary_metrics,
        ensure_output_dirs,
        parquet_source_files,
        prepare_features,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )
except ModuleNotFoundError:
    from common import (
        DETECTION_MODEL,
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        binary_metrics,
        ensure_output_dirs,
        parquet_source_files,
        prepare_features,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )


DATE_PATTERN = re.compile(r"-(\d{2})-(\d{2})-(\d{4})_")
LODO_MODEL_DIR = MODEL_DIR / "lodo"
KEY_METRICS = ("accuracy", "precision", "recall", "f1", "roc_auc")


def source_capture_date(source_file: str) -> date:
    match = DATE_PATTERN.search(source_file)
    if not match:
        raise ValueError(f"Không đọc được ngày từ source_file: {source_file}")
    day, month, year = (int(value) for value in match.groups())
    return date(year, month, day)


def day_source_split(
    data_path: str | Path,
    train_end: date,
    test_start: date,
) -> tuple[list[str], list[str]]:
    sources = parquet_source_files(data_path)
    train_sources = [name for name in sources if source_capture_date(name) <= train_end]
    test_sources = [name for name in sources if source_capture_date(name) >= test_start]
    if not train_sources or not test_sources:
        raise ValueError("Không tìm được đủ source_file cho train/test theo ngày đã chọn.")
    if set(train_sources) & set(test_sources):
        raise ValueError("Train và test theo ngày đang bị chồng lấn.")
    return train_sources, test_sources


def label_distribution(frame: pd.DataFrame) -> dict[str, int]:
    return {str(label): int(count) for label, count in frame["Label"].value_counts().items()}


def attack_labels(frame: pd.DataFrame) -> set[str]:
    attacks = frame["target"].astype(int).eq(1)
    return {str(label) for label in frame.loc[attacks, "Label"].unique()}


# Ordered rules: "ddos" must be checked before "dos" because "ddos" contains "dos".
FAMILY_RULES = (
    ("ddos", "DDoS"),
    ("dos", "DoS"),
    ("ftp-bruteforce", "BruteForce"),
    ("ssh-bruteforce", "BruteForce"),
    ("brute force -web", "Web"),
    ("brute force -xss", "Web"),
    ("sql injection", "Web"),
    ("infilteration", "Infiltration"),
    ("bot", "Bot"),
)


def attack_family(label: str) -> str:
    """Map a dataset label to a coarse attack family."""
    text = " ".join(str(label).strip().lower().split())
    for needle, family in FAMILY_RULES:
        if needle in text:
            return family
    return "Other"


def create_pipeline(args: argparse.Namespace) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=args.trees,
                    random_state=args.random_state,
                    n_jobs=args.n_jobs,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )


def fit_and_test(
    pipeline: Pipeline,
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    features: list[str],
) -> dict[str, object]:
    if not features:
        raise ValueError("Không tìm thấy đặc trưng số hợp lệ.")
    X_train = train_frame[features].replace([np.inf, -np.inf], np.nan)
    y_train = train_frame["target"].astype(int)
    X_test = prepare_features(test_frame, features)
    y_test = test_frame["target"].astype(int)
    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)
    scores = pipeline.predict_proba(X_test)[:, 1]
    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "predictions": predictions,
        "scores": scores,
    }


def binary_bundle(
    pipeline: Pipeline,
    features: list[str],
    args: argparse.Namespace,
    train_sources: list[str],
    test_sources: list[str],
) -> dict[str, object]:
    return {
        "pipeline": pipeline,
        "feature_columns": features,
        "task": "binary_detection",
        "classes": {0: "BENIGN", 1: "ATTACK"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split_strategy": "day",
        "random_state": args.random_state,
        "test_size": args.test_size,
        "max_rows": args.max_rows,
        "max_test_rows": args.max_test_rows,
        "train_sources": train_sources,
        "test_sources": test_sources,
    }


def load_fold_frames(
    args: argparse.Namespace,
    train_sources: list[str],
    test_sources: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_frame = read_sampled_dataframe(
        args.data,
        args.max_rows,
        args.random_state,
        filter_values={"source_file": train_sources},
    )
    test_frame = read_sampled_dataframe(
        args.data,
        args.max_test_rows,
        args.random_state + 10_000,
        filter_values={"source_file": test_sources},
    )
    return train_frame, test_frame


def mean_std(values: list[float | None]) -> dict[str, float | int | None]:
    usable = [value for value in values if value is not None]
    if not usable:
        return {"mean": None, "std": None, "folds": 0}
    return {
        "mean": float(np.mean(usable)),
        "std": float(np.std(usable)),
        "folds": len(usable),
    }


def summarise_group(folds: list[dict[str, object]], arrays: list[dict[str, np.ndarray]]) -> dict[str, object]:
    if not arrays:
        return {
            "folds": [],
            "rows": 0,
            "attack_rows": 0,
            "recall": None,
            "precision": None,
            "f1": None,
            "accuracy": None,
            "roc_auc": None,
            "confusion_matrix": [],
            "best_threshold": {
                "threshold": None,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
            },
        }
    actual = np.concatenate([item["actual"] for item in arrays])
    predicted = np.concatenate([item["predicted"] for item in arrays])
    scores = np.concatenate([item["scores"] for item in arrays])
    metrics = binary_metrics(actual, predicted, scores)
    return {
        "folds": [str(fold["source_file"]) for fold in folds],
        "rows": int(len(actual)),
        "attack_rows": int(actual.sum()),
        "recall": metrics["recall"],
        "precision": metrics["precision"],
        "f1": metrics["f1"],
        "accuracy": metrics["accuracy"],
        "roc_auc": metrics["roc_auc"],
        "confusion_matrix": metrics["confusion_matrix"],
        "best_threshold": threshold_sweep(actual, scores),
    }


def fold_metrics(
    fold_index: int,
    source: str,
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    result: dict[str, object],
) -> dict[str, object]:
    y_test = result["y_test"]
    predictions = np.asarray(result["predictions"])
    scores = np.asarray(result["scores"])
    metrics = binary_metrics(y_test, predictions, scores)
    train_attacks = attack_labels(train_frame)
    train_families = {attack_family(label) for label in train_attacks}
    test_labels = label_distribution(test_frame)
    test_attacks = set(attack_labels(test_frame))
    test_families = {attack_family(label) for label in test_attacks}

    labels = test_frame["Label"].astype(str).reset_index(drop=True)
    predicted_series = pd.Series(predictions)
    score_series = pd.Series(scores)
    per_label: dict[str, dict[str, object]] = {}
    for label in sorted(labels.unique()):
        mask = labels.eq(label)
        family = attack_family(label)
        per_label[label] = {
            "rows": int(mask.sum()),
            "predicted_attack_rate": float(predicted_series[mask].mean()),
            "mean_attack_probability": float(score_series[mask].mean()),
            "seen_in_train": label in train_attacks,
            "family": family,
            "family_seen_in_train": family in train_families,
        }

    return {
        "fold": fold_index,
        "source_file": source,
        "capture_date": source_capture_date(source).isoformat(),
        "train_rows": int(len(train_frame)),
        "test_rows": int(len(test_frame)),
        "attack_rows": int(y_test.sum()),
        "attack_rate": float(y_test.mean()),
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "roc_auc": metrics["roc_auc"],
        "confusion_matrix": metrics["confusion_matrix"],
        "train_attack_labels": sorted(train_attacks),
        "test_attack_labels": sorted(test_attacks),
        "unseen_attack_labels": sorted(test_attacks - train_attacks),
        "train_families": sorted(train_families),
        "test_families": sorted(test_families),
        "unseen_families": sorted(test_families - train_families),
        "best_threshold": threshold_sweep(y_test, scores),
        "test_label_distribution": test_labels,
        "per_label": per_label,
    }


def fmt_metric(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def threshold_sweep(
    y_true: np.ndarray,
    scores: np.ndarray,
    low: float = 0.01,
    high: float = 0.95,
    step: float = 0.01,
) -> dict[str, float | None]:
    """Pick the threshold that maximises F1 on this fold (diagnostic, not deployment)."""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores)
    best: dict[str, float | None] = {
        "threshold": None,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }
    for threshold in np.arange(low, high + step / 2, step):
        predicted = scores >= threshold
        tp = int(np.sum(predicted & (y_true == 1)))
        fp = int(np.sum(predicted & (y_true == 0)))
        fn = int(np.sum(~predicted & (y_true == 1)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best["f1"]:
            best = {
                "threshold": float(round(threshold, 2)),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
            }
    return best


def write_lodo_report(
    fold_rows: list[dict[str, object]],
    aggregate: dict[str, object],
    path: Path,
) -> None:
    label_seen = aggregate["label_seen"]
    label_unseen = aggregate["label_unseen"]
    family_seen = aggregate["family_seen"]
    family_unseen = aggregate["family_unseen"]
    all_rows = aggregate["all"]
    macro = aggregate["macro"]

    def group_line(name: str, group: dict[str, object]) -> str:
        best = group["best_threshold"]
        threshold_text = "-" if best["threshold"] is None else f"{best['threshold']:.2f}"
        return (
            f"| {name} | {len(group['folds'])} | {group['rows']:,} | {group['attack_rows']:,} | "
            f"{fmt_metric(group['recall'])} | {fmt_metric(group['precision'])} | "
            f"{fmt_metric(group['f1'])} | {fmt_metric(group['roc_auc'])} | "
            f"{best['f1']:.4f} | {threshold_text} |"
        )

    lines = [
        "# Leave-one-day-out cho model detection",
        "",
        "## Thiết lập",
        "",
        f"- Số fold: {len(fold_rows)} (mỗi fold giữ đúng một ngày thu thập làm test).",
        f"- Train mỗi fold: tối đa {fold_rows[0]['train_rows']:,} flow lấy từ các ngày còn lại.",
        f"- Test mỗi fold: tối đa {fold_rows[0]['test_rows']:,} flow của ngày bị giữ lại.",
        "- Không fold nào dùng chung `source_file` giữa train và test.",
        "- `label_seen` / `label_unseen`: xét theo nhãn cụ thể (ví dụ "
        "`DDoS attacks-LOIC-HTTP`).",
        "- `family_seen` / `family_unseen`: xét theo họ tấn công (DDoS, DoS, BruteForce, "
        "Web, Bot, Infiltration), phản ánh việc mô hình đã thấy hành vi tương tự hay chưa.",
        "",
        "## Kết quả từng fold",
        "",
        "| Fold | Ngày | Test rows | Attack rows | Recall | Precision | F1 | ROC-AUC | F1 tốt nhất | Ngưỡng | Nhãn mới | Họ mới |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in fold_rows:
        unseen_labels = ", ".join(row["unseen_attack_labels"]) or "-"
        unseen_families = ", ".join(row["unseen_families"]) or "-"
        best = row["best_threshold"]
        lines.append(
            f"| {row['fold']} | {row['capture_date']} | {row['test_rows']:,} | "
            f"{row['attack_rows']:,} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {fmt_metric(row['roc_auc'])} | {best['f1']:.4f} | "
            f"{'-' if best['threshold'] is None else best['threshold']:.2f} | "
            f"{unseen_labels} | {unseen_families} |"
        )

    lines.extend(
        [
            "",
            "## Tổng hợp",
            "",
            "| Nhóm fold | Số fold | Test rows | Attack rows | Recall | Precision | F1 | ROC-AUC | F1 tốt nhất | Ngưỡng |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            group_line("label_seen", label_seen),
            group_line("label_unseen", label_unseen),
            group_line("family_seen", family_seen),
            group_line("family_unseen", family_unseen),
            group_line("all", all_rows),
            "",
            "## Trung bình theo fold",
            "",
            f"- Recall: {fmt_metric(macro['recall']['mean'])} ± "
            f"{fmt_metric(macro['recall']['std'])}",
            f"- F1: {fmt_metric(macro['f1']['mean'])} ± {fmt_metric(macro['f1']['std'])}",
            f"- ROC-AUC: {fmt_metric(macro['roc_auc']['mean'])} ± "
            f"{fmt_metric(macro['roc_auc']['std'])}",
            "",
            "## Diễn giải",
            "",
        ]
    )

    best_fold = max(fold_rows, key=lambda row: row["f1"])
    worst_fold = min(fold_rows, key=lambda row: row["f1"])
    lines.append(
        "Kết quả rất không đồng đều: fold tốt nhất là "
        f"{best_fold['capture_date']} (F1 {best_fold['f1']:.4f}, recall "
        f"{best_fold['recall']:.4f}), fold kém nhất là {worst_fold['capture_date']} "
        f"(F1 {worst_fold['f1']:.4f}, recall {worst_fold['recall']:.4f}). Vì vậy không nên "
        "chỉ đọc một con số trung bình."
    )

    if family_seen["folds"] and family_unseen["folds"]:
        lines.append("")
        lines.append(
            "Ở mức họ tấn công, khi ngày test chỉ chứa họ đã thấy (`family_seen`): "
            f"recall {family_seen['recall']:.2%}, F1 {family_seen['f1']:.4f}, "
            f"ROC-AUC {family_seen['roc_auc']:.4f}. Khi có họ hoàn toàn mới "
            f"(`family_unseen`): recall {family_unseen['recall']:.2%}, "
            f"F1 {family_unseen['f1']:.4f}, ROC-AUC {family_unseen['roc_auc']:.4f}. "
            "Chênh lệch này là bằng chứng định lượng cho mức độ phụ thuộc vào họ tấn công "
            "đã thấy."
        )

    if label_seen["folds"] and label_unseen["folds"]:
        lines.append(
            f"Ở mức nhãn cụ thể, `label_seen` đạt recall {label_seen['recall']:.2%} và "
            f"`label_unseen` đạt {label_unseen['recall']:.2%}. Lưu ý `label_unseen` vẫn có "
            "thể cao nếu nhãn mới nhưng họ tấn công đã thấy (ví dụ DDoS-LOIC-HTTP trong "
            "train giúp nhận ra DDOS-HOIC/LOIC-UDP)."
        )

    best_f1_mean = float(np.mean([row["best_threshold"]["f1"] for row in fold_rows]))
    lines.extend(
        [
            "",
            "Về ngưỡng: ROC-AUC trung bình theo fold là "
            f"{fmt_metric(macro['roc_auc']['mean'])} nhưng F1 tại ngưỡng 0,5 chỉ "
            f"{fmt_metric(macro['f1']['mean'])}. Nếu chọn ngưỡng tốt nhất cho từng fold, F1 "
            f"trung bình lên tới {best_f1_mean:.4f} (đây là cận trên lạc quan vì ngưỡng được "
            "chọn trên chính tập test). Điều này cho thấy mô hình còn tín hiệu xếp hạng nhưng "
            "xác suất bị lệch khi chuyển sang ngày mới, nên ngưỡng 0,5 cố định không phù hợp "
            "khi triển khai; cần calibration trên một ngày validation riêng.",
        ]
    )

    inverted = [
        row for row in fold_rows if row["roc_auc"] is not None and row["roc_auc"] < 0.5
    ]
    if inverted:
        dates = ", ".join(str(row["capture_date"]) for row in inverted)
        lines.append(
            f"Có {len(inverted)} fold ROC-AUC dưới 0,5 ({dates}), nghĩa là thứ hạng bị đảo: "
            "flow tấn công nhận điểm thấp hơn benign. Đây là lỗi nghiêm trọng hơn việc chỉ "
            "lệch ngưỡng."
        )

    if family_unseen["folds"] and family_unseen["recall"] is not None:
        if family_unseen["recall"] < 0.3:
            lines.append(
                f"Với họ tấn công hoàn toàn mới, recall chỉ {family_unseen['recall']:.2%} tại "
                "ngưỡng 0,5. Random Forest là mô hình closed-set nên không thể bắt họ mới chỉ "
                "bằng dữ liệu có nhãn; cần bổ sung phát hiện bất thường không giám sát "
                "(Isolation Forest, autoencoder) hoặc cơ chế open-set/novelty detection."
            )

    lines.extend(
        [
            "",
            "Lưu ý: accuracy không nên dùng làm chỉ số chính vì Benign chiếm đa số trong mọi "
            "fold; recall/F1/ROC-AUC của lớp ATTACK mới phản ánh năng lực phát hiện.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_lodo(args: argparse.Namespace) -> None:
    all_sources = parquet_source_files(args.data)
    sources = all_sources
    if args.only_sources:
        keys = [key.lower() for key in args.only_sources]
        sources = [name for name in all_sources if any(key in name.lower() for key in keys)]
    if not sources:
        raise ValueError("Không có source_file nào khớp bộ lọc --only-sources.")
    if len(all_sources) < 2:
        raise ValueError("Cần ít nhất hai source_file để chạy leave-one-day-out.")

    fold_rows: list[dict[str, object]] = []
    fold_arrays: list[dict[str, np.ndarray]] = []
    groups: dict[str, tuple[list[dict[str, object]], list[dict[str, np.ndarray]]]] = {
        "label_seen": ([], []),
        "label_unseen": ([], []),
        "family_seen": ([], []),
        "family_unseen": ([], []),
    }
    if args.save_fold_models:
        LODO_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for index, source in enumerate(sources, 1):
        train_sources = [name for name in all_sources if name != source]
        print(f"[{index}/{len(sources)}] Giữ lại ngày test: {source}")
        train_frame, test_frame = load_fold_frames(args, train_sources, [source])
        features = select_numeric_features(train_frame)
        if not features:
            raise ValueError("Không tìm thấy đặc trưng số hợp lệ.")

        pipeline = create_pipeline(args)
        result = fit_and_test(pipeline, train_frame, test_frame, features)
        y_test = result["y_test"]
        if y_test.nunique() < 2:
            raise ValueError(f"Fold {source} chỉ có một lớp trong tập test.")

        row = fold_metrics(index, source, train_frame, test_frame, result)
        fold_rows.append(row)
        arrays = {
            "actual": np.asarray(y_test),
            "predicted": np.asarray(result["predictions"]),
            "scores": np.asarray(result["scores"]),
        }
        fold_arrays.append(arrays)

        label_group = "label_unseen" if row["unseen_attack_labels"] else "label_seen"
        family_group = "family_unseen" if row["unseen_families"] else "family_seen"
        for group in (label_group, family_group):
            groups[group][0].append(row)
            groups[group][1].append(arrays)

        unseen = ", ".join(row["unseen_attack_labels"]) or "-"
        unseen_families = ", ".join(row["unseen_families"]) or "-"
        print(
            f"    test={row['test_rows']:,} attack={row['attack_rows']:,} "
            f"recall={row['recall']:.4f} f1={row['f1']:.4f} "
            f"auc={fmt_metric(row['roc_auc'])} unseen_nhan={unseen} "
            f"unseen_ho={unseen_families}"
        )

        if args.save_fold_models:
            bundle = binary_bundle(pipeline, features, args, train_sources, [source])
            fold_path = LODO_MODEL_DIR / f"fold_{index:02d}_{Path(source).stem}.joblib"
            joblib.dump(bundle, fold_path)
            print(f"    Đã lưu model fold: {fold_path}")

        del train_frame, test_frame, result
        gc.collect()

    macro = {
        key: mean_std([row[key] for row in fold_rows])
        for key in KEY_METRICS
        if any(row[key] is not None for row in fold_rows)
    }
    aggregate = {
        "split_strategy": "lodo",
        "protocol": "leave-one-day-out theo source_file",
        "trees": args.trees,
        "max_rows": args.max_rows,
        "max_test_rows": args.max_test_rows,
        "folds": fold_rows,
        "label_seen": summarise_group(*groups["label_seen"]),
        "label_unseen": summarise_group(*groups["label_unseen"]),
        "family_seen": summarise_group(*groups["family_seen"]),
        "family_unseen": summarise_group(*groups["family_unseen"]),
        "all": summarise_group(fold_rows, fold_arrays),
        "macro": macro,
    }
    save_json(aggregate, RESULT_DIR / "lodo_metrics.json")

    summary_rows = []
    for row in fold_rows:
        best = row["best_threshold"]
        summary = {
            key: (json_list(value) if isinstance(value, list) else value)
            for key, value in row.items()
            if key
            not in {
                "per_label",
                "test_label_distribution",
                "confusion_matrix",
                "best_threshold",
            }
        }
        summary.update(
            {
                "best_f1": best["f1"],
                "best_threshold_value": best["threshold"],
                "best_threshold_recall": best["recall"],
                "best_threshold_precision": best["precision"],
            }
        )
        summary_rows.append(summary)
    pd.DataFrame(summary_rows).to_csv(
        RESULT_DIR / "lodo_summary.csv", index=False, encoding="utf-8-sig"
    )
    write_lodo_report(fold_rows, aggregate, RESULT_DIR / "lodo_report.md")

    print("")
    print(f"Folds: {len(fold_rows)}")
    for name in ("label_seen", "label_unseen", "family_seen", "family_unseen", "all"):
        group = aggregate[name]
        print(
            f"{name:<14} folds={len(group['folds']):>2} attack={group['attack_rows']:>7,} "
            f"recall={fmt_metric(group['recall'])} precision={fmt_metric(group['precision'])} "
            f"f1={fmt_metric(group['f1'])} auc={fmt_metric(group['roc_auc'])}"
        )
    print(f"Báo cáo: {(RESULT_DIR / 'lodo_report.md').resolve()}")


def json_list(values: list[object]) -> str:
    return "; ".join(str(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--model", default=str(DETECTION_MODEL))
    parser.add_argument(
        "--split-strategy",
        choices=["day", "lodo", "random"],
        default="day",
        help="day: giữ một mốc ngày; lodo: leave-one-day-out; random: baseline.",
    )
    parser.add_argument("--train-end", type=date.fromisoformat, default=date(2018, 2, 23))
    parser.add_argument("--test-start", type=date.fromisoformat, default=date(2018, 2, 28))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=500_000,
        help="Số dòng train tối đa mỗi fold; 0 để dùng toàn bộ.",
    )
    parser.add_argument(
        "--max-test-rows",
        type=int,
        default=200_000,
        help="Số dòng test tối đa mỗi fold; 0 để dùng toàn bộ.",
    )
    parser.add_argument(
        "--only-sources",
        nargs="*",
        default=None,
        help="Chỉ chạy các fold có tên source_file chứa một trong các chuỗi này.",
    )
    parser.add_argument(
        "--save-fold-models",
        action="store_true",
        help="Lưu model từng fold vào models/lodo/ (tốn dung lượng).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()

    if args.split_strategy == "lodo":
        run_lodo(args)
        return

    train_sources: list[str] = []
    test_sources: list[str] = []
    if args.split_strategy == "day":
        train_sources, test_sources = day_source_split(
            args.data, args.train_end, args.test_start
        )
        train_frame, test_frame = load_fold_frames(args, train_sources, test_sources)
        features = select_numeric_features(train_frame)
        pipeline = create_pipeline(args)
        result = fit_and_test(pipeline, train_frame, test_frame, features)
    else:
        frame = read_sampled_dataframe(args.data, args.max_rows, args.random_state)
        features = select_numeric_features(frame)
        X = frame[features].replace([np.inf, -np.inf], np.nan)
        y = frame["target"].astype(int)
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=args.test_size,
            random_state=args.random_state,
            stratify=y,
        )
        train_frame = frame.loc[X_train.index]
        test_frame = frame.loc[X_test.index]
        pipeline = create_pipeline(args)
        result = fit_and_test(pipeline, train_frame, test_frame, features)

    if not features:
        raise ValueError("Không tìm thấy đặc trưng số hợp lệ.")
    y_train = result["y_train"]
    y_test = result["y_test"]
    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError("Cả train và test phải có BENIGN (0) lẫn ATTACK (1).")

    predictions = result["predictions"]
    scores = result["scores"]
    metrics = binary_metrics(y_test, predictions, scores)

    train_labels = label_distribution(train_frame)
    test_labels = label_distribution(test_frame)
    trained_attacks = {label for label in train_labels if label.upper() != "BENIGN"}
    tested_attacks = {label for label in test_labels if label.upper() != "BENIGN"}
    metrics.update(
        {
            "split_strategy": args.split_strategy,
            "train_rows": int(len(train_frame)),
            "test_rows": int(len(test_frame)),
            "feature_count": len(features),
            "random_state": args.random_state,
            "train_sources": train_sources,
            "test_sources": test_sources,
            "train_label_distribution": train_labels,
            "test_label_distribution": test_labels,
            "unseen_test_attack_labels": sorted(tested_attacks - trained_attacks),
        }
    )

    bundle = binary_bundle(pipeline, features, args, train_sources, test_sources)
    if args.split_strategy == "random":
        bundle["split_strategy"] = "random"
        bundle["test_size"] = args.test_size
    else:
        bundle["train_end"] = args.train_end.isoformat()
        bundle["test_start"] = args.test_start.isoformat()
    model_path = Path(args.model)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)

    save_json(metrics, RESULT_DIR / "detection_metrics.json")
    save_json(metrics, RESULT_DIR / f"detection_metrics_{args.split_strategy}.json")
    predictions_frame = pd.DataFrame(
        {
            "actual": y_test.to_numpy(),
            "predicted": predictions,
            "attack_probability": scores,
        }
    )
    predictions_frame.to_csv(RESULT_DIR / "detection_test_predictions.csv", index=False)
    predictions_frame.to_csv(
        RESULT_DIR / f"detection_test_predictions_{args.split_strategy}.csv", index=False
    )

    print(f"Đã lưu model: {model_path.resolve()}")
    print(f"Chiến lược chia: {args.split_strategy}")
    print(f"Train: {len(train_frame):,} dòng; test: {len(test_frame):,} dòng")
    if args.split_strategy == "day":
        print(f"Train sources: {len(train_sources)}; test sources: {len(test_sources)}")
        print(f"Tấn công chưa thấy trong train: {sorted(tested_attacks - trained_attacks)}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1-score:  {metrics['f1']:.4f}")
    print(f"ROC-AUC:   {metrics['roc_auc']:.4f}")


if __name__ == "__main__":
    main()
