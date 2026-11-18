"""Train an operational attack-family classifier from CIC-IDS + Mininet.

The classifier deliberately predicts broad, actionable families instead of
generator implementation names. CIC-IDS2017/2018 provide cross-dataset attack
coverage; Mininet sessions keep the model adapted to the live demo extractor.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

try:
    from src.common import read_sampled_dataframe, save_json
    from src.train_mininet_lab import ATTACK_FAMILIES, load_lab_flows, session_split
except ModuleNotFoundError:
    from common import read_sampled_dataframe, save_json
    from train_mininet_lab import ATTACK_FAMILIES, load_lab_flows, session_split


ROOT = Path(__file__).resolve().parents[1]
FAMILY_LABELS: dict[str, dict[str, tuple[str, ...]]] = {
    "cic2018": {
        "DoS": (
            "DoS attacks-Hulk", "DoS attacks-GoldenEye",
            "DoS attacks-Slowloris", "DoS attacks-SlowHTTPTest",
        ),
        "DDoS": ("DDoS attacks-LOIC-HTTP", "DDOS attack-HOIC", "DDOS attack-LOIC-UDP"),
        "Brute Force": ("SSH-Bruteforce", "FTP-BruteForce"),
        "Web Attack": ("Brute Force -Web", "Brute Force -XSS", "SQL Injection"),
        "Botnet": ("Bot",),
        "Infiltration": ("Infilteration",),
    },
    "cic2017": {
        "DoS": ("DoS Hulk", "DoS GoldenEye", "DoS slowloris", "DoS Slowhttptest"),
        "DDoS": ("DDoS",),
        "Port Scan": ("PortScan",),
        "Brute Force": ("FTP-Patator", "SSH-Patator"),
        "Web Attack": (
            "Web Attack - Brute Force", "Web Attack - XSS", "Web Attack - Sql Injection",
        ),
        "Botnet": ("Bot",),
        "Infiltration": ("Infiltration",),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cic2018", type=Path, default=Path("data/processed/cse_cic_ids2018_clean.parquet"))
    parser.add_argument("--cic2017", type=Path, default=Path("data/processed/cicids2017_with_meta.parquet"))
    parser.add_argument("--lab", type=Path, default=Path("data/mininet/lab_flows.jsonl"))
    parser.add_argument("--model", type=Path, default=Path("models/attack_type_model.joblib"))
    parser.add_argument("--metrics", type=Path, default=Path("results/attack_family_metrics.json"))
    parser.add_argument("--per-family", type=int, default=20_000)
    parser.add_argument("--trees", type=int, default=400)
    parser.add_argument("--lab-weight", type=float, default=50.0)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def load_cic(path: Path, domain: str, per_family: int, random_state: int) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for index, (family, labels) in enumerate(FAMILY_LABELS[domain].items()):
        frame = read_sampled_dataframe(
            path, per_family, random_state + index,
            filter_values={"Label": list(labels)},
        )
        frame["attack_family"] = family
        frame["domain"] = domain
        parts.append(frame)
        print(f"{domain}/{family}: {len(frame):,}", flush=True)
    return pd.concat(parts, ignore_index=True)


def metrics(y_true: pd.Series, predicted: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    confidence = probabilities.max(axis=1)
    accepted = confidence >= 0.50
    correct = predicted == y_true.to_numpy(str)
    return {
        "rows": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "macro_f1": float(f1_score(y_true, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, predicted, average="weighted", zero_division=0)),
        "unknown_rate_at_0_50": float(1.0 - accepted.mean()),
        "accepted_accuracy_at_0_50": float(correct[accepted].mean()) if accepted.any() else None,
        "mean_confidence": float(confidence.mean()),
        "classification_report": classification_report(
            y_true, predicted, output_dict=True, zero_division=0
        ),
    }


def main() -> None:
    args = parse_args()
    lab, features = load_lab_flows(args.lab)
    split = session_split(lab)
    lab = lab[lab["scenario"].isin(ATTACK_FAMILIES)].copy()
    lab["attack_family"] = lab["scenario"].map(ATTACK_FAMILIES)
    lab["domain"] = "mininet"
    lab_train = lab[lab["session_id"].isin(split["train"] | split["validation"])].copy()
    lab_test = lab[lab["session_id"].isin(split["test"])].copy()

    cic = pd.concat(
        [
            load_cic(args.cic2018, "cic2018", args.per_family, args.random_state),
            load_cic(args.cic2017, "cic2017", args.per_family, args.random_state + 100),
        ],
        ignore_index=True,
    )
    cic_train, cic_test = train_test_split(
        cic, test_size=0.20, random_state=args.random_state,
        stratify=cic["attack_family"],
    )
    train = pd.concat([cic_train, lab_train], ignore_index=True)
    test = pd.concat([cic_test, lab_test], ignore_index=True)
    y_train = train["attack_family"].astype(str)
    counts = y_train.value_counts()
    class_weights = y_train.map({label: len(y_train) / (len(counts) * count) for label, count in counts.items()})
    domain_weights = np.where(train["domain"].eq("mininet"), args.lab_weight, 1.0)
    sample_weights = class_weights.to_numpy(float) * domain_weights

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=args.trees,
                    min_samples_leaf=1,
                    max_features="sqrt",
                    class_weight=None,
                    random_state=args.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(train[features], y_train, classifier__sample_weight=sample_weights)
    predicted = pipeline.predict(test[features])
    probabilities = pipeline.predict_proba(test[features])

    overall = metrics(test["attack_family"].astype(str), predicted, probabilities)
    per_domain: dict[str, Any] = {}
    for domain in sorted(test["domain"].unique()):
        mask = test["domain"].eq(domain).to_numpy()
        per_domain[domain] = metrics(
            test.loc[mask, "attack_family"].astype(str), predicted[mask], probabilities[mask]
        )

    created_at = datetime.now(timezone.utc).isoformat()
    classes = list(pipeline.named_steps["classifier"].classes_)
    bundle = {
        "pipeline": pipeline,
        "feature_columns": features,
        "task": "attack_type_prediction",
        "classes": classes,
        "created_at": created_at,
        "version": "cic17-18-mininet-families-1",
        "confidence_threshold": 0.50,
        "families": classes,
        "scenario_family_map": ATTACK_FAMILIES,
        "training_sources": {
            "cic_rows": int(len(cic_train)),
            "mininet_rows": int(len(lab_train)),
        },
        "split_strategy": "cic_stratified_plus_mininet_session_holdout",
    }
    args.model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.model)
    report = {
        "created_at": created_at,
        "version": bundle["version"],
        "classes": classes,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "class_distribution_train": {str(k): int(v) for k, v in y_train.value_counts().items()},
        "overall": overall,
        "per_domain": per_domain,
    }
    save_json(report, args.metrics)
    print("Overall:", {key: overall[key] for key in ("accuracy", "macro_f1", "unknown_rate_at_0_50")})
    for domain, values in per_domain.items():
        print(domain, {key: values[key] for key in ("accuracy", "macro_f1", "unknown_rate_at_0_50")})
    print(f"Saved {args.model} with classes={classes}")


if __name__ == "__main__":
    main()
