"""Train lab-aware detection, attack classification, and traffic forecasting models.

The final evaluation holds out complete Mininet sessions.  CIC-IDS2018 remains a
low-weight background source for the binary detector, while scenario labels and
the short-horizon forecast are learned from the exact collector used by the UI.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

try:
    from src.common import PROCESSED_DATA, read_sampled_dataframe, save_json
    from src.traffic_features import make_supervised, prepare_rate_frame
except ModuleNotFoundError:
    from common import PROCESSED_DATA, read_sampled_dataframe, save_json
    from traffic_features import make_supervised, prepare_rate_frame


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "models"
RESULT_DIR = PROJECT_ROOT / "results"
ATTACK_SCENARIOS = (
    "SYN_FLOOD",
    "UDP_FLOOD",
    "ICMP_FLOOD",
    "PORT_SCAN",
    "CONNECTION_BURST",
    "BRUTE_FORCE",
    "WEB_ATTACK",
)
ATTACK_FAMILIES = {
    "SYN_FLOOD": "DoS",
    "CONNECTION_BURST": "DoS",
    "UDP_FLOOD": "DDoS",
    "ICMP_FLOOD": "DDoS",
    "PORT_SCAN": "Port Scan",
    "BRUTE_FORCE": "Brute Force",
    "WEB_ATTACK": "Web Attack",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flows", type=Path, default=Path("data/mininet/lab_flows.jsonl"))
    parser.add_argument("--series", type=Path, default=Path("data/mininet/lab_series.csv"))
    parser.add_argument("--cic-data", type=Path, default=PROCESSED_DATA)
    parser.add_argument("--cic-rows", type=int, default=4000)
    parser.add_argument("--trees", type=int, default=300)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--interval-seconds", type=int, default=1)
    parser.add_argument("--lags", type=int, default=3)
    parser.add_argument("--windows", default="2,3")
    parser.add_argument(
        "--tasks", nargs="+", choices=("detection", "attack", "forecast"),
        default=("detection", "attack", "forecast"),
        help="Chỉ huấn luyện các tác vụ được chọn.",
    )
    return parser.parse_args()


def load_lab_flows(path: Path) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy flow Mininet: {path}")
    rows: list[dict[str, Any]] = []
    feature_names: list[str] | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            features = item["flow"]["features"]
            names = list(features)
            if feature_names is None:
                feature_names = names
            elif set(names) != set(feature_names):
                raise ValueError("Các flow Mininet không có cùng schema đặc trưng")
            rows.append(
                {
                    **{name: features[name] for name in feature_names},
                    "session_id": str(item["session_id"]),
                    "scenario": str(item["scenario"]),
                    "target": int(item["binary_label"] == "ATTACK"),
                    "sequence": int(item["sequence"]),
                }
            )
    if not rows or feature_names is None:
        raise ValueError("Dataset Mininet rỗng")
    return pd.DataFrame(rows), feature_names


def session_split(frame: pd.DataFrame) -> dict[str, set[str]]:
    split = {"train": set(), "validation": set(), "test": set()}
    for scenario, part in frame.groupby("scenario", sort=True):
        sessions = list(dict.fromkeys(part["session_id"].astype(str)))
        if len(sessions) < 5:
            raise ValueError(f"Cần ít nhất 5 session cho {scenario}, hiện có {len(sessions)}")
        test_count = max(1, round(len(sessions) * 0.2))
        validation_count = max(1, round(len(sessions) * 0.2))
        split["test"].update(sessions[-test_count:])
        split["validation"].update(sessions[-test_count - validation_count : -test_count])
        split["train"].update(sessions[: -test_count - validation_count])
    return split


def balanced_weights(labels: pd.Series) -> np.ndarray:
    counts = labels.value_counts()
    return labels.map({label: 1.0 / count for label, count in counts.items()}).to_numpy(float)


def classifier(trees: int, random_state: int) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=trees,
                    min_samples_leaf=1,
                    max_features="sqrt",
                    class_weight="balanced_subsample",
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def choose_threshold(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, dict[str, float]]:
    candidates: list[dict[str, float]] = []
    for threshold in np.linspace(0.05, 0.95, 181):
        predicted = (scores >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
        fpr = fp / max(1, fp + tn)
        candidates.append(
            {
                "threshold": float(threshold),
                "fpr": float(fpr),
                "precision": float(precision_score(y_true, predicted, zero_division=0)),
                "recall": float(recall_score(y_true, predicted, zero_division=0)),
                "f1": float(f1_score(y_true, predicted, zero_division=0)),
            }
        )
    feasible = [item for item in candidates if item["fpr"] <= 0.05]
    pool = feasible or candidates
    best = max(pool, key=lambda item: (item["f1"], item["recall"], -item["fpr"]))
    return best["threshold"], best


def binary_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = (scores >= threshold).astype(int)
    return {
        "rows": int(len(y_true)),
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) == 2 else None,
        "confusion_matrix": confusion_matrix(y_true, predicted, labels=[0, 1]).tolist(),
    }


def backup_models() -> None:
    target = MODEL_DIR / "baseline_cic"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("detection_model.joblib", "attack_type_model.joblib", "traffic_forecast.joblib"):
        source = MODEL_DIR / name
        backup = target / name
        if source.exists() and not backup.exists():
            shutil.copy2(source, backup)


def train_detection(
    lab: pd.DataFrame,
    features: list[str],
    split: dict[str, set[str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    train = lab[lab["session_id"].isin(split["train"])].copy()
    validation = lab[lab["session_id"].isin(split["validation"])].copy()
    test = lab[lab["session_id"].isin(split["test"])].copy()

    X_train = train[features]
    y_train = train["target"].astype(int)
    weights = balanced_weights(train["scenario"])

    cic_rows = 0
    if args.cic_data.exists() and args.cic_rows > 0:
        cic = read_sampled_dataframe(args.cic_data, args.cic_rows * 2, args.random_state)
        cic = cic.dropna(subset=["target"])
        benign = cic[cic["target"].astype(int) == 0].head(args.cic_rows // 2)
        attack = cic[cic["target"].astype(int) == 1].head(args.cic_rows // 2)
        cic = pd.concat([benign, attack], ignore_index=True)
        if len(cic):
            missing = set(features) - set(cic.columns)
            if missing:
                raise ValueError(f"CIC thiếu {len(missing)} feature của Mininet: {sorted(missing)[:5]}")
            cic_rows = len(cic)
            # CIC contributes background knowledge but cannot dominate the lab domain.
            cic_weight = np.full(cic_rows, 0.5 / cic_rows, dtype=float)
            X_train = pd.concat([X_train, cic[features]], ignore_index=True)
            y_train = pd.concat([y_train, cic["target"].astype(int)], ignore_index=True)
            weights = np.concatenate([weights, cic_weight])

    model = classifier(args.trees, args.random_state)
    model.fit(X_train, y_train, classifier__sample_weight=weights)
    validation_scores = model.predict_proba(validation[features])[:, 1]
    threshold, calibration = choose_threshold(validation["target"].to_numpy(int), validation_scores)
    test_scores = model.predict_proba(test[features])[:, 1]

    per_scenario = {}
    for scenario, part in test.groupby("scenario"):
        indexes = part.index
        positions = test.index.get_indexer(indexes)
        per_scenario[scenario] = binary_metrics(
            part["target"].to_numpy(int), test_scores[positions], threshold
        )

    created_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "pipeline": model,
        "feature_columns": features,
        "task": "binary_detection",
        "classes": {0: "BENIGN", 1: "ATTACK"},
        "created_at": created_at,
        "version": "mininet-lab-2",
        "split_strategy": "grouped_by_mininet_session",
        "decision_threshold": float(threshold),
        "training_sources": {"mininet_rows": int(len(train)), "cic_rows": int(cic_rows)},
    }
    joblib.dump(bundle, MODEL_DIR / "detection_model.joblib")
    metrics = {
        "created_at": created_at,
        "train_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "test_rows": int(len(test)),
        "cic_background_rows": int(cic_rows),
        "feature_count": len(features),
        "calibration": calibration,
        "test": binary_metrics(test["target"].to_numpy(int), test_scores, threshold),
        "per_scenario": per_scenario,
        "sessions": {name: sorted(values) for name, values in split.items()},
    }
    save_json(metrics, RESULT_DIR / "mininet_detection_metrics.json")
    return metrics


def train_attack_type(
    lab: pd.DataFrame,
    features: list[str],
    split: dict[str, set[str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    attacks = lab[lab["scenario"].isin(ATTACK_SCENARIOS)].copy()
    attacks["attack_family"] = attacks["scenario"].map(ATTACK_FAMILIES)
    train = attacks[attacks["session_id"].isin(split["train"])]
    test = attacks[attacks["session_id"].isin(split["test"])]
    model = classifier(args.trees, args.random_state + 1)
    model.fit(
        train[features],
        train["attack_family"],
        classifier__sample_weight=balanced_weights(train["attack_family"]),
    )
    predicted = model.predict(test[features])
    probabilities = model.predict_proba(test[features])
    created_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "pipeline": model,
        "feature_columns": features,
        "task": "attack_type_prediction",
        "classes": list(model.named_steps["classifier"].classes_),
        "created_at": created_at,
        "version": "mininet-lab-families-1",
        "split_strategy": "grouped_by_mininet_session",
        "scenario_family_map": ATTACK_FAMILIES,
    }
    joblib.dump(bundle, MODEL_DIR / "attack_type_model.joblib")
    metrics = {
        "created_at": created_at,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "accuracy": float(accuracy_score(test["attack_family"], predicted)),
        "macro_f1": float(f1_score(test["attack_family"], predicted, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(test["attack_family"], predicted, average="weighted", zero_division=0)),
        "classification_report": classification_report(
            test["attack_family"], predicted, output_dict=True, zero_division=0
        ),
        "mean_confidence": float(np.max(probabilities, axis=1).mean()),
        "confusion_matrix": confusion_matrix(
            test["attack_family"], predicted, labels=list(model.named_steps["classifier"].classes_)
        ).tolist(),
        "classes": list(model.named_steps["classifier"].classes_),
    }
    save_json(metrics, RESULT_DIR / "mininet_attack_type_metrics.json")
    return metrics


def build_forecast_rows(
    series: pd.DataFrame,
    sessions: set[str],
    interval: int,
    lags: int,
    windows: list[int],
) -> tuple[pd.DataFrame, dict[str, pd.Series], pd.DataFrame]:
    feature_parts: list[pd.DataFrame] = []
    target_parts: dict[str, list[pd.Series]] = {
        "packets_per_second": [],
        "bytes_per_second": [],
    }
    baseline_parts: list[pd.DataFrame] = []
    for session_id, part in series[series["session_id"].isin(sessions)].groupby("session_id"):
        frame = prepare_rate_frame(
            part.rename(columns={"observed_at": "timestamp"}),
            interval,
            list(target_parts),
        )
        X, targets, baselines = make_supervised(frame, list(target_parts), lags, windows, 1)
        if X.empty:
            continue
        X = X.copy()
        X["__session_id"] = session_id
        feature_parts.append(X)
        for target, values in targets.items():
            target_parts[target].append(values)
        baseline_parts.append(baselines)
    if not feature_parts:
        raise ValueError("Không đủ chuỗi Mininet để tạo feature dự báo")
    return (
        pd.concat(feature_parts),
        {target: pd.concat(parts) for target, parts in target_parts.items()},
        pd.concat(baseline_parts),
    )


def regression_metrics(y_true: pd.Series, prediction: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, prediction))),
        "r2": float(r2_score(y_true, prediction)) if len(y_true) > 1 else 0.0,
    }


def train_forecast(series_path: Path, split: dict[str, set[str]], args: argparse.Namespace) -> dict[str, Any]:
    series = pd.read_csv(series_path)
    windows = sorted({int(value) for value in args.windows.split(",") if value.strip()})
    X_train, y_train, _ = build_forecast_rows(
        series, split["train"], args.interval_seconds, args.lags, windows
    )
    X_test, y_test, baselines = build_forecast_rows(
        series, split["test"], args.interval_seconds, args.lags, windows
    )
    train_sessions = X_train.pop("__session_id")
    test_sessions = X_test.pop("__session_id")
    del train_sessions, test_sessions

    models: dict[str, RandomForestRegressor] = {}
    per_target: dict[str, Any] = {}
    thresholds: dict[str, dict[str, float]] = {}
    prediction_intervals: dict[str, dict[str, float]] = {}
    for index, target in enumerate(y_train):
        model = RandomForestRegressor(
            n_estimators=args.trees,
            min_samples_leaf=2,
            max_features=0.8,
            random_state=args.random_state + 10 + index,
            n_jobs=-1,
        )
        model.fit(X_train, y_train[target])
        prediction = model.predict(X_test)
        per_target[target] = {
            "random_forest": regression_metrics(y_test[target], prediction),
            "persistence": regression_metrics(y_test[target], baselines[f"{target}_persistence"]),
        }
        absolute_error = np.abs(y_test[target].to_numpy(dtype=float) - prediction)
        prediction_intervals[target] = {
            "coverage": 0.95,
            "absolute_error": float(np.quantile(absolute_error, 0.95)),
        }
        active = y_train[target][y_train[target] > 0]
        basis = active if len(active) >= 10 else y_train[target]
        thresholds[target] = {
            "p95": float(np.quantile(basis, 0.95)),
            "p99": float(np.quantile(basis, 0.99)),
            "max": float(np.max(basis)),
        }
        models[target] = model

    created_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "models": models,
        "feature_columns": list(X_train.columns),
        "targets": list(y_train),
        "interval_seconds": int(args.interval_seconds),
        "lags": int(args.lags),
        "windows": windows,
        "horizon": 1,
        "risk_thresholds": thresholds,
        "prediction_intervals": prediction_intervals,
        "evaluation_metrics": per_target,
        "created_at": created_at,
        "version": "mininet-traffic-3",
        "task": "traffic_forecast",
        "split_strategy": "grouped_by_mininet_session",
    }
    joblib.dump(bundle, MODEL_DIR / "traffic_forecast.joblib")
    metrics = {
        "created_at": created_at,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_count": int(len(X_train.columns)),
        "interval_seconds": int(args.interval_seconds),
        "per_target": per_target,
        "risk_thresholds": thresholds,
        "prediction_intervals": prediction_intervals,
    }
    save_json(metrics, RESULT_DIR / "mininet_traffic_forecast_metrics.json")
    return metrics


def main() -> None:
    args = parse_args()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    backup_models()
    lab, features = load_lab_flows(args.flows)
    split = session_split(lab)
    print(f"Rows={len(lab):,}; sessions={lab['session_id'].nunique()}; {dict(Counter(lab['scenario']))}")
    if "detection" in args.tasks:
        detection = train_detection(lab, features, split, args)
        print("Detection test:", detection["test"])
    if "attack" in args.tasks:
        attack_type = train_attack_type(lab, features, split, args)
        print("Attack type:", {k: attack_type[k] for k in ("accuracy", "macro_f1", "weighted_f1")})
    if "forecast" in args.tasks:
        forecast = train_forecast(args.series, split, args)
        print("Forecast:", forecast["per_target"])


if __name__ == "__main__":
    main()
