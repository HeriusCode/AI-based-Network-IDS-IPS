"""Evaluate alert-budget policies (top-k / top-q) on saved LODO scores.

The LODO score files contain one row per test flow with the model score, the
ground-truth target, and the attack family.  This script ranks flows by score
inside each held-out day and reports what a fixed alert budget would catch.
It does not train or tune anything, so it is safe to use after the fact.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.common import RESULT_DIR, ensure_output_dirs, save_json
except ModuleNotFoundError:
    from common import RESULT_DIR, ensure_output_dirs, save_json


DEFAULT_K = (10, 50, 100, 500, 1_000, 5_000, 10_000)
DEFAULT_Q = (0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20)
DEFAULT_VARIANTS = ("raw", "robust")
DEFAULT_CALIBRATED_FPRS = (0.01, 0.05)
RECALL_TARGETS = (0.25, 0.5, 0.8)


def fold_id(frame: pd.DataFrame) -> int:
    return int(frame["fold"].iloc[0])


def load_folds(score_root: Path, variant: str) -> list[pd.DataFrame]:
    directory = score_root / variant
    files = sorted(directory.glob("fold_*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy score cho variant '{variant}' trong {directory}. "
            "Hãy chạy train_normalized.py với --save-scores trước."
        )
    folds: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_parquet(path)
        required = {"fold", "target", "score"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{path} thiếu cột: {sorted(missing)}")
        if "family" not in frame:
            frame["family"] = "Unknown"
        if "capture_date" not in frame:
            frame["capture_date"] = ""
        frame["target"] = frame["target"].astype(int)
        frame["score"] = pd.to_numeric(frame["score"], errors="coerce").fillna(0.0)
        frame["family"] = frame["family"].fillna("Unknown").astype(str)
        folds.append(frame.reset_index(drop=True))
    return folds


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _ranking(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = frame["target"].to_numpy(dtype=np.int8)
    scores = frame["score"].to_numpy(dtype=float)
    order = np.argsort(-scores, kind="mergesort")
    return y, scores, order


def topk_row(frame: pd.DataFrame, k: int) -> dict[str, object]:
    """Metrics for exactly k alerts, plus the threshold-at-k variant.

    Random Forest scores are discrete, so many flows can share the k-th score.
    ``tp_best`` / ``tp_worst`` bound the effect of choosing which tied rows fill
    the remaining slots.  The threshold-at-k columns show what a real threshold
    implementation would alert (usually more than k).
    """
    y, scores, order = _ranking(frame)
    n = len(y)
    if n == 0:
        raise ValueError("Fold rỗng.")
    k = max(1, min(int(k), n))
    chosen = order[:k]
    attacks = int(y.sum())
    benign = n - attacks
    tp = int(y[chosen].sum())
    fp = k - tp
    fn = attacks - tp
    tn = benign - fp

    threshold = float(scores[chosen[-1]])
    predicted = scores >= threshold
    tp_threshold = int(np.sum(predicted & (y == 1)))
    fp_threshold = int(np.sum(predicted & (y == 0)))
    alerts_threshold = int(predicted.sum())

    above = scores > threshold
    ties = scores == threshold
    tp_above = int(np.sum(above & (y == 1)))
    attack_ties = int(np.sum(ties & (y == 1)))
    benign_ties = int(np.sum(ties & (y == 0)))
    slots = k - int(above.sum())
    tp_best = tp_above + min(slots, attack_ties)
    tp_worst = tp_above + max(0, slots - benign_ties)

    return {
        "fold": fold_id(frame),
        "capture_date": str(frame["capture_date"].iloc[0]),
        "rows": n,
        "attacks": attacks,
        "benign": benign,
        "k": k,
        "alerts": k,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / k,
        "recall": tp / attacks if attacks else 0.0,
        "f1": _f1(tp / k, tp / attacks if attacks else 0.0),
        "fpr": fp / benign if benign else 0.0,
        "threshold": threshold,
        "alerts_at_threshold": alerts_threshold,
        "tp_at_threshold": tp_threshold,
        "fp_at_threshold": fp_threshold,
        "precision_at_threshold": tp_threshold / alerts_threshold
        if alerts_threshold
        else 0.0,
        "recall_at_threshold": tp_threshold / attacks if attacks else 0.0,
        "tp_best": tp_best,
        "tp_worst": tp_worst,
        "precision_best": tp_best / k,
        "precision_worst": tp_worst / k,
        "recall_best": tp_best / attacks if attacks else 0.0,
        "recall_worst": tp_worst / attacks if attacks else 0.0,
    }


def threshold_row(frame: pd.DataFrame, threshold: float) -> dict[str, object]:
    y, scores, _ = _ranking(frame)
    n = len(y)
    attacks = int(y.sum())
    benign = n - attacks
    predicted = scores >= float(threshold)
    tp = int(np.sum(predicted & (y == 1)))
    fp = int(np.sum(predicted & (y == 0)))
    fn = attacks - tp
    tn = benign - fp
    alerts = int(predicted.sum())
    precision = tp / alerts if alerts else 0.0
    recall = tp / attacks if attacks else 0.0
    return {
        "fold": fold_id(frame),
        "capture_date": str(frame["capture_date"].iloc[0]),
        "rows": n,
        "attacks": attacks,
        "benign": benign,
        "k": None,
        "alerts": alerts,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "fpr": fp / benign if benign else 0.0,
        "threshold": float(threshold),
        "alerts_at_threshold": alerts,
        "tp_at_threshold": tp,
        "fp_at_threshold": fp,
        "precision_at_threshold": precision,
        "recall_at_threshold": recall,
        "tp_best": tp,
        "tp_worst": tp,
        "precision_best": precision,
        "precision_worst": precision,
        "recall_best": recall,
        "recall_worst": recall,
    }


def recall_target_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Smallest alert budget (in flows) needed to reach each recall target."""
    y, _, order = _ranking(frame)
    attacks = int(y.sum())
    n = len(y)
    if attacks == 0:
        return [
            {
                "target": target,
                "k": None,
                "fraction": None,
                "max_recall": 0.0,
            }
            for target in RECALL_TARGETS
        ]
    cumulative_tp = np.cumsum(y[order])
    rows: list[dict[str, object]] = []
    for target in RECALL_TARGETS:
        needed = int(math.ceil(target * attacks))
        index = int(np.searchsorted(cumulative_tp, needed, side="left"))
        k = min(index + 1, n)
        rows.append(
            {
                "target": target,
                "k": k,
                "fraction": k / n,
                "max_recall": float(cumulative_tp[-1] / attacks),
            }
        )
    return rows


