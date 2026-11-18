"""Holdout end-to-end check of the raw + robust fusion architecture.

The existing deployable split is used: 7 days for training and the three
unseen days (Botnet, Infil1, Infil2) for testing.  Both models are trained on
exactly the same per-day sample, then evaluated at the chosen 5% flow/day
budget.  This is deliberately separate from the 10-fold LODO reference; it is
a packaging sanity check, not a replacement for LODO.
"""

from __future__ import annotations

import argparse
import gc
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
from scipy.stats import rankdata

try:
    from src.calibrate import read_sources
    from src.common import (
        DETECTION_MODEL,
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        load_bundle,
        prepare_features,
        save_json,
        select_numeric_features,
    )
    from src.evaluate_budget import (
        family_summary,
        recall_ceiling,
        summarize_rows,
        topk_row,
    )
    from src.train_detection import attack_family, source_capture_date
    from src.train_normalized import fit_pipeline, model_columns, prepare_day
except ModuleNotFoundError:  # Allows: python src/evaluate_holdout_fusion.py
    from calibrate import read_sources
    from common import (
        DETECTION_MODEL,
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        load_bundle,
        prepare_features,
        save_json,
        select_numeric_features,
    )
    from evaluate_budget import (
        family_summary,
        recall_ceiling,
        summarize_rows,
        topk_row,
    )
    from train_detection import attack_family, source_capture_date
    from train_normalized import fit_pipeline, model_columns, prepare_day


BUDGET = 0.05
SMALL_BUDGET = 0.01
TREES = 100
RANDOM_STATE = 42
MAX_TRAIN_ROWS = 500_000
MAX_TEST_ROWS_PER_DAY = 200_000


def rank_min_tb(raw_scores: np.ndarray, robust_scores: np.ndarray) -> np.ndarray:
    count = len(raw_scores)
    left = rankdata(raw_scores, method="average") / count
    right = rankdata(robust_scores, method="average") / count
    return np.minimum(left, right) + 1e-6 * ((left + right) / 2.0)


def train_one(
    mode: str,
    train_sources: list[str],
    base_features: list[str],
    per_day: int,
    seed: int,
) -> tuple[object, list[str], int]:
    parts = []
    args = SimpleNamespace(data=PROCESSED_DATA)
    for offset, source in enumerate(train_sources):
        raw = read_sources(args, [source], per_day, seed + offset)
        parts.append(prepare_day(raw, base_features, mode))
        del raw
    frame = pd.concat(parts, ignore_index=True)
    del parts
    features = model_columns(frame)
    pipeline = fit_pipeline(
        frame,
        features,
        SimpleNamespace(trees=TREES, random_state=RANDOM_STATE, n_jobs=-1),
    )
    rows = len(frame)
    del frame
    gc.collect()
    return pipeline, features, rows


