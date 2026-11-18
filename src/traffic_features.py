"""Shared feature engineering for traffic forecasting (train + inference).

The module works on a regular time-indexed frame with one row per interval.
Targets are rates (packets/s, bytes/s), so resampling uses ``mean``.  Feature
building is deliberately causal: row ``t`` only uses values up to ``t`` and is
used to predict ``t + horizon``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

DEFAULT_TARGETS = ("packets_per_second", "bytes_per_second")
DEFAULT_WINDOWS = (3, 6, 12, 24)


def parse_timestamps(values: pd.Series) -> pd.Series:
    """Parse ISO timestamps and CIC-IDS day-first timestamps.

    CIC-IDS2017 uses ``03/07/2017 08:55:58`` (day/month/year) and also
    ``7/7/2017 3:30``.  ISO timestamps such as ``2017-07-03 01:00:00`` must not
    be parsed with ``dayfirst=True`` because that swaps month and day.
    """
    text = values.astype(str)
    if text.str.contains("/", regex=False).any():
        try:
            parsed = pd.to_datetime(values, errors="coerce", dayfirst=True, format="mixed")
        except (TypeError, ValueError):
            parsed = pd.to_datetime(values, errors="coerce", dayfirst=True)
    else:
        try:
            parsed = pd.to_datetime(values, errors="coerce", format="mixed")
        except (TypeError, ValueError):
            parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().all():
        parsed = pd.to_datetime(values, errors="coerce")
    return parsed


def infer_interval_seconds(frame: pd.DataFrame, timestamp_column: str = "timestamp") -> int:
    """Infer the dominant sampling interval from timestamps."""
    if timestamp_column not in frame:
        raise ValueError(f"Thiếu cột thời gian: {timestamp_column}")
    parsed = parse_timestamps(frame[timestamp_column]).dropna().sort_values()
    diffs = parsed.diff().dt.total_seconds().dropna()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return 5
    return max(1, int(round(float(diffs.median()))))


def prepare_rate_frame(
    frame: pd.DataFrame,
    interval_seconds: int,
    targets: Sequence[str] = DEFAULT_TARGETS,
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    """Return a regular, gap-filled frame indexed by timestamp.

    Short gaps (up to 3 intervals) are interpolated.  Longer gaps are treated
    as zero traffic; this is appropriate for the offline CIC-IDS capture where
    no flows were recorded, but a production collector should mark collector
    downtime separately.
    """
    missing = {timestamp_column, *targets} - set(frame.columns)
    if missing:
        raise ValueError(f"Thiếu cột: {sorted(missing)}")

    work = frame.copy()
    work[timestamp_column] = parse_timestamps(work[timestamp_column])
    work = work.dropna(subset=[timestamp_column]).sort_values(timestamp_column)
    for target in targets:
        work[target] = pd.to_numeric(work[target], errors="coerce")

    work = work.set_index(timestamp_column)
    # Duplicate timestamps can appear when a caller sends multiple rows per
    # interval; average the rates instead of silently keeping the last row.
    work = work.groupby(level=0)[list(targets)].mean()
    work = work.resample(f"{int(interval_seconds)}s").mean()
    work[list(targets)] = (
        work[list(targets)]
        .interpolate(limit=3, limit_direction="both")
        .fillna(0.0)
        .clip(lower=0.0)
    )
    return work


def build_feature_frame(
    frame: pd.DataFrame,
    targets: Sequence[str] = DEFAULT_TARGETS,
    lags: int = 12,
    windows: Sequence[int] = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    """Build lag, rolling-window, difference and time-of-day features."""
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("frame phải có DatetimeIndex.")

    out: dict[str, pd.Series] = {}
    for target in targets:
        series = frame[target].astype(float)
        for lag in range(1, int(lags) + 1):
            out[f"{target}_lag_{lag}"] = series.shift(lag)
        for window in windows:
            window = int(window)
            rolling = series.rolling(window=window, min_periods=window)
            out[f"{target}_roll_mean_{window}"] = rolling.mean()
            out[f"{target}_roll_std_{window}"] = rolling.std()
            out[f"{target}_roll_min_{window}"] = rolling.min()
            out[f"{target}_roll_max_{window}"] = rolling.max()
        out[f"{target}_diff_1"] = series.diff(1)
        out[f"{target}_diff_3"] = series.diff(3)

    index = frame.index
    seconds = index.hour * 3600 + index.minute * 60 + index.second
    minute_of_hour = index.minute * 60 + index.second
    out["hour_sin"] = np.sin(2 * np.pi * seconds / 86400.0)
    out["hour_cos"] = np.cos(2 * np.pi * seconds / 86400.0)
    out["minute_sin"] = np.sin(2 * np.pi * minute_of_hour / 3600.0)
    out["minute_cos"] = np.cos(2 * np.pi * minute_of_hour / 3600.0)
    out["dow_sin"] = np.sin(2 * np.pi * index.dayofweek / 7.0)
    out["dow_cos"] = np.cos(2 * np.pi * index.dayofweek / 7.0)
    return pd.DataFrame(out, index=index)


def make_supervised(
    frame: pd.DataFrame,
    targets: Sequence[str],
    lags: int,
    windows: Sequence[int],
    horizon: int,
) -> tuple[pd.DataFrame, dict[str, pd.Series], pd.DataFrame]:
    """Return ``X``, per-target ``y`` and simple forecast baselines.

    Rows with any NaN feature or target are dropped.  Baselines are aligned to
    the same rows so they can be compared directly on the test split.
    """
    features = build_feature_frame(frame, targets, lags, windows)
    target_values = {target: frame[target].shift(-int(horizon)) for target in targets}

    baseline_values: dict[str, pd.Series] = {}
    for target in targets:
        series = frame[target]
        baseline_values[f"{target}_persistence"] = series
        baseline_values[f"{target}_ma3"] = series.rolling(3, min_periods=1).mean()
        baseline_values[f"{target}_ma6"] = series.rolling(6, min_periods=1).mean()
    baselines = pd.DataFrame(baseline_values, index=frame.index)

    valid = features.notna().all(axis=1)
    for series in target_values.values():
        valid &= series.notna()

    return (
        features.loc[valid],
        {name: values.loc[valid] for name, values in target_values.items()},
        baselines.loc[valid],
    )
