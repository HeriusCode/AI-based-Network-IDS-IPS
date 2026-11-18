"""Audit label and feature consistency for selected capture days.

The audit answers four questions for a day where the model behaves strangely:

1. Are the labels clean (only expected variants, no contradictory duplicates)?
2. Do the raw features separate benign from attack *within* the day?
3. Is the benign traffic of the day shifted relative to other days?
4. What scores does a model trained on the other nine days assign to each label?

Usage:
    python src/audit_days.py --sources DoS2 DDoS2
"""

from __future__ import annotations

import argparse
import gc
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

try:
    from src.common import (
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        prepare_features,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )
    from src.train_detection import create_pipeline, source_capture_date
except ModuleNotFoundError:
    from common import (
        PROCESSED_DATA,
        RESULT_DIR,
        ensure_output_dirs,
        prepare_features,
        read_sampled_dataframe,
        save_json,
        select_numeric_features,
    )
    from train_detection import create_pipeline, source_capture_date


KEY_FEATURES = (
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Packet Length Mean",
    "Fwd Packet Length Mean",
    "Bwd Packet Length Mean",
    "SYN Flag Count",
    "ACK Flag Count",
    "Down/Up Ratio",
    "Init Fwd Win Bytes",
)


def load_day(path: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = pd.read_parquet(path)
    frame["Label"] = frame["Label"].astype(str).str.strip()
    frame["target"] = (frame["Label"].str.lower() != "benign").astype(int)
    frame["source_file"] = path.name
    features = select_numeric_features(frame)
    return frame, features


def univariate_aucs(
    frame: pd.DataFrame, features: list[str], sample: int = 150_000, seed: int = 42
) -> list[dict[str, object]]:
    subset = frame if len(frame) <= sample else frame.sample(sample, random_state=seed)
    y_true = subset["target"].to_numpy()
    results = []
    for feature in features:
        values = pd.to_numeric(subset[feature], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(values)
        if mask.sum() < 500 or np.unique(values[mask]).size < 2:
            continue
        auc = float(roc_auc_score(y_true[mask], values[mask]))
        results.append({"feature": feature, "auc": auc, "direction": "higher=attack" if auc >= 0.5 else "higher=benign"})
    results.sort(key=lambda item: abs(item["auc"] - 0.5), reverse=True)
    return results


def duplicate_stats(frame: pd.DataFrame, features: list[str]) -> dict[str, object]:
    values = frame[features].replace([np.inf, -np.inf], np.nan)
    hashes = pd.util.hash_pandas_object(values, index=False)
    table = pd.DataFrame({"hash": hashes, "target": frame["target"]})
    groups = table.groupby("hash")["target"].agg(["count", "nunique"])
    duplicated_rows = int(groups.loc[groups["count"] > 1, "count"].sum())
    conflict_groups = groups[(groups["count"] > 1) & (groups["nunique"] > 1)]
    return {
        "rows": int(len(frame)),
        "unique_feature_rows": int(len(groups)),
        "rows_in_duplicate_groups": duplicated_rows,
        "groups_with_conflicting_labels": int(len(conflict_groups)),
        "rows_in_conflicting_groups": int(conflict_groups["count"].sum()),
    }


def benign_statistics(frame: pd.DataFrame, features: list[str], sample: int = 80_000, seed: int = 7) -> dict[str, float]:
    benign = frame[frame["target"].eq(0)]
    if len(benign) > sample:
        benign = benign.sample(sample, random_state=seed)
    values = benign[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    logged = np.log1p(np.clip(values, 0, None))
    return {
        "mean": np.nanmean(logged, axis=0),
        "std": np.nanstd(logged, axis=0),
        "median": np.nanmedian(values, axis=0),
    }


def drift_table(
    frame: pd.DataFrame,
    features: list[str],
    other_benign: dict[str, float],
    limit: int = 10,
) -> list[dict[str, float]]:
    stats = benign_statistics(frame, features)
    rows = []
    for index, feature in enumerate(features):
        other_mean = other_benign["mean"][index]
        other_std = other_benign["std"][index]
        if not np.isfinite(other_mean) or not np.isfinite(other_std) or other_std <= 1e-9:
            continue
        smd = float((stats["mean"][index] - other_mean) / other_std)
        rows.append(
            {
                "feature": feature,
                "smd": smd,
                "day_median": float(stats["median"][index]),
                "other_days_median": float(other_benign["median"][index]),
            }
        )
    rows.sort(key=lambda item: abs(item["smd"]), reverse=True)
    return rows[:limit]


def class_feature_medians(frame: pd.DataFrame, features: list[str]) -> dict[str, dict[str, float]]:
    result = {}
    for label, subset in frame.groupby("Label"):
        if len(subset) > 100_000:
            subset = subset.sample(100_000, random_state=11)
        result[str(label)] = {
            feature: float(np.nanmedian(pd.to_numeric(subset[feature], errors="coerce")))
            for feature in KEY_FEATURES
            if feature in subset
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(PROCESSED_DATA))
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--max-train-rows", type=int, default=500_000)
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    ensure_output_dirs()

    day_paths = sorted(Path("data/raw").glob("*.parquet"))
    all_days = [path for path in day_paths if path.name != ".gitkeep"]
    selected = [
        path
        for path in all_days
        if any(key.lower() in path.name.lower() for key in args.sources)
    ]
    if not selected:
        raise ValueError("Không tìm thấy ngày nào khớp --sources.")

    print("Đang tính phân bố benign của các ngày còn lại...")
    benign_sums: dict[str, np.ndarray] = {}
    benign_sumsq: dict[str, np.ndarray] = {}
    benign_counts: dict[str, np.ndarray] = {}
    benign_medians: dict[str, np.ndarray] = {}
    for path in all_days:
        frame, features = load_day(path)
        benign = frame[frame["target"].eq(0)]
        if len(benign) > 80_000:
            benign = benign.sample(80_000, random_state=7)
        values = benign[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        logged = np.log1p(np.clip(values, 0, None))
        benign_sums[path.name] = np.nansum(logged, axis=0)
        benign_sumsq[path.name] = np.nansum(logged**2, axis=0)
        benign_counts[path.name] = np.sum(np.isfinite(logged), axis=0)
        benign_medians[path.name] = np.nanmedian(values, axis=0)
        del frame
    reference_features = features

    payload: dict[str, object] = {"days": {}}
    markdown = [
        "# Audit dữ liệu các ngày bất thường",
        "",
        "Mỗi ngày được kiểm tra: nhãn, trùng lặp, AUC đơn biến trong ngày, drift benign",
        "so với 9 ngày còn lại, và điểm của model train trên 9 ngày đó.",
        "",
    ]

    for path in selected:
        print(f"\n=== {path.name} ===")
        frame, features = load_day(path)
        if features != reference_features:
            print("Cảnh báo: danh sách đặc trưng khác reference.")
        y_true = frame["target"].to_numpy()

        label_counts = {str(key): int(value) for key, value in frame["Label"].value_counts().items()}
        print("Nhãn:", label_counts)

        duplicates = duplicate_stats(frame, features)
        print("Trùng lặp:", duplicates)

        aucs = univariate_aucs(frame, features)
        print("Top AUC đơn biến:", [(item["feature"], round(item["auc"], 3)) for item in aucs[:5]])

        other_names = [name for name in benign_sums if name != path.name]
        other_sum = np.sum([benign_sums[name] for name in other_names], axis=0)
        other_sumsq = np.sum([benign_sumsq[name] for name in other_names], axis=0)
        other_count = np.sum([benign_counts[name] for name in other_names], axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            other_mean = other_sum / other_count
            other_var = other_sumsq / other_count - other_mean**2
        other_benign = {
            "mean": other_mean,
            "std": np.sqrt(np.clip(other_var, 0, None)),
            "median": np.nanmedian(np.vstack([benign_medians[name] for name in other_names]), axis=0),
        }
        drift = drift_table(frame, features, other_benign)
        print("Drift mạnh nhất:", [(item["feature"], round(item["smd"], 2)) for item in drift[:5]])

        other_sources = other_names
        train_frame = read_sampled_dataframe(
            args.data,
            args.max_train_rows,
            args.random_state,
            filter_values={"source_file": other_sources},
        )
        pipeline = create_pipeline(argparse.Namespace(trees=args.trees, random_state=args.random_state, n_jobs=-1))
        X_train = train_frame[features].replace([np.inf, -np.inf], np.nan)
        pipeline.fit(X_train, train_frame["target"].astype(int))
        del train_frame, X_train

        scores = pipeline.predict_proba(prepare_features(frame, features))[:, 1]
        overall_auc = float(roc_auc_score(y_true, scores))
        per_label = {}
        for label, subset in frame.groupby("Label"):
            mask = frame["Label"].eq(label).to_numpy()
            label_scores = scores[mask]
            per_label[str(label)] = {
                "rows": int(mask.sum()),
                "mean_score": float(np.mean(label_scores)),
                "median_score": float(np.median(label_scores)),
                "p90_score": float(np.quantile(label_scores, 0.9)),
                "predicted_attack_rate_0_5": float(np.mean(label_scores >= 0.5)),
            }
        print(f"AUC model 9 ngày: {overall_auc:.4f}")
        for label, stats in per_label.items():
            print(
                f"  {label:<24} n={stats['rows']:>7,} mean={stats['mean_score']:.4f} "
                f"median={stats['median_score']:.4f} p90={stats['p90_score']:.4f} "
                f"pred@0.5={stats['predicted_attack_rate_0_5']:.4f}"
            )

        payload["days"][path.name] = {
            "capture_date": source_capture_date(path.name).isoformat(),
            "rows": int(len(frame)),
            "label_counts": label_counts,
            "duplicates": duplicates,
            "top_univariate_auc": aucs[:15],
            "drift_top": drift,
            "class_feature_medians": class_feature_medians(frame, features),
            "model": {
                "auc": overall_auc,
                "per_label": per_label,
                "train_sources": other_sources,
            },
        }

        markdown.extend(
            [
                f"## {path.name}",
                "",
                f"- Tổng flow: {len(frame):,}",
                f"- Nhãn: " + ", ".join(f"`{key}` = {value:,}" for key, value in label_counts.items()),
                f"- Dòng trùng đặc trưng: {duplicates['rows_in_duplicate_groups']:,} "
                f"({duplicates['rows_in_duplicate_groups'] / len(frame):.2%}); "
                f"nhóm trùng nhưng khác nhãn: {duplicates['groups_with_conflicting_labels']:,}",
                f"- AUC model train 9 ngày: **{overall_auc:.4f}**",
                "",
                "### Điểm model theo nhãn",
                "",
                "| Nhãn | Số flow | Score trung bình | Median | P90 | Tỉ lệ dự đoán ATTACK @0,5 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for label, stats in per_label.items():
            markdown.append(
                f"| {label} | {stats['rows']:,} | {stats['mean_score']:.4f} | "
                f"{stats['median_score']:.4f} | {stats['p90_score']:.4f} | "
                f"{stats['predicted_attack_rate_0_5']:.2%} |"
            )

        markdown.extend(
            [
                "",
                "### AUC đơn biến trong ngày",
                "",
                "| Đặc trưng | AUC | Hướng |",
                "|---|---:|---|",
            ]
        )
        for item in aucs[:10]:
            markdown.append(f"| {item['feature']} | {item['auc']:.3f} | {item['direction']} |")

        markdown.extend(
            [
                "",
                "### Drift benign so với 9 ngày còn lại",
                "",
                "| Đặc trưng | SMD | Median ngày này | Median 9 ngày |",
                "|---|---:|---:|---:|",
            ]
        )
        for item in drift:
            markdown.append(
                f"| {item['feature']} | {item['smd']:+.2f} | {item['day_median']:.3f} | "
                f"{item['other_days_median']:.3f} |"
            )
        markdown.append("")

        del frame

        gc.collect()

    output_json = RESULT_DIR / "audit_days.json"
    save_json(payload, output_json)
    output_md = RESULT_DIR / "audit_days.md"
    output_md.write_text("\n".join(markdown), encoding="utf-8")
    print(f"\nĐã ghi: {output_json.resolve()}")
    print(f"Đã ghi: {output_md.resolve()}")


if __name__ == "__main__":
    main()
