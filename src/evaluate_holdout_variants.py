"""Compare fusion rules on the saved 3-day holdout models.

The models are not retrained here.  This answers a narrow question left open by
the LODO fusion report: on the deployment holdout (Botnet + Infiltration), does
``rank_min_tb`` remain the best rule, or does a simpler rule win?
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.calibrate import read_sources
    from src.common import (
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        load_bundle,
        prepare_features,
        save_json,
    )
    from src.evaluate_budget import (
        family_summary,
        recall_ceiling,
        summarize_rows,
        topk_row,
    )
    from src.evaluate_fusion import fused_frame
    from src.train_detection import attack_family, source_capture_date
    from src.train_normalized import prepare_day
except ModuleNotFoundError:
    from calibrate import read_sources
    from common import (
        MODEL_DIR,
        PROCESSED_DATA,
        RESULT_DIR,
        load_bundle,
        prepare_features,
        save_json,
    )
    from evaluate_budget import (
        family_summary,
        recall_ceiling,
        summarize_rows,
        topk_row,
    )
    from evaluate_fusion import fused_frame
    from train_detection import attack_family, source_capture_date
    from train_normalized import prepare_day


METHODS = ("mean", "max", "rank_mean", "rank_max", "rank_min", "rank_min_tb")
BUDGETS = (0.01, 0.05)
MAX_TEST_ROWS = 200_000


def main() -> None:
    raw_bundle = load_bundle(MODEL_DIR / "holdout_fusion_raw.joblib")
    robust_bundle = load_bundle(MODEL_DIR / "holdout_fusion_robust.joblib")
    test_sources = sorted(
        list(raw_bundle["test_sources"]), key=source_capture_date
    )
    base_features = list(raw_bundle["feature_columns"])

    raw_frames: list[pd.DataFrame] = []
    robust_frames: list[pd.DataFrame] = []
    for index, source in enumerate(test_sources, 1):
        raw = read_sources(
            type("Args", (), {"data": PROCESSED_DATA})(),
            [source],
            MAX_TEST_ROWS,
            42 + 10_000,
        )
        raw_frame = prepare_day(raw, base_features, "raw")
        robust_frame = prepare_day(raw, base_features, "robust")
        raw_scores = raw_bundle["pipeline"].predict_proba(
            prepare_features(raw_frame, raw_bundle["feature_columns"])
        )[:, 1]
        robust_scores = robust_bundle["pipeline"].predict_proba(
            prepare_features(robust_frame, robust_bundle["feature_columns"])
        )[:, 1]
        labels = raw["Label"].astype(str).to_numpy()
        targets = raw["target"].astype(int).to_numpy()
        families = np.array(
            [
                "Benign" if target == 0 else attack_family(label)
                for label, target in zip(labels, targets)
            ],
            dtype=object,
        )
        base = pd.DataFrame(
            {
                "fold": np.full(len(raw), index, dtype=np.int16),
                "capture_date": source_capture_date(source).isoformat(),
                "source_file": source,
                "target": targets,
                "label": labels,
                "family": families,
            }
        )
        raw_df = base.copy()
        raw_df["score"] = raw_scores.astype(np.float32)
        robust_df = base.copy()
        robust_df["score"] = robust_scores.astype(np.float32)
        raw_frames.append(raw_df)
        robust_frames.append(robust_df)
        del raw, raw_frame, robust_frame, raw_scores, robust_scores
        print(f"scored {source_capture_date(source)}")

    frames_by_variant: dict[str, list[pd.DataFrame]] = {
        "raw": raw_frames,
        "robust": robust_frames,
    }
    for method in METHODS:
        frames_by_variant[f"fusion_{method}"] = [
            fused_frame(left, right, method)
            for left, right in zip(raw_frames, robust_frames)
        ]

    payload: dict[str, object] = {
        "protocol": (
            "Holdout 3 ngày (28/02-02/03), model raw/robust train 14-23/02. "
            "Không train lại; so sánh các fusion rule ở top-q 1% và 5%."
        ),
        "budgets": list(BUDGETS),
        "variants": {},
    }
    names = list(frames_by_variant)
    for name, frames in frames_by_variant.items():
        payload["variants"][name] = {
            "pools": {},
            "families": {},
        }
        for budget in BUDGETS:
            rows = [
                topk_row(frame, max(1, math.ceil(budget * len(frame))))
                for frame in frames
            ]
            payload["variants"][name]["pools"][str(budget)] = {
                "pooled": summarize_rows(rows),
                "ceiling": recall_ceiling(rows),
                "per_fold": rows,
            }
        payload["variants"][name]["families"]["0.05"] = family_summary(
            frames, lambda frame: max(1, math.ceil(0.05 * len(frame)))
        )

    save_json(payload, RESULT_DIR / "holdout_fusion_variants.json")
    lines = [
        "# Holdout: so sánh fusion rule",
        "",
        "- 3 ngày test: Botnet 02/03, Infil1 28/02, Infil2 01/03.",
        "- Model raw/robust train 14-23/02; không train lại ở bước này.",
        "",
        "## 5% flow/ngày",
        "",
        "| Phương án | Recall | Precision | F1 | FPR | Ceiling |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in names:
        policy = payload["variants"][name]["pools"]["0.05"]
        pooled = policy["pooled"]
        lines.append(
            f"| {name} | {pooled['recall']:.2%} | {pooled['precision']:.2%} | "
            f"{pooled['f1']:.4f} | {pooled['fpr']:.2%} | "
            f"{policy['ceiling']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## 1% flow/ngày",
            "",
            "| Phương án | Recall | Precision | F1 | FPR |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name in names:
        pooled = payload["variants"][name]["pools"]["0.01"]["pooled"]
        lines.append(
            f"| {name} | {pooled['recall']:.2%} | {pooled['precision']:.2%} | "
            f"{pooled['f1']:.4f} | {pooled['fpr']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Theo họ @ 5% flow/ngày",
            "",
            "| Họ | " + " | ".join(names) + " |",
            "|---|" + "|".join(["---:"] * len(names)) + "|",
        ]
    )
    families = sorted(
        {
            row["family"]
            for name in names
            for row in payload["variants"][name]["families"]["0.05"]
        }
    )
    for family in families:
        cells = []
        for name in names:
            value = next(
                (
                    row["recall"]
                    for row in payload["variants"][name]["families"]["0.05"]
                    if row["family"] == family
                ),
                None,
            )
            cells.append("-" if value is None else f"{value:.2%}")
        lines.append(f"| {family} | " + " | ".join(cells) + " |")
    (RESULT_DIR / "holdout_fusion_variants.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
