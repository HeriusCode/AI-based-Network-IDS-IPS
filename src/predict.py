"""Run binary intrusion predictions for records in a CSV file.

Supports both supervised detection bundles (``predict_proba``) and unsupervised
anomaly bundles (``decision_function``). The decision threshold is read from the
bundle (``decision_threshold``) so calibrated models behave correctly, and can be
overridden from the command line.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.common import (
        DETECTION_MODEL,
        RESULT_DIR,
        load_bundle,
        prepare_features,
        read_dataframe,
    )
except ModuleNotFoundError:
    from common import (
        DETECTION_MODEL,
        RESULT_DIR,
        load_bundle,
        prepare_features,
        read_dataframe,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=RESULT_DIR / "predictions.csv")
    parser.add_argument("--model", type=Path, default=DETECTION_MODEL)
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Ghi đè decision_threshold đã lưu trong model.",
    )
    return parser.parse_args()


def compute_scores(bundle: dict, X: pd.DataFrame) -> np.ndarray:
    """Return attack scores where larger always means more suspicious."""
    pipeline = bundle["pipeline"]
    if bundle.get("task") == "anomaly_detection":
        return -pipeline.decision_function(X)
    return pipeline.predict_proba(X)[:, 1]


def main() -> None:
    args = parse_args()
    bundle = load_bundle(args.model)
    frame = read_dataframe(args.input)
    X = prepare_features(frame, bundle["feature_columns"])
    scores = compute_scores(bundle, X)
    threshold = (
        float(args.threshold)
        if args.threshold is not None
        else float(bundle.get("decision_threshold", 0.5))
    )
    labels = (scores >= threshold).astype(int)

    result = frame.copy()
    result["prediction"] = labels
    result["prediction_label"] = ["ATTACK" if value == 1 else "BENIGN" for value in labels]
    if bundle.get("task") == "anomaly_detection":
        result["anomaly_score"] = scores
    else:
        result["attack_probability"] = scores
    result["threshold"] = threshold

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(
        f"Đã ghi {len(result):,} dự đoán vào: {args.output.resolve()} "
        f"(threshold={threshold:.6f})"
    )


if __name__ == "__main__":
    main()
