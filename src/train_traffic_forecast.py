"""Train a baseline traffic forecaster (packets/s and bytes/s).

The input is a regular time series produced by ``build_traffic_series.py`` or
by a real collector.  Training is chronological: the first rows are train, the
next block is validation, and the last block is test.  Random splitting is not
allowed because future values would leak into the past.

Example:

    python src/train_traffic_forecast.py ^
        --data data/processed/traffic_series_60s.csv ^
        --interval-seconds 60 ^
        --lags 12 --trees 150 ^
        --model models/traffic_forecast.joblib
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from src.common import MODEL_DIR, RESULT_DIR, save_json
    from src.traffic_features import (
        DEFAULT_TARGETS,
        DEFAULT_WINDOWS,
        infer_interval_seconds,
        make_supervised,
        prepare_rate_frame,
    )
except ModuleNotFoundError:  # Allows: python src/train_traffic_forecast.py
    from common import MODEL_DIR, RESULT_DIR, save_json
    from traffic_features import (
        DEFAULT_TARGETS,
        DEFAULT_WINDOWS,
        infer_interval_seconds,
        make_supervised,
        prepare_rate_frame,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/traffic_series_60s.csv"),
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL_DIR / "traffic_forecast.joblib",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=RESULT_DIR / "traffic_forecast_metrics.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=RESULT_DIR / "traffic_forecast_report.md",
    )
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Danh sách target, phân tách bằng dấu phẩy.",
    )
    parser.add_argument("--interval-seconds", type=int, default=0, help="0 = tự suy ra.")
    parser.add_argument("--lags", type=int, default=12)
    parser.add_argument(
        "--windows",
        default=",".join(str(value) for value in DEFAULT_WINDOWS),
        help="Các cửa sổ rolling, phân tách bằng dấu phẩy.",
    )
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--trees", type=int, default=150)
    parser.add_argument("--max-depth", type=int, default=0, help="0 = không giới hạn.")
    parser.add_argument("--min-samples-leaf", type=int, default=2)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--version", default="traffic-1")
    return parser.parse_args()


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float | None]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    if len(y_true) == 0:
        return {"mae": None, "rmse": None, "mape": None, "r2": None, "rows": 0}
    absolute_error = np.abs(y_true - y_pred)
    nonzero = np.abs(y_true) > 1e-9
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mape": float(np.mean(absolute_error[nonzero] / np.abs(y_true[nonzero]))) if nonzero.any() else None,
        "r2": float(r2_score(y_true, y_pred)) if len(y_true) >= 2 else None,
        "rows": int(len(y_true)),
    }


def split_bounds(length: int, val_fraction: float, test_fraction: float) -> tuple[int, int]:
    if val_fraction < 0 or test_fraction <= 0 or val_fraction + test_fraction >= 1:
        raise ValueError("Cần val_fraction >= 0, test_fraction > 0 và tổng < 1.")
    val_rows = max(1, int(round(length * val_fraction)))
    test_rows = max(1, int(round(length * test_fraction)))
    train_end = length - val_rows - test_rows
    if train_end < 10:
        raise ValueError("Quá ít dòng train sau khi chia; cần thêm dữ liệu.")
    return train_end, length - test_rows


def markdown_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, float):
                values.append(f"{value:.6g}")
            elif value is None:
                values.append("—")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if not args.data.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu: {args.data}")
    targets = [item.strip() for item in args.targets.split(",") if item.strip()]
    windows = sorted({int(item) for item in args.windows.split(",") if item.strip()})
    if args.lags <= 0 or not windows or args.horizon <= 0:
        raise ValueError("--lags, --windows, --horizon phải > 0.")

    raw = pd.read_csv(args.data)
    interval = args.interval_seconds or infer_interval_seconds(raw)
    frame = prepare_rate_frame(raw, interval, targets)
    features, target_values, baselines = make_supervised(frame, targets, args.lags, windows, args.horizon)
    if len(features) < 30:
        raise ValueError("Quá ít dòng sau feature engineering; cần thêm dữ liệu.")

    train_end, test_start = split_bounds(len(features), args.val_fraction, args.test_fraction)
    train_index = features.index[:train_end]
    val_index = features.index[train_end:test_start]
    test_index = features.index[test_start:]

    models: dict[str, RandomForestRegressor] = {}
    metrics: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": args.version,
        "data": str(args.data),
        "interval_seconds": int(interval),
        "lags": int(args.lags),
        "windows": windows,
        "horizon": int(args.horizon),
        "targets": targets,
        "train_rows": int(len(train_index)),
        "val_rows": int(len(val_index)),
        "test_rows": int(len(test_index)),
        "train_start": str(train_index.min()),
        "train_end": str(train_index.max()),
        "test_start": str(test_index.min()),
        "test_end": str(test_index.max()),
        "per_target": {},
    }
    risk_thresholds: dict[str, dict[str, float]] = {}
    top_features: dict[str, list[dict[str, object]]] = {}

    for target in targets:
        model = RandomForestRegressor(
            n_estimators=args.trees,
            max_depth=args.max_depth or None,
            min_samples_leaf=args.min_samples_leaf,
            random_state=args.random_state,
            n_jobs=-1,
        )
        model.fit(features.loc[train_index], target_values[target].loc[train_index])
        models[target] = model

        validation_prediction = model.predict(features.loc[val_index])
        test_prediction = model.predict(features.loc[test_index])
        test_truth = target_values[target].loc[test_index]

        target_metrics: dict[str, object] = {
            "random_forest": {
                "validation": regression_metrics(
                    target_values[target].loc[val_index], validation_prediction
                ),
                "test": regression_metrics(test_truth, test_prediction),
            },
            "persistence": regression_metrics(
                test_truth, baselines.loc[test_index, f"{target}_persistence"]
            ),
            "moving_average_3": regression_metrics(
                test_truth, baselines.loc[test_index, f"{target}_ma3"]
            ),
            "moving_average_6": regression_metrics(
                test_truth, baselines.loc[test_index, f"{target}_ma6"]
            ),
        }
        metrics["per_target"][target] = target_metrics

        train_values = frame.loc[train_index, target].astype(float)
        # Long capture gaps produce zero buckets; including them would make
        # p95 = 0 and mark almost every real forecast as HIGH. Use active
        # traffic for the risk thresholds when enough active rows exist.
        active_values = train_values[train_values > 0]
        threshold_values = active_values if len(active_values) >= 10 else train_values
        risk_thresholds[target] = {
            "p95": float(np.nanquantile(threshold_values, 0.95)),
            "p99": float(np.nanquantile(threshold_values, 0.99)),
            "max": float(np.nanmax(threshold_values)),
            "basis": "active_traffic" if len(active_values) >= 10 else "all_rows",
        }

        order = np.argsort(-model.feature_importances_)[:20]
        top_features[target] = [
            {"feature": features.columns[index], "importance": float(model.feature_importances_[index])}
            for index in order
        ]

    metrics["risk_thresholds"] = risk_thresholds
    metrics["top_features"] = top_features
    bundle = {
        "models": models,
        "feature_columns": list(features.columns),
        "targets": targets,
        "interval_seconds": int(interval),
        "lags": int(args.lags),
        "windows": windows,
        "horizon": int(args.horizon),
        "risk_thresholds": risk_thresholds,
        "metrics": metrics,
        "created_at": metrics["created_at"],
        "version": args.version,
        "task": "traffic_forecast",
    }
    args.model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.model)
    save_json(metrics, args.metrics)

    report_rows: list[dict[str, object]] = []
    for target in targets:
        for name in ("random_forest", "persistence", "moving_average_3", "moving_average_6"):
            item = metrics["per_target"][target][name]
            values = item["test"] if name == "random_forest" else item
            report_rows.append(
                {
                    "target": target,
                    "model": name,
                    "MAE": values["mae"],
                    "RMSE": values["rmse"],
                    "MAPE": values["mape"],
                    "R2": values["r2"],
                }
            )

    report_lines = [
        "# Traffic forecast report",
        "",
        f"- Data: `{args.data}`",
        f"- Interval: {interval} giây",
        f"- Horizon: {args.horizon} bước",
        f"- Lags: {args.lags}; windows: {windows}",
        f"- Train: {len(train_index):,} dòng ({train_index.min()} → {train_index.max()})",
        f"- Validation: {len(val_index):,} dòng",
        f"- Test: {len(test_index):,} dòng ({test_index.min()} → {test_index.max()})",
        f"- Model: `{args.model}`",
        "",
        "## Kết quả trên test",
        "",
        markdown_table(
            report_rows,
            ["target", "model", "MAE", "RMSE", "MAPE", "R2"],
        ),
        "",
        "## Ngưỡng rủi ro (từ train)",
        "",
        "| Target | p95 | p99 | max |",
        "|---|---:|---:|---:|",
    ]
    for target in targets:
        thresholds = risk_thresholds[target]
        report_lines.append(
            f"| {target} | {thresholds['p95']:.6g} | {thresholds['p99']:.6g} | {thresholds['max']:.6g} |"
        )
    report_lines.extend(["", "## Top feature importance", ""])
    for target in targets:
        report_lines.append(f"### {target}")
        report_lines.append("")
        report_lines.append(markdown_table(top_features[target], ["feature", "importance"]))
        report_lines.append("")
    report_lines.extend(
        [
            "## Lưu ý",
            "",
            "- Đây là baseline; không dùng random split vì sẽ rò rỉ tương lai.",
            "- Model train cho 1 bước; predict_traffic.py dự báo đệ quy N bước.",
            "- CIC-IDS2017 chỉ có timestamp độ phân giải phút, nên chuỗi demo dùng 60 giây.",
            "- Với dữ liệu 5 giây thật từ Mininet/OVS, truyền `--interval-seconds 5`.",
            "- Ngưỡng rủi ro dùng p95/p99 của các bucket có traffic > 0 trong train.",
            "- Metric thấp là tín hiệu cần thêm dữ liệu/feature, không phải lỗi code.",
        ]
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Đã lưu model: {args.model.resolve()}")
    print(f"Đã lưu metrics: {args.metrics.resolve()}")
    print(f"Đã lưu report: {args.report.resolve()}")
    for target in targets:
        test_metrics = metrics["per_target"][target]["random_forest"]["test"]
        print(
            f"{target}: MAE={test_metrics['mae']:.4g} "
            f"RMSE={test_metrics['rmse']:.4g} R2={test_metrics['r2']}"
        )


if __name__ == "__main__":
    main()
