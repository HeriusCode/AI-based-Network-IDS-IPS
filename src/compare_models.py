"""Compare the supervised Random Forest and the unsupervised Isolation Forest.

Both models are evaluated with the same leave-one-day-out protocol and the same
validation-day calibration. The script only reads the two result JSON files, so
it is cheap to re-run after either experiment changes.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from src.common import RESULT_DIR
except ModuleNotFoundError:
    from common import RESULT_DIR


def aggregate(folds: list[dict], key: str) -> dict[str, float]:
    tp = sum(fold[key]["tp"] for fold in folds)
    fp = sum(fold[key]["fp"] for fold in folds)
    fn = sum(fold[key]["fn"] for fold in folds)
    tn = sum(fold[key]["tn"] for fold in folds)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "alerts": tp + fp,
    }


def select(folds: list[dict], group: str | None = None, skip_fold: int | None = None) -> list[dict]:
    chosen = folds
    if group is not None:
        chosen = [fold for fold in chosen if fold["group"] == group]
    if skip_fold is not None:
        chosen = [fold for fold in chosen if fold["fold"] != skip_fold]
    return chosen


ROWS = (
    ("Random Forest", "fixed 0,5", "at_fixed_0_5"),
    ("Random Forest", "calibrated FPR 1%", "fpr_0.01"),
    ("Random Forest", "calibrated FPR 5%", "fpr_0.05"),
    ("Isolation Forest", "mặc định sklearn", "at_default"),
    ("Isolation Forest", "calibrated FPR 1%", "fpr_0.01"),
    ("Isolation Forest", "calibrated FPR 5%", "fpr_0.05"),
)


def render(folds_by_model: dict[str, list[dict]]) -> str:
    lines = [
        "# So sánh Random Forest và Isolation Forest",
        "",
        "Cùng giao thức leave-one-day-out: train 8 ngày, validation là ngày liền trước,",
        "test là ngày bị giữ. Random Forest train trên benign + attack; Isolation Forest",
        "chỉ train trên benign.",
        "",
        "## Toàn bộ 10 fold",
        "",
        "| Mô hình | Ngưỡng | Recall | Precision | F1 | FPR thực tế |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model, label, key in ROWS:
        folds = folds_by_model[model]
        if not folds or key not in folds[0]:
            continue
        row = aggregate(folds, key)
        lines.append(
            f"| {model} | {label} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )

    lines.extend(
        [
            "",
            "## Tại ngưỡng calibrated FPR 1%, theo nhóm",
            "",
            "| Mô hình | Nhóm | Số fold | Recall | Precision | F1 | FPR |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for model in ("Random Forest", "Isolation Forest"):
        folds = folds_by_model[model]
        for group in ("family_seen", "family_unseen"):
            subset = select(folds, group=group)
            if not subset:
                continue
            row = aggregate(subset, "fpr_0.01")
            lines.append(
                f"| {model} | {group} | {len(subset)} | {row['recall']:.4f} | "
                f"{row['precision']:.4f} | {row['f1']:.4f} | {row['fpr']:.4%} |"
            )

    lines.extend(
        [
            "",
            "## Bỏ fold DDoS2 (AUC < 0,5, xếp hạng bị đảo)",
            "",
            "| Mô hình | Ngưỡng | Recall | Precision | F1 | FPR thực tế |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for model, label, key in ROWS:
        folds = folds_by_model[model]
        subset = select(folds, skip_fold=5)
        if not subset or key not in subset[0]:
            continue
        row = aggregate(subset, key)
        lines.append(
            f"| {model} | {label} | {row['recall']:.4f} | {row['precision']:.4f} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )

    lines.extend(["", "## Nhận xét tự động", ""])
    rf = folds_by_model["Random Forest"]
    iso = folds_by_model["Isolation Forest"]
    if rf and iso:
        rf_fixed = aggregate(rf, "at_fixed_0_5")
        rf_cal = aggregate(rf, "fpr_0.01")
        iso_fixed = aggregate(iso, "at_default")
        iso_cal = aggregate(iso, "fpr_0.01")
        lines.append(
            f"- Ở ngưỡng calibrated 1%: RF recall {rf_cal['recall']:.2%}, F1 "
            f"{rf_cal['f1']:.4f}; Isolation Forest recall {iso_cal['recall']:.2%}, F1 "
            f"{iso_cal['f1']:.4f}."
        )
        lines.append(
            f"- FPR thực tế: RF {rf_cal['fpr']:.2%}, Isolation Forest {iso_cal['fpr']:.2%} "
            "(mục tiêu 1%). Chênh lệch phản ánh drift giữa ngày validation và ngày test."
        )
        if iso_cal["f1"] > rf_cal["f1"]:
            lines.append(
                "- Isolation Forest tốt hơn ở ngưỡng calibrated, phù hợp để bổ sung như "
                "lớp cảnh báo cho họ tấn công mới."
            )
        else:
            lines.append(
                "- Isolation Forest chưa vượt Random Forest ở ngưỡng calibrated; cần cải "
                "thiện đặc trưng hoặc chuẩn hoá điểm theo ngày trước khi dùng làm lớp chính."
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    calibration_path = RESULT_DIR / "calibration_metrics.json"
    anomaly_path = RESULT_DIR / "anomaly_metrics.json"
    payloads: dict[str, dict] = {
        "Random Forest": json.loads(calibration_path.read_text(encoding="utf-8")),
        "Isolation Forest": json.loads(anomaly_path.read_text(encoding="utf-8")),
    }
    folds_by_model = {
        "Random Forest": payloads["Random Forest"]["folds"],
        "Isolation Forest": payloads["Isolation Forest"]["folds"],
    }
    output = RESULT_DIR / "comparison.md"
    output.write_text(render(folds_by_model), encoding="utf-8")
    print(f"Đã ghi: {output.resolve()}")


if __name__ == "__main__":
    main()
