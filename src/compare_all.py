"""Consolidated comparison of the full 10-fold runs.

Uses precomputed pooled metrics so the table stays comparable even when only
rates (not confusion counts) were logged. Subset runs (4 folds) are kept in
``results/normalization_report.md`` and are not mixed in here.
"""

from __future__ import annotations

import json

try:
    from src.common import RESULT_DIR
except ModuleNotFoundError:
    from common import RESULT_DIR


def load(name: str) -> dict:
    return json.loads((RESULT_DIR / name).read_text(encoding="utf-8"))


def fmt(row: dict, key: str = "precision") -> str:
    value = row.get(key)
    return "—" if value is None else f"{value:.4f}"


def metric_line(name: str, policy: str, row: dict) -> str:
    return (
        f"| {name} | {policy} | {row['recall']:.4f} | {fmt(row)} | "
        f"{row['f1']:.4f} | {row['fpr']:.4%} |"
    )


def main() -> None:
    baseline = load("calibration_metrics.json")
    robust = load("normalized_robust_metrics.json")
    anomaly = load("anomaly_metrics.json")
    lodo = load("lodo_metrics.json")

    lines = [
        "# So sánh các run đầy đủ 10 fold",
        "",
        "Cùng giao thức leave-one-day-out: train 8 ngày, validation là ngày liền trước,",
        "test là ngày bị giữ. Random Forest baseline và bản chuẩn hoá robust dùng cùng",
        "500.000 flow train và 100 cây. Isolation Forest dùng cấu hình riêng.",
        "",
        "## Kết quả gộp",
        "",
        "| Mô hình | Ngưỡng | Recall | Precision | F1 | FPR thực tế |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for policy, key in (("cố định 0,5", "fixed_0_5"), ("calibrated 1%", "fpr_0.01"), ("calibrated 5%", "fpr_0.05")):
        lines.append(metric_line("Random Forest (baseline)", policy, baseline["pooled"][key]))
    for policy, key in (("cố định 0,5", "fixed_0_5"), ("calibrated 1%", "fpr_0.01"), ("calibrated 5%", "fpr_0.05")):
        lines.append(metric_line("RF + chuẩn hoá robust/ngày", policy, robust["pooled"][key]))
    for policy, key in (("mặc định sklearn", "default_0"), ("calibrated 1%", "fpr_0.01"), ("calibrated 5%", "fpr_0.05")):
        lines.append(metric_line("Isolation Forest", policy, anomaly["pooled"][key]))

    lines.extend(
        [
            "",
            "## Theo nhóm tại ngưỡng 1%",
            "",
            "| Mô hình | Nhóm | Recall | Precision | F1 | FPR |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for name, payload in (("Random Forest (baseline)", baseline), ("RF + chuẩn hoá robust/ngày", robust)):
        for group in ("family_seen", "family_unseen"):
            group_payload = payload["by_group"].get(group, {})
            row = group_payload.get("fpr_0.01")
            if row is None and "recall" in group_payload:
                # Robust results were reconstructed from the log, which only
                # printed the group metrics at the chosen 1% threshold.
                row = group_payload
            if row is None:
                continue
            lines.append(
                f"| {name} | {group} | {row['recall']:.4f} | {fmt(row)} | "
                f"{row['f1']:.4f} | {row['fpr']:.4%} |"
            )
    for group in ("family_seen", "family_unseen"):
        row = anomaly["by_group"].get(group, {}).get("fpr_0.01")
        if row is None:
            continue
        lines.append(
            f"| Isolation Forest | {group} | {row['recall']:.4f} | {fmt(row)} | "
            f"{row['f1']:.4f} | {row['fpr']:.4%} |"
        )

    lines.extend(
        [
            "",
            "## AUC từng fold",
            "",
            "AUC baseline lấy từ `lodo_metrics.json` (train 9 ngày, không loại ngày",
            "validation). AUC robust là run 8 ngày. Vì vậy cột baseline lạc quan hơn ở",
            "các fold mà ngày liền trước thuộc cùng họ tấn công.",
            "",
            "| Fold | Ngày test | Nhóm | RF baseline (9 ngày) | RF + robust (8 ngày) | Isolation Forest |",
            "|---:|---|---|---:|---:|---:|",
        ]
    )
    baseline_auc = {fold["capture_date"]: fold["roc_auc"] for fold in lodo["folds"]}
    anomaly_auc = {fold["capture_date"]: fold["auc"] for fold in anomaly["folds"]}
    for fold in robust["folds"]:
        date = fold["capture_date"]
        lines.append(
            f"| {fold['fold']} | {date} | {fold['group']} | "
            f"{baseline_auc[date]:.3f} | {fold['auc']:.3f} | {anomaly_auc[date]:.3f} |"
        )

    mean_baseline = sum(fold["roc_auc"] for fold in lodo["folds"]) / len(lodo["folds"])
    lines.extend(
        [
            "",
            "## Nhận xét",
            "",
            f"- AUC trung bình: baseline 9 ngày {mean_baseline:.3f}; robust 8 ngày "
            f"{robust['mean_auc']:.3f}. Trung bình gần như nhau nhưng phân bố hoàn toàn khác.",
            "- Chuẩn hoá robust sửa hẳn các ngày flood: DoS2 0,163 → 0,994; DDoS2 "
            "0,843 → 1,000; DDoS1 0,922 → 0,984; Web1 0,959 → 0,999.",
            "- Nhưng nó phá các ngày dựa vào biên độ tuyệt đối: Botnet 0,960 → 0,435; "
            "Bruteforce 0,922 → 0,405.",
            "- Ở mục tiêu FPR 5%, robust đạt recall 66,0% / F1 0,567 / FPR 16,5% "
            "so với 31,9% / 0,328 / 15,4% của baseline. Đây là cải thiện thật nhưng FPR "
            "vẫn quá cao cho vận hành.",
            "- Ngưỡng vẫn không chuyển được qua ngày: fold Infil1 có FPR 99,46% khi "
            "calibration mục tiêu 1%. Vì vậy chuẩn hoá đặc trưng **không thay thế** "
            "calibration trên mạng đích.",
            "- Kết luận: dùng chuẩn hoá như một detector song song có mục tiêu (flood), "
            "không phải biến đổi mặc định cho mọi ngày.",
            "",
        ]
    )

    output = RESULT_DIR / "comparison_all.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Đã ghi: {output.resolve()}")


if __name__ == "__main__":
    main()