def score_frame(bundle: dict, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return bundle["pipeline"].predict_proba(prepare_features(frame, features))[:, 1]


def evaluate_at(
    meta: pd.DataFrame,
    scores: np.ndarray,
    rows: list[dict[str, object]],
    frames: list[pd.DataFrame],
    budget: float,
) -> None:
    frame = meta.copy()
    frame["score"] = scores.astype(np.float32)
    k = max(1, math.ceil(budget * len(frame)))
    rows.append(topk_row(frame, k))
    frames.append(frame)


def fmt(value: float | None, kind: str = "pct") -> str:
    if value is None:
        return "-"
    return f"{value:.2%}" if kind == "pct" else f"{value:.4f}"


def main() -> None:
    ensure_output_dirs()
    raw_bundle = load_bundle(DETECTION_MODEL)
    train_sources = list(raw_bundle["train_sources"])
    test_sources = sorted(
        list(raw_bundle["test_sources"]), key=source_capture_date
    )
    base_features = list(raw_bundle["feature_columns"])
    per_day = max(MAX_TRAIN_ROWS // max(len(train_sources), 1), 5_000)

    print("Train sources:", len(train_sources), "days, per_day=", per_day)
    pipelines: dict[str, object] = {}
    features_by_mode: dict[str, list[str]] = {}
    train_rows: dict[str, int] = {}
    for mode in ("raw", "robust"):
        print(f"Training {mode}...")
        pipeline, features, rows = train_one(
            mode, train_sources, base_features, per_day, RANDOM_STATE
        )
        pipelines[mode] = pipeline
        features_by_mode[mode] = features
        train_rows[mode] = rows
        bundle = {
            "pipeline": pipeline,
            "feature_columns": features,
            "task": "binary_detection",
            "classes": {0: "BENIGN", 1: "ATTACK"},
            "normaliser": mode,
            "train_sources": train_sources,
            "test_sources": test_sources,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "random_state": RANDOM_STATE,
            "trees": TREES,
            "max_train_rows": MAX_TRAIN_ROWS,
        }
        model_path = MODEL_DIR / f"holdout_fusion_{mode}.joblib"
        joblib.dump(bundle, model_path)
        print(f"  saved {model_path.name}; features={len(features)} rows={rows:,}")

    rows_by_variant: dict[str, list[dict[str, object]]] = {
        "raw": [],
        "robust": [],
        "fusion_rank_min_tb": [],
    }
    frames_by_variant: dict[str, list[pd.DataFrame]] = {
        "raw": [],
        "robust": [],
        "fusion_rank_min_tb": [],
    }
    per_day_rows = []

    for index, source in enumerate(test_sources, 1):
        raw = read_sources(
            SimpleNamespace(data=PROCESSED_DATA),
            [source],
            MAX_TEST_ROWS_PER_DAY,
            RANDOM_STATE + 10_000,
        )
        raw_frame = prepare_day(raw, base_features, "raw")
        robust_frame = prepare_day(raw, base_features, "robust")
        raw_scores = score_frame(
            {"pipeline": pipelines["raw"]}, raw_frame, features_by_mode["raw"]
        )
        robust_scores = score_frame(
            {"pipeline": pipelines["robust"]},
            robust_frame,
            features_by_mode["robust"],
        )
        fused = rank_min_tb(raw_scores, robust_scores)
        labels = raw["Label"].astype(str).to_numpy()
        targets = raw["target"].astype(int).to_numpy()
        families = np.array(
            [
                "Benign" if target == 0 else attack_family(label)
                for label, target in zip(labels, targets)
            ],
            dtype=object,
        )
        meta = pd.DataFrame(
            {
                "fold": np.full(len(raw), index, dtype=np.int16),
                "capture_date": str(source_capture_date(source).isoformat()),
                "target": targets,
                "family": families,
            }
        )
        for name, scores in (
            ("raw", raw_scores),
            ("robust", robust_scores),
            ("fusion_rank_min_tb", fused),
        ):
            evaluate_at(
                meta,
                scores,
                rows_by_variant[name],
                frames_by_variant[name],
                BUDGET,
            )
        per_day_rows.append(
            {
                "date": source_capture_date(source).isoformat(),
                "rows": len(raw),
                "attacks": int(targets.sum()),
            }
        )
        del raw, raw_frame, robust_frame, raw_scores, robust_scores, fused, meta
        gc.collect()

    pooled_5 = {
        name: summarize_rows(rows) for name, rows in rows_by_variant.items()
    }
    ceilings_5 = {
        name: recall_ceiling(rows) for name, rows in rows_by_variant.items()
    }
    per_family_5 = {
        name: family_summary(
            frames,
            lambda frame: max(1, math.ceil(BUDGET * len(frame))),
        )
        for name, frames in frames_by_variant.items()
    }

    # 1% comparison from the same scored frames; no refit.
    rows_1: dict[str, list[dict[str, object]]] = {
        name: [] for name in rows_by_variant
    }
    for name, frames in frames_by_variant.items():
        for frame in frames:
            k = max(1, math.ceil(SMALL_BUDGET * len(frame)))
            rows_1[name].append(topk_row(frame, k))
    pooled_1 = {name: summarize_rows(rows) for name, rows in rows_1.items()}

    payload = {
        "protocol": (
            "Holdout end-to-end: train 7 ngày (14-23/02), test 3 ngày chưa thấy "
            "(Botnet 02/03, Infil1 28/02, Infil2 01/03). Train raw và robust trên "
            "cùng mẫu per-day; đánh giá top-q 1% và 5% flow/ngày."
        ),
        "train_sources": train_sources,
        "test_sources": test_sources,
        "train_rows": train_rows,
        "trees": TREES,
        "budget": BUDGET,
        "small_budget": SMALL_BUDGET,
        "pooled_5": pooled_5,
        "ceilings_5": ceilings_5,
        "pooled_1": pooled_1,
        "per_family_5": per_family_5,
        "per_day": per_day_rows,
        "models": {
            "raw": str(MODEL_DIR / "holdout_fusion_raw.joblib"),
            "robust": str(MODEL_DIR / "holdout_fusion_robust.joblib"),
        },
    }
    save_json(payload, RESULT_DIR / "holdout_fusion_metrics.json")

    csv_rows = []
    for name, pooled in pooled_5.items():
        csv_rows.append(
            {
                "variant": name,
                "budget": BUDGET,
                "recall": pooled["recall"],
                "precision": pooled["precision"],
                "f1": pooled["f1"],
                "fpr": pooled["fpr"],
                "recall_ceiling": ceilings_5[name],
                "alerts_per_day": pooled["alerts_per_day"],
                "alerts_at_threshold_per_day": pooled[
                    "alerts_at_threshold_per_day"
                ],
                "recall_at_threshold": pooled["recall_at_threshold"],
                "precision_at_threshold": pooled["precision_at_threshold"],
            }
        )
    pd.DataFrame(csv_rows).to_csv(
        RESULT_DIR / "holdout_fusion_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    names = ["raw", "robust", "fusion_rank_min_tb"]
    lines = [
        "# Holdout end-to-end: raw + robust fusion",
        "",
        "## Thiết lập",
        "",
        f"- {payload['protocol']}",
        f"- Train: {len(train_sources)} ngày, {MAX_TRAIN_ROWS:,} flow mục tiêu, "
        f"{TREES} cây; test tối đa {MAX_TEST_ROWS_PER_DAY:,} flow/ngày.",
        "- Hai model được train trên cùng mẫu per-day để so sánh công bằng.",
        "- Đây là kiểm tra packaging/holdout, không thay thế LODO 10 fold.",
        "",
        "## Kết quả 5% flow/ngày",
        "",
        "| Phương án | Recall | Precision | F1 | FPR | Ceiling | Alert/ngày |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in names:
        pooled = pooled_5[name]
        lines.append(
            f"| {name} | {fmt(pooled['recall'])} | {fmt(pooled['precision'])} | "
            f"{pooled['f1']:.4f} | {fmt(pooled['fpr'])} | "
            f"{fmt(ceilings_5[name])} | {pooled['alerts_per_day']:,.0f} |"
        )

    lines.extend(
        [
            "",
            "## Kết quả 1% flow/ngày",
            "",
            "| Phương án | Recall | Precision | F1 | FPR |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name in names:
        pooled = pooled_1[name]
        lines.append(
            f"| {name} | {fmt(pooled['recall'])} | {fmt(pooled['precision'])} | "
            f"{pooled['f1']:.4f} | {fmt(pooled['fpr'])} |"
        )

    lines.extend(
        [
            "",
            "## Theo ngày @ 5% flow/ngày",
            "",
            "| Ngày | Rows | Attacks | raw recall | robust recall | fusion recall |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for day_index, source in enumerate(test_sources):
        date = source_capture_date(source).isoformat()
        values = {}
        for name in names:
            row = rows_by_variant[name][day_index]
            values[name] = row["recall"]
        rows = rows_by_variant["raw"][day_index]["rows"]
        attacks = rows_by_variant["raw"][day_index]["attacks"]
        lines.append(
            f"| {date} | {rows:,} | {attacks:,} | {fmt(values['raw'])} | "
            f"{fmt(values['robust'])} | {fmt(values['fusion_rank_min_tb'])} |"
        )

    lines.extend(
        [
            "",
            "## Theo họ tấn công @ 5% flow/ngày",
            "",
            "| Họ | raw | robust | fusion_rank_min_tb |",
            "|---|---:|---:|---:|",
        ]
    )
    families = sorted(
        {
            row["family"]
            for name in names
            for row in per_family_5[name]
        }
    )
    for family in families:
        cells = []
        for name in names:
            value = next(
                (
                    row["recall"]
                    for row in per_family_5[name]
                    if row["family"] == family
                ),
                None,
            )
            cells.append(fmt(value))
        lines.append(f"| {family} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Kết luận",
            "",
            "Holdout chỉ có Botnet và Infiltration, không có ngày flood. Vì vậy "
            "kết quả này kiểm tra đường ống và hành vi trên họ chưa thấy, không "
            "đại diện cho toàn bộ phân bố. Kết luận chính vẫn lấy từ LODO 10 fold.",
            "",
            "Model artifacts: `models/holdout_fusion_raw.joblib`, "
            "`models/holdout_fusion_robust.joblib` (experimental).",
        ]
    )
    (RESULT_DIR / "holdout_fusion_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print("\nHoldout @ 5% flow/day")
    for name in names:
        pooled = pooled_5[name]
        print(
            f"  {name:<20} recall={pooled['recall']:.4f} "
            f"precision={pooled['precision']:.4f} f1={pooled['f1']:.4f} "
            f"fpr={pooled['fpr']:.4%}"
        )
    print(f"\nReport: {(RESULT_DIR / 'holdout_fusion_report.md').resolve()}")


if __name__ == "__main__":
    main()
