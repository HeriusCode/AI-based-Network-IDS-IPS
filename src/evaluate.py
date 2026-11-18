"""Evaluate a detection model using the holdout strategy stored in its bundle."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import RocCurveDisplay
from sklearn.model_selection import train_test_split

try:
    from src.common import (
        DETECTION_MODEL,
        PROCESSED_DATA,
        RESULT_DIR,
        binary_metrics,
        ensure_output_dirs,
        load_bundle,
        prepare_features,
        read_sampled_dataframe,
        save_json,
    )
except ModuleNotFoundError:
    from common import (
        DETECTION_MODEL,
        PROCESSED_DATA,
        RESULT_DIR,
        binary_metrics,
        ensure_output_dirs,
        load_bundle,
        prepare_features,
        read_sampled_dataframe,
        save_json,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--model", default=str(DETECTION_MODEL))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    bundle = load_bundle(Path(args.model))
    split_strategy = str(bundle.get("split_strategy", "random"))

    if split_strategy == "day":
        test_sources = bundle.get("test_sources", [])
        if not test_sources:
            raise ValueError("Model day-split không chứa danh sách test_sources.")
        test_frame = read_sampled_dataframe(
            args.data,
            bundle.get("max_test_rows", 200_000),
            int(bundle.get("random_state", 42)) + 10_000,
            filter_values={"source_file": test_sources},
        )
        X_test = prepare_features(test_frame, bundle["feature_columns"])
        y_test = test_frame["target"].astype(int)
    else:
        frame = read_sampled_dataframe(
            args.data,
            bundle.get("max_rows", 500_000),
            int(bundle.get("random_state", 42)),
        )
        if "target" not in frame:
            raise ValueError("Dữ liệu đánh giá phải có cột target.")
        X = prepare_features(frame, bundle["feature_columns"])
        y = frame["target"].astype(int)
        _, X_test, _, y_test = train_test_split(
            X,
            y,
            test_size=float(bundle.get("test_size", 0.2)),
            random_state=int(bundle.get("random_state", 42)),
            stratify=y,
        )

    pipeline = bundle["pipeline"]
    predictions = pipeline.predict(X_test)
    scores = pipeline.predict_proba(X_test)[:, 1]
    metrics = binary_metrics(y_test, predictions, scores)
    metrics.update(
        {
            "split_strategy": split_strategy,
            "test_rows": int(len(X_test)),
            "test_sources": bundle.get("test_sources", []),
        }
    )
    if split_strategy == "day":
        sources = test_frame["source_file"].reset_index(drop=True)
        labels = test_frame["Label"].astype(str).reset_index(drop=True)
        actual = y_test.reset_index(drop=True)
        per_source = {}
        for source in sorted(sources.unique()):
            mask = sources.eq(source).to_numpy()
            source_metrics = binary_metrics(actual[mask], predictions[mask], scores[mask])
            per_source[source] = {
                key: source_metrics[key]
                for key in ("accuracy", "precision", "recall", "f1", "roc_auc")
            }
            per_source[source]["rows"] = int(mask.sum())
        metrics["per_source"] = per_source
        metrics["per_label_detection"] = {
            label: {
                "rows": int(mask.sum()),
                "predicted_attack_rate": float(predictions[mask].mean()),
                "mean_attack_probability": float(scores[mask].mean()),
            }
            for label in sorted(labels.unique())
            if (mask := labels.eq(label).to_numpy()).any()
        }
    save_json(metrics, RESULT_DIR / "evaluation_metrics.json")
    save_json(metrics, RESULT_DIR / f"evaluation_metrics_{split_strategy}.json")

    fig, axis = plt.subplots(figsize=(5.5, 4.5))
    sns.heatmap(
        np.asarray(metrics["confusion_matrix"]),
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["BENIGN", "ATTACK"],
        yticklabels=["BENIGN", "ATTACK"],
        ax=axis,
    )
    axis.set(
        xlabel="Dự đoán",
        ylabel="Thực tế",
        title=f"Confusion matrix ({split_strategy} split)",
    )
    fig.tight_layout()
    fig.savefig(RESULT_DIR / "confusion_matrix.png", dpi=160)
    fig.savefig(RESULT_DIR / f"confusion_matrix_{split_strategy}.png", dpi=160)
    plt.close(fig)

    if y_test.nunique() == 2:
        fig, axis = plt.subplots(figsize=(5.5, 4.5))
        RocCurveDisplay.from_predictions(y_test, scores, ax=axis)
        axis.set_title(f"ROC curve ({split_strategy} split)")
        fig.tight_layout()
        fig.savefig(RESULT_DIR / "roc_curve.png", dpi=160)
        fig.savefig(RESULT_DIR / f"roc_curve_{split_strategy}.png", dpi=160)
        plt.close(fig)

    print(f"Chiến lược chia: {split_strategy}")
    print(f"Test rows: {len(X_test):,}")
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1-score: {metrics['f1']:.4f}")
    print(f"ROC-AUC:  {metrics['roc_auc']:.4f}")
    print(f"Kết quả:  {RESULT_DIR}")


if __name__ == "__main__":
    main()
