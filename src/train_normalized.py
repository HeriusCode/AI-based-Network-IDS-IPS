"""Leave-one-day-out experiment with per-day feature normalisation.

Two label-free normalisers are supported:

- ``robust``: signed log1p, then (x - median) / (IQR / 1.349) using the
  statistics of each day separately.
- ``rank``: per-feature percentile inside each day (uniform marginals).

Both are monotonic inside a day, so they keep the local ordering but remove
cross-day differences in location and scale. Statistics are computed on the
sampled batch only; no label information from the test day is used.
"""

from __future__ import annotations

import argparse
import gc
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

try:
    from src.calibrate import (
        detection_at,
        read_sources,
        thresholds_from_benign,
    )
    from src.common import (
        MODEL_METADATA_COLUMNS,
        PROCESSED_DATA,
        RESULT_DIR,
        SCORE_METADATA_COLUMNS,
        ensure_output_dirs,
        parquet_source_files,
        save_json,
        select_numeric_features,
    )
    from src.train_detection import (
        attack_family,
        attack_labels,
        create_pipeline,
        source_capture_date,
    )
except ModuleNotFoundError:
    from calibrate import detection_at, read_sources, thresholds_from_benign
    from common import (
        MODEL_METADATA_COLUMNS,
        PROCESSED_DATA,
        RESULT_DIR,
        SCORE_METADATA_COLUMNS,
        ensure_output_dirs,
        parquet_source_files,
        save_json,
        select_numeric_features,
    )
    from train_detection import (
        attack_family,
        attack_labels,
        create_pipeline,
        source_capture_date,
    )


TARGET_FPRS = (0.001, 0.005, 0.01, 0.02, 0.05)


def output_stem(args: argparse.Namespace, fold_count: int) -> str:
    """Keep subset/dataset runs from overwriting other experiment artifacts."""
    suffix = f"_{fold_count}fold" if args.only_sources else ""
    return f"{args.prefix}_{args.normaliser}{suffix}"


def score_stem(args: argparse.Namespace, fold_count: int) -> str:
    """Directory name for exported per-fold scores."""
    suffix = f"_{fold_count}fold" if args.only_sources else ""
    return f"{args.normaliser}{suffix}"


