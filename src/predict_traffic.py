"""Forecast future packets/s and bytes/s with a trained traffic model.

Input history must contain ``timestamp`` plus the targets used at training time
(``packets_per_second`` and/or ``bytes_per_second``).  The model is recursive:
each predicted step is appended to the history before the next step is built.

Example:

    python src/predict_traffic.py ^
        --input data/processed/traffic_series_60s.csv ^
        --model models/traffic_forecast.joblib ^
        --horizon 12 ^
        --output results/traffic_forecast.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    from src.common import MODEL_DIR, RESULT_DIR, read_dataframe
    from src.traffic_features import build_feature_frame, prepare_rate_frame
except ModuleNotFoundError:  # Allows: python src/predict_traffic.py
    from common import MODEL_DIR, RESULT_DIR, read_dataframe
    from traffic_features import build_feature_frame, prepare_rate_frame


def validate_bundle(bundle: dict[str, Any]) -> None:
    required = {"models", "feature_columns", "targets", "interval_seconds", "lags", "windows"}
    missing = required - set(bundle)
    if missing:
        raise ValueError(f"Model traffic không đúng định dạng; thiếu: {sorted(missing)}")


def risk_level(predictions: dict[str, float], thresholds: dict[str, dict[str, float]]) -> str:
    """Map a forecast to LOW/MEDIUM/HIGH using training p95/p99."""
    level = "LOW"
    for target, value in predictions.items():
        target_thresholds = thresholds.get(target, {})
        p95 = target_thresholds.get("p95")
        p99 = target_thresholds.get("p99")
        if p99 is not None and value >= float(p99):
            return "HIGH"
        if p95 is not None and value >= float(p95):
            level = "MEDIUM"
    return level


def forecast_frame(
    history: pd.DataFrame,
    bundle: dict[str, Any],
    horizon: int | None = None,
) -> tuple[pd.DataFrame, str]:
    """Return a forecast frame and the maximum risk across all steps."""
    validate_bundle(bundle)
    targets = list(bundle["targets"])
    interval = int(bundle["interval_seconds"])
    lags = int(bundle["lags"])
    windows = [int(value) for value in bundle["windows"]]
    feature_columns = list(bundle["feature_columns"])
    horizon = int(horizon or bundle.get("horizon", 1))
    if horizon <= 0:
        raise ValueError("horizon phải > 0.")

    missing = {target for target in targets if target not in history.columns}
    if missing:
        raise ValueError(f"History thiếu target: {sorted(missing)}")
    if len(history) == 0:
        raise ValueError("History rỗng.")

    frame = prepare_rate_frame(history, interval, targets)
    minimum_history = max([lags, *windows]) + 1
    if len(frame) < minimum_history:
        raise ValueError(
            f"Cần ít nhất {minimum_history} điểm lịch sử, hiện có {len(frame)}. "
            "Hãy gửi thêm dữ liệu."
        )

    rows: list[dict[str, Any]] = []
    overall_risk = "LOW"
    for step in range(1, horizon + 1):
        features = build_feature_frame(frame, targets, lags, windows)
        latest = features.iloc[[-1]].reindex(columns=feature_columns)
        if latest.isna().any().any():
            raise ValueError("Không đủ lịch sử để tạo feature; hãy gửi thêm điểm.")

        predictions: dict[str, float] = {}
        for target in targets:
            value = float(bundle["models"][target].predict(latest)[0])
            predictions[target] = max(0.0, value)

        next_timestamp = frame.index[-1] + pd.Timedelta(seconds=interval)
        appended = pd.DataFrame([predictions], index=[next_timestamp])
        frame = pd.concat([frame, appended])

        step_risk = risk_level(predictions, bundle.get("risk_thresholds", {}))
        if step_risk == "HIGH" or (step_risk == "MEDIUM" and overall_risk == "LOW"):
            overall_risk = step_risk
        rows.append(
            {
                "timestamp": next_timestamp,
                "step": step,
                **predictions,
                **{
                    f"{target}_lower": max(
                        0.0,
                        value
                        - float(bundle.get("prediction_intervals", {}).get(target, {}).get("absolute_error", 0.0)),
                    )
                    for target, value in predictions.items()
                },
                **{
                    f"{target}_upper": value
                    + float(bundle.get("prediction_intervals", {}).get(target, {}).get("absolute_error", 0.0))
                    for target, value in predictions.items()
                },
                "risk_level": step_risk,
            }
        )

    return pd.DataFrame(rows), overall_risk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL_DIR / "traffic_forecast.joblib",
    )
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULT_DIR / "traffic_forecast.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model.exists():
        raise FileNotFoundError(f"Không tìm thấy model: {args.model}")
    bundle = joblib.load(args.model)
    history = read_dataframe(args.input)
    forecast, overall_risk = forecast_frame(history, bundle, args.horizon)
    forecast = forecast.copy()
    forecast["timestamp"] = forecast["timestamp"].astype(str)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    forecast.to_csv(args.output, index=False)
    print(f"Đã ghi {len(forecast):,} bước dự báo vào: {args.output.resolve()}")
    print(f"Risk tổng thể: {overall_risk}")
    print(forecast.to_string(index=False))


if __name__ == "__main__":
    main()