def summarize_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {}
    tp = sum(int(row["tp"]) for row in rows)
    fp = sum(int(row["fp"]) for row in rows)
    fn = sum(int(row["fn"]) for row in rows)
    tn = sum(int(row["tn"]) for row in rows)
    alerts = sum(int(row["alerts"]) for row in rows)
    alerts_threshold = sum(int(row["alerts_at_threshold"]) for row in rows)
    tp_threshold = sum(int(row["tp_at_threshold"]) for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    precision_threshold = (
        tp_threshold / alerts_threshold if alerts_threshold else 0.0
    )
    recall_threshold = tp_threshold / (tp + fn) if tp + fn else 0.0
    return {
        "folds": len(rows),
        "rows": sum(int(row["rows"]) for row in rows),
        "attacks": tp + fn,
        "benign": fp + tn,
        "alerts": alerts,
        "alerts_per_day": alerts / len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "alerts_at_threshold": alerts_threshold,
        "alerts_at_threshold_per_day": alerts_threshold / len(rows),
        "tp_at_threshold": tp_threshold,
        "precision_at_threshold": precision_threshold,
        "recall_at_threshold": recall_threshold,
        "f1_at_threshold": _f1(precision_threshold, recall_threshold),
    }


def recall_ceiling(rows: list[dict[str, object]]) -> float | None:
    """Largest recall achievable with these per-day budgets.

    A day cannot contribute more true positives than its number of attacks, so
    summing k over days overestimates the ceiling when a day has few attacks.
    """
    if not rows or any(row.get("k") is None for row in rows):
        return None
    attacks = sum(int(row["attacks"]) for row in rows)
    if attacks == 0:
        return None
    possible = sum(
        min(int(row["k"]), int(row["attacks"])) for row in rows
    )
    return min(1.0, possible / attacks)


def macro_stats(rows: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    metrics = ("precision", "recall", "f1", "fpr")
    return {
        metric: {
            "mean": float(np.mean([row[metric] for row in rows])),
            "std": float(np.std([row[metric] for row in rows])),
        }
        for metric in metrics
    }


def load_thresholds(path: Path) -> dict[int, dict[float, float]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    thresholds: dict[int, dict[float, float]] = {}
    for row in payload.get("folds", []):
        fold = int(row["fold"])
        values: dict[float, float] = {}
        for key, value in (row.get("thresholds") or {}).items():
            try:
                values[float(key)] = float(value)
            except (TypeError, ValueError):
                continue
        for alpha in DEFAULT_CALIBRATED_FPRS:
            key = f"fpr_{alpha}"
            detail = row.get(key)
            if isinstance(detail, dict) and detail.get("threshold") is not None:
                values.setdefault(float(alpha), float(detail["threshold"]))
        if values:
            thresholds[fold] = values
    return thresholds


def family_summary(
    folds: list[pd.DataFrame],
    budget,
) -> list[dict[str, object]]:
    totals: dict[str, int] = {}
    true_positives: dict[str, int] = {}
    alert_counts: dict[str, int] = {}
    total_alerts = 0
    for frame in folds:
        y = frame["target"].to_numpy(dtype=np.int8)
        _, _, order = _ranking(frame)
        k = max(1, min(int(budget(frame)), len(frame)))
        selected = frame.iloc[order[:k]]
        total_alerts += k
        for family, count in frame.loc[y == 1, "family"].value_counts().items():
            totals[str(family)] = totals.get(str(family), 0) + int(count)
        selected_attacks = selected.loc[selected["target"] == 1, "family"]
        for family, count in selected_attacks.value_counts().items():
            true_positives[str(family)] = true_positives.get(str(family), 0) + int(count)
        for family, count in selected["family"].value_counts().items():
            alert_counts[str(family)] = alert_counts.get(str(family), 0) + int(count)

    rows: list[dict[str, object]] = []
    for family in sorted(totals, key=lambda name: (-totals[name], name)):
        attacks = totals[family]
        tp = true_positives.get(family, 0)
        alerts = alert_counts.get(family, 0)
        rows.append(
            {
                "family": family,
                "attacks": attacks,
                "alerts": alerts,
                "tp": tp,
                "recall": tp / attacks if attacks else 0.0,
                "precision": tp / alerts if alerts else 0.0,
                "alert_share": alerts / total_alerts if total_alerts else 0.0,
            }
        )
    return rows


def build_policies(
    folds: list[pd.DataFrame],
    k_values: list[int],
    quantiles: list[float],
    thresholds: dict[int, dict[float, float]],
    calibrated_fprs: list[float],
) -> dict[str, dict[str, object]]:
    policies: dict[str, dict[str, object]] = {}

    for k in k_values:
        policies[f"top_k_{k}"] = {
            "kind": "top_k",
            "budget": k,
            "rows": [topk_row(frame, k) for frame in folds],
        }

    for q in quantiles:
        policies[f"top_q_{q}"] = {
            "kind": "top_q",
            "budget": q,
            "rows": [
                topk_row(frame, max(1, math.ceil(q * len(frame)))) for frame in folds
            ],
        }

    policies["fixed_0.5"] = {
        "kind": "fixed",
        "budget": 0.5,
        "rows": [threshold_row(frame, 0.5) for frame in folds],
    }

    for alpha in calibrated_fprs:
        rows = []
        for frame in folds:
            threshold = thresholds.get(fold_id(frame), {}).get(float(alpha))
            if threshold is None:
                continue
            rows.append(threshold_row(frame, threshold))
        if rows:
            policies[f"cal_fpr_{alpha}"] = {
                "kind": "calibrated",
                "budget": alpha,
                "rows": rows,
            }

    return policies


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    score_root = Path(args.score_dir)
    payload: dict[str, object] = {
        "protocol": (
            "LODO: train 8 ngày, validation là ngày liền trước, test là ngày bị giữ. "
            "Score từng flow trên ngày test được xếp hạng giảm dần; top-k là ngân sách "
            "alert tuyệt đối mỗi ngày, top-q là tỷ lệ flow mỗi ngày. Không dùng nhãn test "
            "để chọn ngưỡng hay xếp hạng."
        ),
        "score_dir": str(score_root),
        "k_values": list(args.k_values),
        "quantiles": list(args.quantiles),
        "variants": {},
    }

    for variant in args.variants:
        folds = load_folds(score_root, variant)
        metrics_path = (
            Path(args.metrics)
            if args.metrics
            else RESULT_DIR / f"normalized_{variant}_metrics.json"
        )
        thresholds = load_thresholds(metrics_path)
        policies = build_policies(
            folds,
            list(args.k_values),
            list(args.quantiles),
            thresholds,
            list(args.calibrated_fprs),
        )

        variant_payload: dict[str, object] = {
            "metrics_path": str(metrics_path),
            "thresholds_found": bool(thresholds),
            "folds": [
                {
                    "fold": fold_id(frame),
                    "capture_date": str(frame["capture_date"].iloc[0]),
                    "rows": int(len(frame)),
                    "attacks": int(frame["target"].sum()),
                }
                for frame in folds
            ],
            "recall_targets": [
                {
                    "fold": fold_id(frame),
                    "capture_date": str(frame["capture_date"].iloc[0]),
                    "attacks": int(frame["target"].sum()),
                    "targets": recall_target_rows(frame),
                }
                for frame in folds
            ],
            "policies": {},
            "per_family": {},
        }

        for name, policy in policies.items():
            rows = policy["rows"]
            variant_payload["policies"][name] = {
                "kind": policy["kind"],
                "budget": policy["budget"],
                "per_fold": rows,
                "pooled": summarize_rows(rows),
                "macro": macro_stats(rows),
            }

        family_budgets = {}
        for k in (1_000, 5_000):
            name = f"top_k_{k}"
            if name in policies:
                family_budgets[name] = lambda frame, value=k: value
        for q in (0.01, 0.05):
            name = f"top_q_{q}"
            if name in policies:
                family_budgets[name] = (
                    lambda frame, value=q: max(1, math.ceil(value * len(frame)))
                )

        for name, budget in family_budgets.items():
            variant_payload["per_family"][name] = family_summary(folds, budget)

        payload["variants"][variant] = variant_payload

    return payload


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.2%}"


def _num(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def write_report(payload: dict[str, object], path: Path) -> None:
    variants = payload["variants"]
    k_values = payload["k_values"]
    quantiles = payload["quantiles"]
    n_folds = max(
        (len(data.get("folds", [])) for data in variants.values()), default=0
    )

    lines = [
        "# Ngân sách cảnh báo trên LODO",
        "",
        "## Thiết lập",
        "",
        f"- Số fold thực tế: {n_folds}.",
        f"- {payload['protocol']}",
        "- Top-k xếp hạng score giảm dần trong từng ngày. Nhãn test chỉ dùng để đánh giá.",
        "- Random Forest cho score rời rạc, nên nhiều flow có cùng score tại vị trí k. "
        "Cột `Alert thực tế/ngày` dùng ngưỡng tại vị trí k (alert tất cả flow có score "
        "bằng ngưỡng đó), vì vậy có thể nhiều hơn k.",
        "- Các mức 10–20% flow/ngày chỉ dùng để xem trần recall, không phải ngân sách "
        "vận hành thực tế.",
        "",
        "## Ngân sách tuyệt đối (alert/ngày)",
        "",
        "| k/ngày | Variant | Recall | Recall ceiling | Precision | F1 | FPR | Alert thực tế/ngày |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for k in k_values:
        for variant, data in variants.items():
            policy = data["policies"].get(f"top_k_{k}")
            if not policy:
                continue
            pooled = policy["pooled"]
            ceiling = recall_ceiling(policy["per_fold"]) or 0.0
            lines.append(
                f"| {k:,} | {variant} | {_pct(pooled['recall'])} | "
                f"{_pct(ceiling)} | {_pct(pooled['precision'])} | "
                f"{pooled['f1']:.4f} | {_pct(pooled['fpr'])} | "
                f"{_num(pooled['alerts_at_threshold_per_day'], 1)} |"
            )

    lines.extend(
        [
            "",
            "## Ngân sách theo tỷ lệ flow/ngày",
            "",
            "| % flow/ngày | Variant | Alert/ngày | Recall | Recall ceiling | Precision | F1 | FPR |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for q in quantiles:
        for variant, data in variants.items():
            policy = data["policies"].get(f"top_q_{q}")
            if not policy:
                continue
            pooled = policy["pooled"]
            ceiling = recall_ceiling(policy["per_fold"]) or 0.0
            lines.append(
                f"| {q:.1%} | {variant} | {_num(pooled['alerts_per_day'], 1)} | "
                f"{_pct(pooled['recall'])} | {_pct(ceiling)} | "
                f"{_pct(pooled['precision'])} | {pooled['f1']:.4f} | "
                f"{_pct(pooled['fpr'])} |"
            )

    lines.extend(
        [
            "",
            "## Budget cần để đạt recall mục tiêu (theo flow)",
            "",
            "| Recall mục tiêu | Variant | Số fold | Budget trung bình | Median | Min | Max |",
            "|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    for target in RECALL_TARGETS:
        for variant, data in variants.items():
            fractions = []
            for fold in data.get("recall_targets", []):
                for row in fold.get("targets", []):
                    if (
                        row.get("target") == target
                        and row.get("fraction") is not None
                    ):
                        fractions.append(float(row["fraction"]))
            if not fractions:
                continue
            lines.append(
                f"| {target:.0%} | {variant} | {len(fractions)} | "
                f"{_pct(float(np.mean(fractions)))} | "
                f"{_pct(float(np.median(fractions)))} | "
                f"{_pct(min(fractions))} | {_pct(max(fractions))} |"
            )
    lines.append("")
    lines.append(
        "Budget trong bảng này là tỷ lệ flow/ngày phải đưa vào hàng đợi để đạt "
        "recall mục tiêu. Nếu con số vượt quá khoảng 5–10%, ngân sách không khả thi "
        "nếu alert theo từng flow; cần gộp theo thực thể/thời gian. Các ngày có rất "
        "ít attack (Web1/Web2) có thể đẩy `Max` lên 100% nếu model không xếp hạng "
        "được vài chục flow tấn công, nên đọc thêm median thay vì chỉ trung bình."
    )

    lines.extend(
        [
            "",
            "## Ngưỡng calibrated / cố định",
            "",
            "| Chính sách | Variant | Recall | Precision | F1 | FPR | Alert/ngày |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name in ("fixed_0.5", "cal_fpr_0.01", "cal_fpr_0.05"):
        for variant, data in variants.items():
            policy = data["policies"].get(name)
            if not policy:
                continue
            pooled = policy["pooled"]
            lines.append(
                f"| {name} | {variant} | {_pct(pooled['recall'])} | "
                f"{_pct(pooled['precision'])} | {pooled['f1']:.4f} | "
                f"{_pct(pooled['fpr'])} | {_num(pooled['alerts_per_day'], 1)} |"
            )

    def family_map(variant: str, policy: str) -> dict[str, float]:
        data = variants.get(variant, {})
        rows = data.get("per_family", {}).get(policy, [])
        return {row["family"]: row["recall"] for row in rows}

    variant_names = [name for name in ("raw", "robust") if name in variants]
    if not variant_names:
        variant_names = list(variants)
    header_cells = []
    for variant in variant_names:
        header_cells.extend([f"{variant} @1%", f"{variant} @5%"])
    lines.extend(
        [
            "",
            "## Recall theo họ tấn công tại ngân sách 1% và 5% flow/ngày",
            "",
            "| Họ tấn công | " + " | ".join(header_cells) + " |",
            "|---|" + "|".join(["---:"] * len(header_cells)) + "|",
        ]
    )

    families: set[str] = set()
    for variant in variant_names:
        for policy in ("top_q_0.01", "top_q_0.05"):
            families |= set(family_map(variant, policy))
    for family in sorted(families):
        cells = []
        for variant in variant_names:
            cells.append(_pct(family_map(variant, "top_q_0.01").get(family)))
            cells.append(_pct(family_map(variant, "top_q_0.05").get(family)))
        lines.append(f"| {family} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Từng ngày tại ngân sách 1% flow",
            "",
            "| Fold | Ngày | Variant | Rows | Attacks | Alerts | TP | Recall | Precision |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for variant, data in variants.items():
        policy = data["policies"].get("top_q_0.01")
        if not policy:
            continue
        for row in policy["per_fold"]:
            lines.append(
                f"| {row['fold']} | {row.get('capture_date', '')} | {variant} | "
                f"{row['rows']:,} | {row['attacks']:,} | {row['alerts']:,} | "
                f"{row['tp']:,} | {_pct(row['recall'])} | {_pct(row['precision'])} |"
            )

    lines.extend(["", "## Diễn giải", ""])

    raw_k100 = variants.get("raw", {}).get("policies", {}).get("top_k_100", {}).get("pooled")
    robust_k100 = variants.get("robust", {}).get("policies", {}).get("top_k_100", {}).get("pooled")
    raw_q1 = variants.get("raw", {}).get("policies", {}).get("top_q_0.01", {}).get("pooled")
    robust_q1 = variants.get("robust", {}).get("policies", {}).get("top_q_0.01", {}).get("pooled")
    raw_q5 = variants.get("raw", {}).get("policies", {}).get("top_q_0.05", {}).get("pooled")
    robust_q5 = variants.get("robust", {}).get("policies", {}).get("top_q_0.05", {}).get("pooled")
    raw_q20 = variants.get("raw", {}).get("policies", {}).get("top_q_0.2", {}).get("pooled")
    robust_q20 = variants.get("robust", {}).get("policies", {}).get("top_q_0.2", {}).get("pooled")
    raw_cal1 = variants.get("raw", {}).get("policies", {}).get("cal_fpr_0.01", {}).get("pooled")
    robust_cal1 = variants.get("robust", {}).get("policies", {}).get("cal_fpr_0.01", {}).get("pooled")

    def median_budget(variant: str, target: float) -> float | None:
        values = []
        for fold in variants.get(variant, {}).get("recall_targets", []):
            for row in fold.get("targets", []):
                if row.get("target") == target and row.get("fraction") is not None:
                    values.append(float(row["fraction"]))
        return float(np.median(values)) if values else None

    if raw_k100 and robust_k100:
        raw_ceiling = recall_ceiling(
            variants["raw"]["policies"]["top_k_100"]["per_fold"]
        ) or 0.0
        robust_ceiling = recall_ceiling(
            variants["robust"]["policies"]["top_k_100"]["per_fold"]
        ) or 0.0
        lines.append(
            f"Ở ngân sách **100 alert/ngày** (alert theo flow), recall gộp của raw là "
            f"{_pct(raw_k100['recall'])} và robust là {_pct(robust_k100['recall'])}. "
            f"Recall ceiling tương ứng chỉ là {_pct(raw_ceiling)} và {_pct(robust_ceiling)}: "
            "ngay cả khi mọi alert đều là tấn công, ngân sách 100 flow/ngày cũng không thể "
            "phủ được các chiến dịch sinh ra hàng nghìn đến hàng chục nghìn flow. Đây là "
            "giới hạn của ngân sách, không chỉ của model."
        )
    if raw_q1 and robust_q1:
        raw_ceiling = recall_ceiling(
            variants["raw"]["policies"]["top_q_0.01"]["per_fold"]
        ) or 0.0
        robust_ceiling = recall_ceiling(
            variants["robust"]["policies"]["top_q_0.01"]["per_fold"]
        ) or 0.0
        lines.append("")
        lines.append(
            f"Ở ngân sách **1% flow/ngày** (trung bình "
            f"{_num(raw_q1['alerts_per_day'], 0)} alert/ngày), recall ceiling là "
            f"{_pct(raw_ceiling)} (raw) và {_pct(robust_ceiling)} (robust). Raw đạt recall "
            f"{_pct(raw_q1['recall'])} / precision {_pct(raw_q1['precision'])}, "
            f"robust đạt recall {_pct(robust_q1['recall'])} / precision "
            f"{_pct(robust_q1['precision'])}. Nếu recall gần ceiling, nút thắt là ngân sách; "
            "nếu thấp hơn nhiều, nút thắt là thứ hạng của model."
        )
    if raw_q5 and robust_q5:
        lines.append(
            f"Ở ngân sách **5% flow/ngày**, raw đạt recall {_pct(raw_q5['recall'])} "
            f"(FPR {_pct(raw_q5['fpr'])}), robust đạt recall {_pct(robust_q5['recall'])} "
            f"(FPR {_pct(robust_q5['fpr'])})."
        )

    lines.append(
        "Kết quả theo họ tấn công cho thấy ở cùng ngân sách flow, raw và robust gần như "
        "ngang nhau về recall gộp; khác biệt chủ yếu là thành phần họ tấn công. Robust "
        "nhỉnh hơn ở DDoS và một phần Web, trong khi raw tốt hơn rõ ở Botnet và không kém "
        "ở DoS/Infiltration. BruteForce rất kém ở cả hai. Vì vậy không nên chọn một biến "
        "thể duy nhất cho mọi mục tiêu."
    )

    if raw_cal1 and robust_cal1:
        lines.append("")
        lines.append(
            f"**Không nên so trực tiếp với ngưỡng calibrated**: ở mục tiêu FPR 1%, raw đạt "
            f"recall {_pct(raw_cal1['recall'])} với {_num(raw_cal1['alerts_per_day'], 0)} "
            f"alert/ngày và FPR thực {_pct(raw_cal1['fpr'])}; robust đạt recall "
            f"{_pct(robust_cal1['recall'])} nhưng cần "
            f"{_num(robust_cal1['alerts_per_day'], 0)} alert/ngày và FPR thực "
            f"{_pct(robust_cal1['fpr'])}. Robust 'thắng' vì tiêu nhiều alert hơn, không "
            "phải vì cùng ngân sách."
        )

    raw_50 = median_budget("raw", 0.5)
    robust_50 = median_budget("robust", 0.5)
    raw_80 = median_budget("raw", 0.8)
    robust_80 = median_budget("robust", 0.8)
    if raw_50 and robust_50 and raw_80 and robust_80:
        lines.append("")
        lines.append(
            f"Để đạt **50% recall**, budget trung vị cần khoảng {_pct(raw_50)} flow/ngày "
            f"(raw) và {_pct(robust_50)} (robust); để đạt **80% recall**, cần khoảng "
            f"{_pct(raw_80)} và {_pct(robust_80)}. Đây là những mức không khả thi nếu "
            "alert theo từng flow."
        )

    if raw_q20 and robust_q20:
        lines.append(
            f"Ở ngân sách **20% flow/ngày** (chỉ để xem trần), raw đạt recall "
            f"{_pct(raw_q20['recall'])} và robust {_pct(robust_q20['recall'])}; ngay cả "
            "khi đó vẫn còn cách xa recall đầy đủ."
        )

    lines.extend(
        [
            "",
            "**Khuyến nghị vận hành:** không dùng ngân sách 100 alert/ngày ở mức flow; "
            "ngay cả 5% flow/ngày (~10.000 alert/ngày) cũng chỉ đạt khoảng 9% recall. "
            "Trong triển khai thật, nên gộp cảnh báo theo `source IP` + cửa sổ thời gian "
            "(ví dụ 1–5 phút) rồi mới áp ngân sách top-k cho từng thực thể, hoặc dùng "
            "detector theo họ tấn công. Dataset sạch hiện tại không còn cột IP nên báo "
            "cáo này chỉ đo được mức flow; cần giữ IP trong pipeline thu thập để đánh giá "
            "ngân sách theo thực thể.",
            "",
            "**Hạn chế:** score Random Forest rời rạc nên top-k chịu ảnh hưởng của "
            "tie-break; cột ngưỡng-tại-k cho biết số alert thực tế nếu triển khai bằng "
            "ngưỡng. Test mỗi ngày tối đa 200.000 flow, không phải toàn bộ lưu lượng.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary_csv(payload: dict[str, object], path: Path) -> None:
    rows = []
    for variant, data in payload["variants"].items():
        for name, policy in data["policies"].items():
            pooled = policy["pooled"]
            macro = policy["macro"]
            rows.append(
                {
                    "variant": variant,
                    "policy": name,
                    "kind": policy["kind"],
                    "budget": policy["budget"],
                    "folds": pooled["folds"],
                    "rows": pooled["rows"],
                    "attacks": pooled["attacks"],
                    "benign": pooled["benign"],
                    "alerts": pooled["alerts"],
                    "alerts_per_day": pooled["alerts_per_day"],
                    "tp": pooled["tp"],
                    "fp": pooled["fp"],
                    "fn": pooled["fn"],
                    "tn": pooled["tn"],
                    "precision": pooled["precision"],
                    "recall": pooled["recall"],
                    "recall_ceiling": recall_ceiling(policy["per_fold"]),
                    "f1": pooled["f1"],
                    "fpr": pooled["fpr"],
                    "precision_macro": macro["precision"]["mean"],
                    "precision_macro_std": macro["precision"]["std"],
                    "recall_macro": macro["recall"]["mean"],
                    "recall_macro_std": macro["recall"]["std"],
                    "f1_macro": macro["f1"]["mean"],
                    "f1_macro_std": macro["f1"]["std"],
                    "alerts_at_threshold_per_day": pooled[
                        "alerts_at_threshold_per_day"
                    ],
                    "precision_at_threshold": pooled["precision_at_threshold"],
                    "recall_at_threshold": pooled["recall_at_threshold"],
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def print_summary(payload: dict[str, object]) -> None:
    for variant, data in payload["variants"].items():
        print(f"\nVariant: {variant}")
        for name in ("top_k_100", "top_k_1000", "top_q_0.01", "top_q_0.05", "cal_fpr_0.01"):
            policy = data["policies"].get(name)
            if not policy:
                continue
            pooled = policy["pooled"]
            print(
                f"  {name:<16} recall={pooled['recall']:.4f} "
                f"precision={pooled['precision']:.4f} f1={pooled['f1']:.4f} "
                f"fpr={pooled['fpr']:.4%} alerts/day={pooled['alerts_per_day']:.1f}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--score-dir",
        default=str(RESULT_DIR / "lodo_scores"),
        help="Thư mục gốc chứa các thư mục variant/fold_*.parquet.",
    )
    parser.add_argument(
        "--variants",
        nargs="*",
        default=list(DEFAULT_VARIANTS),
        help="Các variant cần đánh giá (mặc định: raw robust).",
    )
    parser.add_argument(
        "--metrics",
        default=None,
        help="JSON metrics của một variant; mặc định results/normalized_<variant>_metrics.json.",
    )
    parser.add_argument(
        "--k-values",
        type=int,
        nargs="*",
        default=list(DEFAULT_K),
        help="Ngân sách alert tuyệt đối mỗi ngày.",
    )
    parser.add_argument(
        "--quantiles",
        type=float,
        nargs="*",
        default=list(DEFAULT_Q),
        help="Ngân sách theo tỷ lệ flow mỗi ngày.",
    )
    parser.add_argument(
        "--calibrated-fprs",
        type=float,
        nargs="*",
        default=list(DEFAULT_CALIBRATED_FPRS),
        help="Các mức FPR calibrated cần so sánh.",
    )
    parser.add_argument("--output-stem", default="budget")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    if args.metrics and len(args.variants) > 1:
        raise ValueError("--metrics chỉ dùng được với một variant.")
    payload = build_payload(args)
    save_json(payload, RESULT_DIR / f"{args.output_stem}_metrics.json")
    write_summary_csv(payload, RESULT_DIR / f"{args.output_stem}_summary.csv")
    write_report(payload, RESULT_DIR / f"{args.output_stem}_report.md")
    print_summary(payload)
    print(f"\nBáo cáo: {(RESULT_DIR / f'{args.output_stem}_report.md').resolve()}")


if __name__ == "__main__":
    main()
