"""Score flows with the raw + robust fusion architecture.

This is the runnable counterpart of ``results/architecture_decision.md``.  It
loads the two holdout bundles, scores each day/batch, fuses the scores, and
returns a ranked alert queue at a chosen top-q or top-k budget.

The robust branch recomputes the same per-day signed-log/median-IQR transform
used during training.  It therefore expects a batch that represents one day (or
one meaningful traffic window); do not mix unrelated days in a single batch
when ``source_file`` is absent.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

try:
    from src.common import (
        MODEL_DIR,
        RESULT_DIR,
        load_bundle,
        prepare_features,
        read_dataframe,
    )
except ModuleNotFoundError:  # Allows: python src/predict_fusion.py
    from common import (
        MODEL_DIR,
        RESULT_DIR,
        load_bundle,
        prepare_features,
        read_dataframe,
    )


def signed_log(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.log1p(np.abs(values))


def robust_transform(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Match train_normalized.robust_normalise without requiring a target."""
    values = frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    logged = signed_log(values)
    median = np.nanmedian(logged, axis=0)
    q1 = np.nanquantile(logged, 0.25, axis=0)
    q3 = np.nanquantile(logged, 0.75, axis=0)
    scale = (q3 - q1) / 1.349
    std = np.nanstd(logged, axis=0)
    scale = np.where(scale > 1e-9, scale, np.where(std > 1e-9, std, 1.0))
    normalised = np.clip((logged - median) / scale, -12.0, 12.0)
    return pd.DataFrame(normalised, columns=features, index=frame.index)


def fuse_scores(
    raw_scores: np.ndarray,
    robust_scores: np.ndarray,
    method: str,
) -> np.ndarray:
    if method == "mean":
        return (raw_scores + robust_scores) / 2.0
    if method == "max":
        return np.maximum(raw_scores, robust_scores)
    if method == "rank_mean":
        count = len(raw_scores)
        left = rankdata(raw_scores, method="average") / count
        right = rankdata(robust_scores, method="average") / count
        return (left + right) / 2.0
    if method == "rank_min_tb":
        count = len(raw_scores)
        left = rankdata(raw_scores, method="average") / count
        right = rankdata(robust_scores, method="average") / count
        return np.minimum(left, right) + 1e-6 * ((left + right) / 2.0)
    raise ValueError(f"Không hỗ trợ fusion method: {method}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULT_DIR / "fusion_alerts.csv",
    )
    parser.add_argument(
        "--raw-model",
        type=Path,
        default=MODEL_DIR / "holdout_fusion_raw.joblib",
    )
    parser.add_argument(
        "--robust-model",
        type=Path,
        default=MODEL_DIR / "holdout_fusion_robust.joblib",
    )
    parser.add_argument(
        "--fusion-method",
        choices=("mean", "max", "rank_mean", "rank_min_tb"),
        default="rank_min_tb",
    )
    parser.add_argument(
        "--budget-q",
        type=float,
        default=0.05,
        help="Tỷ lệ flow alert mỗi nhóm/ngày (mặc định 5%%).",
    )
    parser.add_argument(
        "--budget-k",
        type=int,
        default=None,
        help="Số alert tuyệt đối mỗi nhóm/ngày; ghi đè --budget-q.",
    )
    parser.add_argument(
        "--group-column",
        default="source_file",
        help="Cột nhóm (mặc định source_file). Nếu không có, coi cả file là một nhóm.",
    )
    parser.add_argument(
        "--alerts-only",
        action="store_true",
        help="Chỉ ghi các dòng có alert=1.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.budget_q <= 0 and args.budget_k is None:
        raise ValueError("--budget-q phải > 0 hoặc dùng --budget-k.")
    raw_bundle = load_bundle(args.raw_model)
    robust_bundle = load_bundle(args.robust_model)
    frame = read_dataframe(args.input)
    if frame.empty:
        raise ValueError("Input rỗng.")

    raw_features = list(raw_bundle["feature_columns"])
    robust_features = list(robust_bundle["feature_columns"])
    group_column = args.group_column if args.group_column in frame.columns else None
    if group_column:
        groups = [(str(key), part) for key, part in frame.groupby(group_column, sort=False)]
    else:
        groups = [("__all__", frame)]

    results = []
    for group_name, group in groups:
        raw_x = prepare_features(group, raw_features)
        robust_x = prepare_features(group, robust_features)
        raw_scores = raw_bundle["pipeline"].predict_proba(raw_x)[:, 1]
        robust_scores = robust_bundle["pipeline"].predict_proba(
            robust_transform(robust_x, robust_features)
        )[:, 1]
        fused = fuse_scores(raw_scores, robust_scores, args.fusion_method)

        count = len(group)
        budget = (
            max(1, int(args.budget_k))
            if args.budget_k is not None
            else max(1, math.ceil(args.budget_q * count))
        )
        budget = min(count, budget)
        order = np.argsort(-fused, kind="mergesort")
        alert_rank = np.empty(count, dtype=np.int32)
        alert_rank[order] = np.arange(1, count + 1, dtype=np.int32)

        result = group.copy()
        result["fusion_group"] = group_name
        result["raw_score"] = raw_scores
        result["robust_score"] = robust_scores
        result["fusion_score"] = fused
        result["alert_rank"] = alert_rank
        result["alert"] = (alert_rank <= budget).astype(np.int8)
        result["budget_k"] = budget
        result["budget_q"] = args.budget_q
        result["fusion_method"] = args.fusion_method
        results.append(result)
        print(
            f"{group_name}: rows={count:,} alerts={budget:,} "
            f"({budget / count:.2%})"
        )

    output = pd.concat(results, ignore_index=True)
    if args.alerts_only:
        output = output[output["alert"].eq(1)].sort_values(
            ["fusion_group", "alert_rank"]
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(
        f"Đã ghi {len(output):,} dòng vào {args.output.resolve()} "
        f"(method={args.fusion_method})"
    )


if __name__ == "__main__":
    main()
