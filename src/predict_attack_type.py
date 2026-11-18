"""Predict the attack type of flows in a CSV/Parquet file.

Example:

    python src/predict_attack_type.py ^
        --input flows.csv ^
        --model models/attack_type_model.joblib ^
        --output results/attack_types.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.common import MODEL_DIR, RESULT_DIR, load_bundle, prepare_features, read_dataframe
except ModuleNotFoundError:  # Allows: python src/predict_attack_type.py
    from common import MODEL_DIR, RESULT_DIR, load_bundle, prepare_features, read_dataframe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL_DIR / "attack_type_model.joblib",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULT_DIR / "attack_types.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = load_bundle(args.model)
    if bundle.get("task") != "attack_type_prediction":
        raise ValueError(f"{args.model} không phải attack-type model.")
    frame = read_dataframe(args.input)
    X = prepare_features(frame, bundle["feature_columns"])
    probabilities = bundle["pipeline"].predict_proba(X)
    classes = [str(value) for value in bundle["pipeline"].named_steps["classifier"].classes_]
    top_k = max(1, min(int(args.top_k), len(classes)))

    result = frame.copy()
    result["attack_type"] = [classes[int(index)] for index in np.argmax(probabilities, axis=1)]
    result["attack_type_confidence"] = probabilities.max(axis=1).astype(float)
    order = np.argsort(-probabilities, axis=1)
    for rank in range(top_k):
        indices = order[:, rank]
        result[f"attack_type_top_{rank + 1}"] = [classes[int(index)] for index in indices]
        result[f"attack_type_top_{rank + 1}_prob"] = probabilities[np.arange(len(indices)), indices]
    result["attack_type_model_version"] = str(bundle.get("version") or "unknown")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"Đã ghi {len(result):,} dòng vào: {args.output.resolve()}")
    print(result["attack_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
