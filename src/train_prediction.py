"""Train a multiclass Random Forest to predict the attack type of a flow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

try:
    from src.common import (
        PREDICTION_MODEL,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )
except ModuleNotFoundError:
    from common import (
        PREDICTION_MODEL,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--model", default=str(PREDICTION_MODEL))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=0, help="0 = không giới hạn.")
    parser.add_argument("--min-samples-leaf", type=int, default=1)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--version", default="attack-type-1")
    parser.add_argument(
        "--report",
        type=Path,
        default=RESULT_DIR / "attack_type_report.md",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=1_000_000,
        help="Số dòng tối đa dùng huấn luyện; 0 để dùng toàn bộ.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    frame = read_sampled_dataframe(args.data, args.max_rows, args.random_state)
    if "Label" not in frame:
        raise ValueError("Thiếu cột Label. Hãy chạy src/preprocess.py trước.")
    features = select_numeric_features(frame)
    X = frame[features].replace([np.inf, -np.inf], np.nan)
    y = frame["Label"].astype(str)
    counts = y.value_counts()
    if len(counts) < 2:
        raise ValueError("Cần ít nhất hai nhãn để huấn luyện mô hình đa lớp.")
    rare = counts[counts < 2].index.tolist()
    if rare:
        raise ValueError(f"Các nhãn cần ít nhất 2 mẫu để stratify: {rare}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.random_state, stratify=y
    )
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=args.trees,
                    max_depth=args.max_depth or None,
                    min_samples_leaf=args.min_samples_leaf,
                    random_state=args.random_state,
                    n_jobs=-1,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "macro_f1": float(f1_score(y_test, predictions, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_test, predictions, average="weighted", zero_division=0)),
        "classification_report": classification_report(
            y_test, predictions, output_dict=True, zero_division=0
        ),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_count": len(features),
        "version": args.version,
        "split_strategy": "random_stratified",
        "data": str(args.data),
    }
    bundle = {
        "pipeline": pipeline,
        "feature_columns": features,
        "task": "attack_type_prediction",
        "classes": pipeline.named_steps["classifier"].classes_.tolist(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": args.version,
        "split_strategy": "random_stratified",
        "random_state": args.random_state,
        "test_size": args.test_size,
        "max_rows": args.max_rows,
    }
    model_path = Path(args.model)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)
    save_json(metrics, RESULT_DIR / "prediction_metrics.json")

    importances = pd.DataFrame(
        {
            "feature": features,
            "importance": pipeline.named_steps["classifier"].feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    importances.head(30).to_csv(RESULT_DIR / "attack_type_feature_importance.csv", index=False)

    report = metrics["classification_report"]
    lines = [
        "# Attack-type prediction report",
        "",
        f"- Data: `{args.data}`",
        f"- Model: `{model_path}`",
        f"- Version: `{args.version}`",
        f"- Split: random stratified (chỉ dùng cho demo, không phải LODO)",
        f"- Train rows: {len(X_train):,}",
        f"- Test rows: {len(X_test):,}",
        f"- Features: {len(features)}",
        f"- Accuracy: {metrics['accuracy']:.4f}",
        f"- Macro F1: {metrics['macro_f1']:.4f}",
        f"- Weighted F1: {metrics['weighted_f1']:.4f}",
        "",
        "## Per-class",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, values in report.items():
        if not isinstance(values, dict) or "precision" not in values:
            continue
        lines.append(
            f"| {label} | {values['precision']:.4f} | {values['recall']:.4f} | "
            f"{values['f1-score']:.4f} | {int(values['support'])} |"
        )
    lines.extend(
        [
            "",
            "## Lưu ý",
            "",
            "- Đây là phân loại **loại tấn công của flow hiện tại**, không phải dự báo tương lai.",
            "- Random split lạc quan hơn thực tế; muốn đánh giá nghiêm túc phải chia theo ngày (LODO).",
            "- Các lớp hiếm (SQL Injection, FTP-BruteForce) có thể có kết quả 0 do quá ít mẫu.",
        ]
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")

    print(f"Đã lưu model: {model_path.resolve()}")
    print(f"Đã lưu metrics: {(RESULT_DIR / 'prediction_metrics.json').resolve()}")
    print(f"Đã lưu report: {args.report.resolve()}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")


if __name__ == "__main__":
    main()