def signed_log(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.log1p(np.abs(values))


def robust_normalise(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    values = frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    logged = signed_log(values)
    median = np.nanmedian(logged, axis=0)
    q1 = np.nanquantile(logged, 0.25, axis=0)
    q3 = np.nanquantile(logged, 0.75, axis=0)
    scale = (q3 - q1) / 1.349
    std = np.nanstd(logged, axis=0)
    scale = np.where(scale > 1e-9, scale, np.where(std > 1e-9, std, 1.0))
    normalised = np.clip((logged - median) / scale, -12.0, 12.0)
    return _wrap(frame, normalised, features, "robust")


def rank_normalise(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    values = frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    normalised = np.full(values.shape, 0.5, dtype=np.float32)
    for column in range(values.shape[1]):
        column_values = values[:, column]
        valid = np.isfinite(column_values)
        if valid.sum() < 2:
            continue
        ranks = rankdata(column_values[valid], method="average")
        normalised[valid, column] = (ranks - 0.5) / valid.sum()
    return _wrap(frame, normalised, features, "rank")


def _attach_context(result: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Attach labels plus optional entity metadata without making them features."""
    result["target"] = frame["target"].to_numpy()
    for column in ("source_file", "Label", *MODEL_METADATA_COLUMNS):
        if column in frame:
            result[column] = frame[column].to_numpy()
    return result


def _wrap(frame: pd.DataFrame, values: np.ndarray, features: list[str], mode: str) -> pd.DataFrame:
    result = pd.DataFrame(values, columns=features, index=frame.index)
    _attach_context(result, frame)
    result.attrs["normaliser"] = mode
    return result


META_COLUMNS = ("target", "source_file", "Label", *MODEL_METADATA_COLUMNS)


def rate_features(features: list[str]) -> list[str]:
    """Features whose absolute scale is dominated by the day's traffic mix."""
    return [
        feature
        for feature in features
        if "/s" in feature or "IAT" in feature
    ]


def prepare_day(frame: pd.DataFrame, features: list[str], mode: str) -> pd.DataFrame:
    """Build the model matrix for one day.

    ``union`` keeps both the raw values and the per-day robust z-scores so the
    forest can use absolute magnitude (useful for Botnet/Bruteforce) and
    cross-day relative position (useful for DoS2/DDoS2) at the same time.
    ``rate`` applies the same idea but only to rate/IAT features, keeping
    counts, durations and flags absolute.
    """
    if mode == "raw":
        result = frame[features].replace([np.inf, -np.inf], np.nan).copy()
        return _attach_context(result, frame)

    if mode == "rate":
        raw = frame[features].replace([np.inf, -np.inf], np.nan).copy()
        selected = rate_features(features)
        normalised = robust_normalise(frame, selected)[selected].copy()
        normalised.columns = [f"z::{column}" for column in selected]
        result = pd.concat([raw, normalised], axis=1)
        return _attach_context(result, frame)

    if mode != "union":
        return (robust_normalise if mode == "robust" else rank_normalise)(frame, features)

    raw = frame[features].replace([np.inf, -np.inf], np.nan).copy()
    raw.columns = [f"raw::{column}" for column in features]
    normalised = robust_normalise(frame, features)[features].copy()
    normalised.columns = [f"z::{column}" for column in features]
    result = pd.concat([raw, normalised], axis=1)
    return _attach_context(result, frame)


def score_metadata(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Return optional IP/time columns in the stable schema used by score files."""
    result: dict[str, pd.Series] = {}
    for output_column, candidates in SCORE_METADATA_COLUMNS.items():
        for candidate in candidates:
            if candidate not in frame:
                continue
            values = frame[candidate]
            if output_column == "timestamp":
                # CIC-IDS timestamps use dd/mm/yyyy HH:MM:SS.  Without
                # dayfirst=True, 02/03/2018 is silently read as 3 February.
                values = pd.to_datetime(
                    values, errors="coerce", utc=True, dayfirst=True, format="mixed"
                )
            result[output_column] = pd.Series(values, dtype="string").reset_index(drop=True)
            break
    return result


def save_fold_scores(
    directory: Path,
    fold: int,
    row: dict[str, object],
    frame: pd.DataFrame,
    scores: np.ndarray,
    y_true: np.ndarray,
) -> Path:
    """Persist scores so alert-budget and entity policies can be evaluated without retraining."""
    labels = (
        frame["Label"].astype(str).to_numpy()
        if "Label" in frame
        else np.full(len(frame), "", dtype=object)
    )
    families = np.array(
        [
            "Benign" if int(target) == 0 else attack_family(label)
            for label, target in zip(labels, y_true)
        ],
        dtype=object,
    )
    source_values = (
        frame["source_file"].to_numpy()
        if "source_file" in frame
        else np.full(len(frame), row["test_source"], dtype=object)
    )
    payload = pd.DataFrame(
        {
            "fold": np.full(len(frame), fold, dtype=np.int16),
            "capture_date": str(row["capture_date"]),
            "source_file": pd.Series(source_values, dtype="string"),
            "target": np.asarray(y_true, dtype=np.int8),
            "label": pd.Series(labels, dtype="string"),
            "family": pd.Series(families, dtype="string"),
            "score": np.asarray(scores, dtype=np.float32),
        }
    )
    for column, values in score_metadata(frame).items():
        payload[column] = values
    path = directory / f"fold_{fold:02d}.parquet"
    payload.to_parquet(path, index=False)
    return path


def model_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in META_COLUMNS]


def fit_pipeline(frame: pd.DataFrame, features: list[str], args: argparse.Namespace):
    pipeline = create_pipeline(args)
    pipeline.fit(frame[features], frame["target"].astype(int))
    return pipeline


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

    score_dir: Path | None = None
    if args.save_scores:
        score_dir = Path(args.score_dir) / score_stem(args, len(selected))
        score_dir.mkdir(parents=True, exist_ok=True)
        for old_path in score_dir.glob("fold_*.parquet"):
            old_path.unlink()
        print(f"    Lưu score từng fold vào: {score_dir}")

    fold_rows: list[dict[str, object]] = []

    for index, test_source in enumerate(selected, 1):
        position = days.index(test_source)
        validation_source = days[(position - 1) % len(days)]
        train_sources = [name for name in days if name not in (test_source, validation_source)]
        per_day = max(args.max_rows // max(len(train_sources), 1), 5_000)
        print(
            f"[{index}/{len(selected)}] test={test_source[:12]} "
            f"validation={validation_source[:12]} train_days={len(train_sources)} "
            f"per_day={per_day:,} normaliser={args.normaliser}"
        )

        train_parts = []
        model_features: list[str] | None = None
        base_features: list[str] = []
        for offset, name in enumerate(train_sources):
            raw = read_sources(args, [name], per_day, args.random_state + offset)
            base_features = select_numeric_features(raw)
            prepared = prepare_day(raw, base_features, args.normaliser)
            if model_features is None:
                model_features = model_columns(prepared)
            train_parts.append(prepared)
            del raw
        train_frame = pd.concat(train_parts, ignore_index=True)
        del train_parts

        validation_raw = read_sources(
            args, [validation_source], args.max_val_rows, args.random_state + 20_000
        )
        test_raw = read_sources(
            args, [test_source], args.max_test_rows, args.random_state + 10_000
        )
        validation_frame = prepare_day(validation_raw, base_features, args.normaliser)
        test_frame = prepare_day(test_raw, base_features, args.normaliser)

        pipeline = fit_pipeline(train_frame, model_features, args)
        benign_mask = validation_frame["target"].astype(int).eq(0).to_numpy()
        validation_scores = pipeline.predict_proba(validation_frame[model_features])[:, 1][benign_mask]
        thresholds = thresholds_from_benign(validation_scores, args.target_fpr)

        scores = pipeline.predict_proba(test_frame[model_features])[:, 1]
        y_true = test_frame["target"].astype(int).to_numpy()
        train_families = {attack_family(label) for label in attack_labels(train_frame)}

        row = {
            "fold": index,
            "capture_date": source_capture_date(test_source).isoformat(),
            "test_source": test_source,
            "validation_source": validation_source,
            "group": family_group(test_frame, train_families),
            "rows": int(len(y_true)),
            "attack_rows": int(y_true.sum()),
            "per_day_train_rows": per_day,
            "thresholds": thresholds,
            "at_fixed_0_5": detection_at(y_true, scores, 0.5),
            **{
                f"fpr_{alpha}": detection_at(y_true, scores, thresholds[alpha])
                for alpha in args.target_fpr
            },
        }
        if len(np.unique(y_true)) > 1:
            from sklearn.metrics import roc_auc_score

            row["auc"] = float(roc_auc_score(y_true, scores))
        else:
            row["auc"] = None
        fold_rows.append(row)
        if score_dir is not None:
            saved_path = save_fold_scores(
                score_dir, index, row, test_frame, scores, y_true
            )
            print(f"    Đã lưu score: {saved_path.name}")

        fixed = row["at_fixed_0_5"]
        chosen = row[f"fpr_{args.threshold_fpr}"]
        print(
            f"    auc={row['auc']:.3f} fixed@0.5 recall={fixed['recall']:.4f} "
            f"f1={fixed['f1']:.4f} fpr={fixed['fpr']:.4%} | calibrated "
            f"recall={chosen['recall']:.4f} f1={chosen['f1']:.4f} fpr={chosen['fpr']:.4%}"
        )

        del train_frame, validation_raw, test_raw, validation_frame, test_frame
        gc.collect()

    def aggregate(rows: list[dict], key: str) -> dict[str, float]:
        tp = sum(row[key]["tp"] for row in rows)
        fp = sum(row[key]["fp"] for row in rows)
        fn = sum(row[key]["fn"] for row in rows)
        tn = sum(row[key]["tn"] for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        return {
            "recall": recall,
            "precision": precision,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "fpr": fp / (fp + tn) if fp + tn else 0.0,
        }

    policies = {"fixed_0_5": aggregate(fold_rows, "at_fixed_0_5")}
    for alpha in args.target_fpr:
        policies[f"fpr_{alpha}"] = aggregate(fold_rows, f"fpr_{alpha}")
    by_group = {}
    for group in ("family_seen", "family_unseen"):
        subset = [row for row in fold_rows if row["group"] == group]
        if not subset:
            continue
        by_group[group] = {
            "fixed_0_5": aggregate(subset, "at_fixed_0_5"),
            **{f"fpr_{alpha}": aggregate(subset, f"fpr_{alpha}") for alpha in args.target_fpr},
            "folds": len(subset),
            "attack_rows": sum(row["attack_rows"] for row in subset),
        }

    payload = {
        "mode": "lodo",
        "normaliser": args.normaliser,
        "protocol": (
            "Chuẩn hoá từng ngày riêng biệt (label-free) trước khi train/test; "
            "train 8 ngày, validation là ngày liền trước, test là ngày bị giữ."
        ),
        "target_fprs": list(args.target_fpr),
        "chosen_fpr": args.threshold_fpr,
        "trees": args.trees,
        "max_rows": args.max_rows,
        "folds": fold_rows,
        "pooled": policies,
        "by_group": by_group,
    }
    save_json(payload, RESULT_DIR / f"{output_stem(args, len(selected))}_metrics.json")

    summary_rows = []
    for row in fold_rows:
        chosen = row[f"fpr_{args.threshold_fpr}"]
        summary_rows.append(
            {
                "fold": row["fold"],
                "capture_date": row["capture_date"],
                "test_source": row["test_source"],
                "group": row["group"],
                "rows": row["rows"],
                "attack_rows": row["attack_rows"],
                "auc": row["auc"],
                "fixed_recall": row["at_fixed_0_5"]["recall"],
                "fixed_f1": row["at_fixed_0_5"]["f1"],
                "fixed_fpr": row["at_fixed_0_5"]["fpr"],
                "calibrated_recall": chosen["recall"],
                "calibrated_f1": chosen["f1"],
                "calibrated_fpr": chosen["fpr"],
            }
        )
    pd.DataFrame(summary_rows).to_csv(
        RESULT_DIR / f"{output_stem(args, len(selected))}_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    lines = [
        f"# Chuẩn hoá đặc trưng theo ngày ({args.normaliser})",
        "",
        f"- {payload['protocol']}",
        f"- Random Forest {args.trees} cây; train tối đa {args.max_rows:,} flow.",
        "",
        "## Kết quả gộp",
        "",
        "| Ngưỡng | Recall | Precision | F1 | FPR thực tế |",
        "|---|---:|---:|---:|---:|",
    ]
    labels = {"fixed_0_5": "cố định 0,5"}
    for alpha in args.target_fpr:
        labels[f"fpr_{alpha}"] = f"FPR mục tiêu {alpha:.1%}"
    for key, label in labels.items():
        row = policies[key]
        lines.append(
            f"| {label} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )
    lines.extend(
        [
            "",
            "## Theo nhóm tại ngưỡng 1%",
            "",
            "| Nhóm | Số fold | Recall | Precision | F1 | FPR |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for group, stats in by_group.items():
        row = stats["fpr_0.01"]
        lines.append(
            f"| {group} | {stats['folds']} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )
    lines.extend(
        [
            "",
            "## Từng fold",
            "",
            "| Fold | Ngày test | Nhóm | AUC | Recall@0,5 | F1@0,5 | Recall@1% | F1@1% | FPR@1% |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in fold_rows:
        chosen = row["fpr_0.01"]
        lines.append(
            f"| {row['fold']} | {row['capture_date']} | {row['group']} | {row['auc']:.3f} | "
            f"{row['at_fixed_0_5']['recall']:.4f} | {row['at_fixed_0_5']['f1']:.4f} | "
            f"{chosen['recall']:.4f} | {chosen['f1']:.4f} | {chosen['fpr']:.4%} |"
        )
    lines.append("")
    (RESULT_DIR / f"{output_stem(args, len(selected))}_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print("")
    for key, row in policies.items():
        print(
            f"{key:<14} recall={row['recall']:.4f} precision={row['precision']:.4f} "
            f"f1={row['f1']:.4f} fpr={row['fpr']:.4%}"
        )
    for group, stats in by_group.items():
        row = stats["fpr_0.01"]
        print(f"{group:<14} recall={row['recall']:.4f} f1={row['f1']:.4f} fpr={row['fpr']:.4%}")


def run_selection(args: argparse.Namespace) -> None:
    """Train raw and robust variants, pick the better one on the validation day."""
    from sklearn.metrics import roc_auc_score

    days = sorted(parquet_source_files(args.data), key=source_capture_date)
    selected = days
    if args.only_sources:
        keys = [key.lower() for key in args.only_sources]
        selected = [name for name in days if any(key in name.lower() for key in keys)]
    if not selected:
        raise ValueError("Không có source_file nào khớp --only-sources.")

    fold_rows: list[dict[str, object]] = []

    for index, test_source in enumerate(selected, 1):
        position = days.index(test_source)
        validation_source = days[(position - 1) % len(days)]
        train_sources = [name for name in days if name not in (test_source, validation_source)]
        per_day = max(args.max_rows // max(len(train_sources), 1), 5_000)
        print(
            f"[{index}/{len(selected)}] test={test_source[:12]} "
            f"validation={validation_source[:12]} select(raw vs robust)"
        )

        raw_parts, robust_parts = [], []
        base_features: list[str] = []
        for offset, name in enumerate(train_sources):
            raw = read_sources(args, [name], per_day, args.random_state + offset)
            base_features = select_numeric_features(raw)
            raw_parts.append(prepare_day(raw, base_features, "raw"))
            robust_parts.append(prepare_day(raw, base_features, "robust"))
            del raw
        raw_train = pd.concat(raw_parts, ignore_index=True)
        robust_train = pd.concat(robust_parts, ignore_index=True)
        del raw_parts, robust_parts

        validation_raw = read_sources(
            args, [validation_source], args.max_val_rows, args.random_state + 20_000
        )
        test_raw = read_sources(
            args, [test_source], args.max_test_rows, args.random_state + 10_000
        )

        variants = {}
        for mode, train_frame in (("raw", raw_train), ("robust", robust_train)):
            features = model_columns(train_frame)
            pipeline = fit_pipeline(train_frame, features, args)
            validation_frame = prepare_day(validation_raw, base_features, mode)
            validation_scores = pipeline.predict_proba(validation_frame[features])[:, 1]
            auc = float(
                roc_auc_score(validation_frame["target"].astype(int), validation_scores)
            )
            variants[mode] = {
                "pipeline": pipeline,
                "features": features,
                "validation_frame": validation_frame,
                "validation_scores": validation_scores,
                "validation_auc": auc,
            }
            print(f"    {mode:<7} validation_auc={auc:.4f}")

        chosen = "raw" if variants["raw"]["validation_auc"] >= variants["robust"]["validation_auc"] else "robust"
        variant = variants[chosen]
        benign_mask = variant["validation_frame"]["target"].astype(int).eq(0).to_numpy()
        thresholds = thresholds_from_benign(
            variant["validation_scores"][benign_mask], args.target_fpr
        )
        test_frame = prepare_day(test_raw, base_features, chosen)
        scores = variant["pipeline"].predict_proba(test_frame[variant["features"]])[:, 1]
        y_true = test_frame["target"].astype(int).to_numpy()

        row = {
            "fold": index,
            "capture_date": source_capture_date(test_source).isoformat(),
            "test_source": test_source,
            "validation_source": validation_source,
            "selected": chosen,
            "validation_auc_raw": variants["raw"]["validation_auc"],
            "validation_auc_robust": variants["robust"]["validation_auc"],
            "rows": int(len(y_true)),
            "attack_rows": int(y_true.sum()),
            "auc": float(roc_auc_score(y_true, scores)),
            "thresholds": thresholds,
            "at_fixed_0_5": detection_at(y_true, scores, 0.5),
            **{
                f"fpr_{alpha}": detection_at(y_true, scores, thresholds[alpha])
                for alpha in args.target_fpr
            },
        }
        fold_rows.append(row)
        chosen_metrics = row[f"fpr_{args.threshold_fpr}"]
        print(
            f"    chọn={chosen} auc_test={row['auc']:.3f} recall@0.5="
            f"{row['at_fixed_0_5']['recall']:.4f} calibrated_recall="
            f"{chosen_metrics['recall']:.4f} fpr={chosen_metrics['fpr']:.4%}"
        )

        del raw_train, robust_train, validation_raw, test_raw
        gc.collect()

    def aggregate(rows: list[dict], key: str) -> dict[str, float]:
        tp = sum(row[key]["tp"] for row in rows)
        fp = sum(row[key]["fp"] for row in rows)
        fn = sum(row[key]["fn"] for row in rows)
        tn = sum(row[key]["tn"] for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        return {
            "recall": recall,
            "precision": precision,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "fpr": fp / (fp + tn) if fp + tn else 0.0,
        }

    policies = {"fixed_0_5": aggregate(fold_rows, "at_fixed_0_5")}
    for alpha in args.target_fpr:
        policies[f"fpr_{alpha}"] = aggregate(fold_rows, f"fpr_{alpha}")

    payload = {
        "mode": "lodo",
        "normaliser": "select",
        "protocol": (
            "Train cả raw và robust/ngày; chọn biến thể có AUC cao hơn trên ngày "
            "validation; test trên ngày bị giữ. Không dùng test để chọn."
        ),
        "target_fprs": list(args.target_fpr),
        "chosen_fpr": args.threshold_fpr,
        "folds": fold_rows,
        "pooled": policies,
    }
    save_json(payload, RESULT_DIR / f"{output_stem(args, len(selected))}_metrics.json")
    pd.DataFrame(
        [
            {
                "fold": row["fold"],
                "capture_date": row["capture_date"],
                "test_source": row["test_source"],
                "selected": row["selected"],
                "validation_auc_raw": row["validation_auc_raw"],
                "validation_auc_robust": row["validation_auc_robust"],
                "auc": row["auc"],
                "fixed_recall": row["at_fixed_0_5"]["recall"],
                "fixed_f1": row["at_fixed_0_5"]["f1"],
                "calibrated_recall": row["fpr_0.01"]["recall"],
                "calibrated_f1": row["fpr_0.01"]["f1"],
                "calibrated_fpr": row["fpr_0.01"]["fpr"],
            }
            for row in fold_rows
        ]
    ).to_csv(
        RESULT_DIR / f"{output_stem(args, len(selected))}_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    lines = [
        "# Chọn biến thể theo ngày validation (raw vs robust)",
        "",
        f"- {payload['protocol']}",
        "",
        "| Ngưỡng | Recall | Precision | F1 | FPR thực tế |",
        "|---|---:|---:|---:|---:|",
    ]
    labels = {"fixed_0_5": "cố định 0,5"}
    for alpha in args.target_fpr:
        labels[f"fpr_{alpha}"] = f"FPR mục tiêu {alpha:.1%}"
    for key, label in labels.items():
        row = policies[key]
        lines.append(
            f"| {label} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )
    lines.extend(
        [
            "",
            "## Từng fold",
            "",
            "| Fold | Ngày test | Chọn | AUC val raw | AUC val robust | AUC test | Recall@1% | F1@1% | FPR@1% |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in fold_rows:
        chosen = row["fpr_0.01"]
        lines.append(
            f"| {row['fold']} | {row['capture_date']} | {row['selected']} | "
            f"{row['validation_auc_raw']:.3f} | {row['validation_auc_robust']:.3f} | "
            f"{row['auc']:.3f} | {chosen['recall']:.4f} | {chosen['f1']:.4f} | "
            f"{chosen['fpr']:.4%} |"
        )
    lines.append("")
    (RESULT_DIR / f"{output_stem(args, len(selected))}_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    for key, row in policies.items():
        print(
            f"{key:<14} recall={row['recall']:.4f} precision={row['precision']:.4f} "
            f"f1={row['f1']:.4f} fpr={row['fpr']:.4%}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument(
        "--prefix",
        default="normalized",
        help="Tiền tố tên file kết quả; đổi khi chạy dataset khác để không ghi đè.",
    )
    parser.add_argument("--normaliser", choices=["raw", "robust", "rank", "union", "rate", "select"], default="robust")
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--max-rows", type=int, default=500_000)
    parser.add_argument("--max-val-rows", type=int, default=150_000)
    parser.add_argument("--max-test-rows", type=int, default=200_000)
    parser.add_argument("--target-fpr", type=float, nargs="*", default=list(TARGET_FPRS))
    parser.add_argument("--threshold-fpr", type=float, default=0.01)
    parser.add_argument("--only-sources", nargs="*", default=None)
    parser.add_argument(
        "--save-scores",
        action="store_true",
        help="Lưu score từng flow của mỗi fold để đánh giá ngân sách cảnh báo.",
    )
    parser.add_argument(
        "--score-dir",
        default=str(RESULT_DIR / "lodo_scores"),
        help="Thư mục gốc chứa score từng fold.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    if args.threshold_fpr not in args.target_fpr:
        raise ValueError("--threshold-fpr phải nằm trong --target-fpr.")
    if args.normaliser == "select":
        run_selection(args)
    else:
        run_lodo(args)


if __name__ == "__main__":
    main()
