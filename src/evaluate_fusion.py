"""Evaluate score-level fusion of raw and robust detectors on saved LODO scores.

Both variants were trained with the same folds and the same test sampling, so
their per-flow scores can be aligned row by row without retraining.  The script
compares simple fusion rules (mean/max probability, rank fusion) against each
detector alone under the same alert budgets.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

try:
    from src.common import RESULT_DIR, ensure_output_dirs, save_json
    from src.evaluate_budget import (
        RECALL_TARGETS,
        family_summary,
        macro_stats,
        recall_ceiling,
        recall_target_rows,
        summarize_rows,
        topk_row,
    )
except ModuleNotFoundError:
    from common import RESULT_DIR, ensure_output_dirs, save_json
    from evaluate_budget import (
        RECALL_TARGETS,
        family_summary,
        macro_stats,
        recall_ceiling,
        recall_target_rows,
        summarize_rows,
        topk_row,
    )


METHODS = ("mean", "max", "rank_mean", "rank_max", "rank_min", "rank_min_tb")
K_VALUES = (100, 1_000, 5_000, 10_000)
Q_VALUES = (0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20)
FAMILY_Q = (0.01, 0.05)


def load_variant(score_root: Path, variant: str) -> list[pd.DataFrame]:
    directory = score_root / variant
    files = sorted(directory.glob("fold_*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy score cho '{variant}' trong {directory}."
        )
    folds: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_parquet(path)
        required = {"fold", "capture_date", "target", "score", "family"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{path} thiếu cột: {sorted(missing)}")
        frame["target"] = frame["target"].astype(int)
        frame["score"] = pd.to_numeric(frame["score"], errors="coerce").fillna(0.0)
        frame["family"] = frame["family"].fillna("Unknown").astype(str)
        folds.append(frame.reset_index(drop=True))
    return folds


def verify_alignment(raw: list[pd.DataFrame], robust: list[pd.DataFrame]) -> None:
    if len(raw) != len(robust):
        raise ValueError(f"Số fold khác nhau: raw={len(raw)}, robust={len(robust)}")
    for left, right in zip(raw, robust):
        if int(left["fold"].iloc[0]) != int(right["fold"].iloc[0]):
            raise ValueError("Fold không khớp giữa raw và robust.")
        if len(left) != len(right):
            raise ValueError(
                f"Fold {int(left['fold'].iloc[0])} có số dòng khác nhau: "
                f"{len(left)} vs {len(right)}"
            )
        for column in ("target", "label", "family", "source_file", "capture_date"):
            if column not in left or column not in right:
                raise ValueError(f"Thiếu cột {column} để kiểm tra alignment.")
            left_values = left[column].astype(str).to_numpy()
            right_values = right[column].astype(str).to_numpy()
            if not np.array_equal(left_values, right_values):
                raise ValueError(
                    f"Fold {int(left['fold'].iloc[0])} lệch cột {column}; "
                    "không thể fusion theo hàng."
                )


def _logit(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def fused_frame(
    raw: pd.DataFrame, robust: pd.DataFrame, method: str
) -> pd.DataFrame:
    base = raw[
        ["fold", "capture_date", "source_file", "target", "label", "family"]
    ].copy()
    left = raw["score"].to_numpy(dtype=float)
    right = robust["score"].to_numpy(dtype=float)
    count = len(left)

    if method == "mean":
        fused = (left + right) / 2.0
    elif method == "max":
        fused = np.maximum(left, right)
    elif method == "logit_mean":
        fused = _sigmoid((_logit(left) + _logit(right)) / 2.0)
    elif method == "rank_mean":
        fused = (
            rankdata(left, method="average") + rankdata(right, method="average")
        ) / (2.0 * count)
    elif method == "rank_max":
        fused = np.maximum(
            rankdata(left, method="average"), rankdata(right, method="average")
        ) / count
    elif method == "rank_min":
        fused = np.minimum(
            rankdata(left, method="average"), rankdata(right, method="average")
        ) / count
    elif method == "rank_min_tb":
        left_rank = rankdata(left, method="average") / count
        right_rank = rankdata(right, method="average") / count
        # The tiny secondary term only breaks exact ties in the primary rank;
        # it keeps the ranking operational when a threshold is used.
        fused = np.minimum(left_rank, right_rank) + 1e-6 * (
            (left_rank + right_rank) / 2.0
        )
    else:
        raise ValueError(f"Không hỗ trợ fusion method: {method}")

    base["score"] = fused.astype(np.float32)
    return base


def evaluate_variant(frames: list[pd.DataFrame]) -> dict[str, object]:
    result: dict[str, object] = {"top_k": {}, "top_q": {}}
    for k in K_VALUES:
        rows = [topk_row(frame, k) for frame in frames]
        result["top_k"][str(k)] = {
            "pooled": summarize_rows(rows),
            "macro": macro_stats(rows),
            "ceiling": recall_ceiling(rows),
            "per_fold": rows,
        }
    for q in Q_VALUES:
        rows = [
            topk_row(frame, max(1, math.ceil(q * len(frame))))
            for frame in frames
        ]
        result["top_q"][str(q)] = {
            "pooled": summarize_rows(rows),
            "macro": macro_stats(rows),
            "ceiling": recall_ceiling(rows),
            "per_fold": rows,
        }
    return result


def family_tables(frames: list[pd.DataFrame]) -> dict[str, list[dict[str, object]]]:
    tables: dict[str, list[dict[str, object]]] = {}
    for q in FAMILY_Q:
        budget = lambda frame, value=q: max(1, math.ceil(value * len(frame)))
        tables[str(q)] = family_summary(frames, budget)
    return tables


def build_payload(
    raw: list[pd.DataFrame], robust: list[pd.DataFrame], methods: list[str]
) -> dict[str, object]:
    variants: dict[str, list[pd.DataFrame]] = {"raw": raw, "robust": robust}
    for method in methods:
        variants[f"fusion_{method}"] = [
            fused_frame(left, right, method)
            for left, right in zip(raw, robust)
        ]

    payload: dict[str, object] = {
        "protocol": (
            "LODO 10 fold; raw và robust được train trên cùng fold và cùng test "
            "sampling. Fusion chỉ dùng score, không dùng nhãn test. Rank fusion "
            "dùng percentile trong từng ngày (transductive, không dùng label)."
        ),
        "methods": methods,
        "k_values": list(K_VALUES),
        "quantiles": list(Q_VALUES),
        "variants": {},
    }
    for name, frames in variants.items():
        payload["variants"][name] = {
            "folds": [
                {
                    "fold": int(frame["fold"].iloc[0]),
                    "capture_date": str(frame["capture_date"].iloc[0]),
                    "rows": int(len(frame)),
                    "attacks": int(frame["target"].sum()),
                }
                for frame in frames
            ],
            "evaluation": evaluate_variant(frames),
            "families": family_tables(frames),
            "recall_targets": [
                {
                    "fold": int(frame["fold"].iloc[0]),
                    "capture_date": str(frame["capture_date"].iloc[0]),
                    "attacks": int(frame["target"].sum()),
                    "targets": recall_target_rows(frame),
                }
                for frame in frames
            ],
        }
    return payload


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.2%}"


def _num(value: float | None, digits: int = 0) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def _policy(payload: dict[str, object], variant: str, kind: str, budget: float):
    return (
        payload["variants"][variant]["evaluation"][kind].get(str(budget), {})
    )


def write_report(payload: dict[str, object], path: Path) -> None:
    variants = payload["variants"]
    names = list(variants)
    lines = [
        "# Fusion raw + robust trên LODO",
        "",
        "## Thiết lập",
        "",
        f"- {payload['protocol']}",
        "- Fusion không train lại; chỉ kết hợp score đã lưu của 10 fold.",
        "- `rank_*` dùng percentile trong từng ngày, nên không bị lệch scale giữa "
        "raw và robust.",
        "- `rank_max` thiên về OR (một detector xếp hạng cao là đủ); `rank_min` "
        "thiên về AND (cả hai phải cùng xếp hạng cao).",
        "- `rank_min_tb` giống `rank_min` nhưng thêm tie-break nhỏ để triển khai "
        "bằng ngưỡng mà không phải alert toàn bộ nhóm score trùng.",
        "",
        "## Ngân sách 1% flow/ngày",
        "",
        "| Phương án | Recall | Precision | F1 | FPR | Recall ceiling |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in names:
        policy = _policy(payload, name, "top_q", 0.01)
        if not policy:
            continue
        pooled = policy["pooled"]
        lines.append(
            f"| {name} | {_pct(pooled['recall'])} | {_pct(pooled['precision'])} | "
            f"{pooled['f1']:.4f} | {_pct(pooled['fpr'])} | "
            f"{_pct(policy['ceiling'])} |"
        )

    lines.extend(
        [
            "",
            "## Ngân sách 5% flow/ngày",
            "",
            "| Phương án | Recall | Precision | F1 | FPR | Recall ceiling |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name in names:
        policy = _policy(payload, name, "top_q", 0.05)
        if not policy:
            continue
        pooled = policy["pooled"]
        lines.append(
            f"| {name} | {_pct(pooled['recall'])} | {_pct(pooled['precision'])} | "
            f"{pooled['f1']:.4f} | {_pct(pooled['fpr'])} | "
            f"{_pct(policy['ceiling'])} |"
        )

    lines.extend(
        [
            "",
            "## Nếu triển khai bằng ngưỡng tại vị trí k",
            "",
            "`Alert thực tế/ngày` là số alert khi dùng đúng score tại vị trí k làm "
            "ngưỡng. Score trùng (đặc biệt với Random Forest) làm số này lớn hơn "
            "ngân sách danh nghĩa; `rank_min_tb` được thêm tie-break để giảm hiện "
            "tượng này.",
            "",
            "| Ngân sách danh nghĩa | Phương án | Alert thực tế/ngày | Recall@ngưỡng | Precision@ngưỡng |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for q in (0.01, 0.05):
        for name in names:
            policy = _policy(payload, name, "top_q", q)
            if not policy:
                continue
            pooled = policy["pooled"]
            lines.append(
                f"| {q:.0%} flow | {name} | "
                f"{_num(pooled['alerts_at_threshold_per_day'], 1)} | "
                f"{_pct(pooled['recall_at_threshold'])} | "
                f"{_pct(pooled['precision_at_threshold'])} |"
            )

    target_names = [
        name
        for name in (
            "raw",
            "robust",
            "fusion_rank_min_tb",
            "fusion_mean",
            "fusion_max",
        )
        if name in names
    ]
    if target_names:
        lines.extend(
            [
                "",
                "## Ngân sách cần để đạt recall mục tiêu",
                "",
                "Phần trăm flow/ngày cần xếp hạng để đạt recall mục tiêu, tính riêng "
                "từng fold rồi lấy trung vị. Đây là ngân sách tối thiểu theo thứ hạng "
                "trên ngày test; không dùng nhãn để chọn ngưỡng.",
                "",
                "| Recall mục tiêu | Phương án | Trung vị % flow | Trung bình | Min | Max |",
                "|---:|---|---:|---:|---:|---:|",
            ]
        )
        for target in RECALL_TARGETS:
            for name in target_names:
                fractions = []
                for fold in variants[name].get("recall_targets", []):
                    for row in fold.get("targets", []):
                        if (
                            row.get("target") == target
                            and row.get("fraction") is not None
                        ):
                            fractions.append(float(row["fraction"]))
                if not fractions:
                    continue
                lines.append(
                    f"| {target:.0%} | {name} | "
                    f"{_pct(float(np.median(fractions)))} | "
                    f"{_pct(float(np.mean(fractions)))} | "
                    f"{_pct(min(fractions))} | {_pct(max(fractions))} |"
                )

    lines.extend(
        [
            "",
            "## Ngân sách tuyệt đối",
            "",
            "| Alert/ngày | Phương án | Recall | Precision | F1 |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for k in (100, 1_000):
        for name in names:
            policy = _policy(payload, name, "top_k", k)
            if not policy:
                continue
            pooled = policy["pooled"]
            lines.append(
                f"| {k:,} | {name} | {_pct(pooled['recall'])} | "
                f"{_pct(pooled['precision'])} | {pooled['f1']:.4f} |"
            )

    for q in FAMILY_Q:
        lines.extend(
            [
                "",
                f"## Recall theo họ tấn công @ {q:.0%} flow/ngày",
                "",
                "| Họ tấn công | " + " | ".join(names) + " |",
                "|---|" + "|".join(["---:"] * len(names)) + "|",
            ]
        )
        families: set[str] = set()
        for name in names:
            families |= {
                row["family"] for row in variants[name]["families"].get(str(q), [])
            }
        for family in sorted(families):
            cells = []
            for name in names:
                rows = variants[name]["families"].get(str(q), [])
                value = next(
                    (row["recall"] for row in rows if row["family"] == family), None
                )
                cells.append(_pct(value))
            lines.append(f"| {family} | " + " | ".join(cells) + " |")

    lines.extend(["", "## Diễn giải", ""])

    def pooled(name: str, q: float) -> dict[str, object]:
        policy = _policy(payload, name, "top_q", q)
        return policy.get("pooled", {}) if policy else {}

    best_1 = max(names, key=lambda name: pooled(name, 0.01).get("recall", -1.0))
    best_5 = max(names, key=lambda name: pooled(name, 0.05).get("recall", -1.0))
    lines.append(
        f"Ở ngân sách exact top-k 1% flow/ngày, phương án có recall gộp cao nhất "
        f"là **{best_1}** với {_pct(pooled(best_1, 0.01).get('recall'))}; ở 5% "
        f"flow/ngày là **{best_5}** với "
        f"{_pct(pooled(best_5, 0.05).get('recall'))}."
    )

    if "fusion_rank_min_tb" in names:
        tb_1 = pooled("fusion_rank_min_tb", 0.01)
        tb_5 = pooled("fusion_rank_min_tb", 0.05)
        lines.extend(
            [
                "",
                "Nếu triển khai bằng ngưỡng thay vì top-k chính xác:",
                "",
                f"- `rank_min_tb` @1%: "
                f"{_num(tb_1.get('alerts_at_threshold_per_day'), 1)} alert/ngày, "
                f"recall {_pct(tb_1.get('recall_at_threshold'))}, precision "
                f"{_pct(tb_1.get('precision_at_threshold'))}.",
                f"- `rank_min_tb` @5%: "
                f"{_num(tb_5.get('alerts_at_threshold_per_day'), 1)} alert/ngày, "
                f"recall {_pct(tb_5.get('recall_at_threshold'))}, precision "
                f"{_pct(tb_5.get('precision_at_threshold'))}.",
            ]
        )
    if "robust" in names:
        robust_1 = pooled("robust", 0.01)
        lines.append(
            f"- `robust` @1%: "
            f"{_num(robust_1.get('alerts_at_threshold_per_day'), 1)} alert/ngày, "
            f"recall {_pct(robust_1.get('recall_at_threshold'))}, precision "
            f"{_pct(robust_1.get('precision_at_threshold'))}. Alert volume cao hơn "
            f"ngân sách danh nghĩa, nên không so trực tiếp với top-k 1%."
        )
    if "fusion_mean" in names:
        mean_10 = pooled("fusion_mean", 0.1)
        mean_20 = pooled("fusion_mean", 0.2)
        lines.extend(
            [
                f"- `fusion_mean` @10% top-q: recall "
                f"{_pct(mean_10.get('recall'))}, precision "
                f"{_pct(mean_10.get('precision'))}; nếu dùng ngưỡng tại k, "
                f"{_num(mean_10.get('alerts_at_threshold_per_day'), 1)} alert/ngày, "
                f"recall {_pct(mean_10.get('recall_at_threshold'))}.",
                f"- `fusion_mean` @20% top-q: recall "
                f"{_pct(mean_20.get('recall'))}, precision "
                f"{_pct(mean_20.get('precision'))}; nếu dùng ngưỡng tại k, "
                f"{_num(mean_20.get('alerts_at_threshold_per_day'), 1)} alert/ngày, "
                f"recall {_pct(mean_20.get('recall_at_threshold'))}.",
            ]
        )
    if "fusion_max" in names:
        max_5 = pooled("fusion_max", 0.05)
        lines.append(
            f"- `fusion_max` @5%: "
            f"{_num(max_5.get('alerts_at_threshold_per_day'), 1)} alert/ngày, "
            f"recall {_pct(max_5.get('recall_at_threshold'))}, precision "
            f"{_pct(max_5.get('precision_at_threshold'))}. Nếu mục tiêu là recall "
            f"cao, `fusion_mean` ở 10–20% flow tốt hơn; `fusion_max` không phải "
            f"lựa chọn high-recall tốt nhất."
        )

    lines.extend(
        [
            "",
            "Fusion cải thiện rõ nhất ở Botnet và DoS, giữ DDoS gần mức robust, "
            "nhưng có thể giảm Web so với raw. BruteForce vẫn gần 0 trong LODO vì "
            "họ này chỉ có một ngày và fold test là zero-shot; fusion score không "
            "giải quyết được thiếu dữ liệu huấn luyện.",
            "",
            "**Khuyến nghị tạm thời:** dùng raw + robust song song và fuse bằng "
            "`rank_min_tb` cho hàng đợi đúng ngân sách. Nếu có thêm năng lực alert, "
            "thêm stream `fusion_mean` ở 10–20% flow để tăng recall; `fusion_max` "
            "không vượt `fusion_mean` ở mục tiêu recall cao. Không nên chọn một "
            "normalizer đơn lẻ làm mặc định.",
            "",
            "**Giới hạn:** đây là fusion ở mức score, không thay đổi feature hay "
            "ngưỡng calibrated. Rank fusion cần đủ flow của ngày để tính percentile "
            "(transductive), giống robust normalization. Nếu triển khai streaming, "
            "cần cửa sổ trượt thay vì percentile toàn ngày. Feature-level `union` "
            "đã dừng sớm: 4 fold có AUC Bruteforce 0,467, DoS2 0,994, DDoS2 0,862, "
            "Botnet 0,881; full run cho Bruteforce AUC 0,092 và DoS1 FPR calibrated "
            "21,88% ở 2 fold đầu, nên không được chọn.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(payload: dict[str, object], path: Path) -> None:
    rows = []
    for name, data in payload["variants"].items():
        for kind in ("top_k", "top_q"):
            for budget, policy in data["evaluation"][kind].items():
                pooled = policy["pooled"]
                rows.append(
                    {
                        "variant": name,
                        "kind": kind,
                        "budget": float(budget),
                        "recall": pooled["recall"],
                        "precision": pooled["precision"],
                        "f1": pooled["f1"],
                        "fpr": pooled["fpr"],
                        "recall_ceiling": policy["ceiling"],
                        "alerts_per_day": pooled["alerts_per_day"],
                        "alerts_at_threshold_per_day": pooled[
                            "alerts_at_threshold_per_day"
                        ],
                        "recall_at_threshold": pooled["recall_at_threshold"],
                        "precision_at_threshold": pooled["precision_at_threshold"],
                        "tp": pooled["tp"],
                        "fp": pooled["fp"],
                        "fn": pooled["fn"],
                        "tn": pooled["tn"],
                    }
                )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--score-dir",
        default=str(RESULT_DIR / "lodo_scores"),
        help="Thư mục gốc chứa raw/ và robust/.",
    )
    parser.add_argument(
        "--methods",
        nargs="*",
        default=list(METHODS),
        help="Các fusion method cần đánh giá.",
    )
    parser.add_argument("--output-stem", default="fusion")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dirs()
    score_root = Path(args.score_dir)
    raw = load_variant(score_root, "raw")
    robust = load_variant(score_root, "robust")
    verify_alignment(raw, robust)
    payload = build_payload(raw, robust, list(args.methods))
    save_json(payload, RESULT_DIR / f"{args.output_stem}_metrics.json")
    write_csv(payload, RESULT_DIR / f"{args.output_stem}_summary.csv")
    write_report(payload, RESULT_DIR / f"{args.output_stem}_report.md")

    print("Fusion methods:", ", ".join(args.methods))
    for name, data in payload["variants"].items():
        pooled = data["evaluation"]["top_q"]["0.01"]["pooled"]
        print(
            f"  {name:<20} recall@1%={pooled['recall']:.4f} "
            f"precision={pooled['precision']:.4f} "
            f"f1={pooled['f1']:.4f} fpr={pooled['fpr']:.4%}"
        )
    print(f"\nBáo cáo: {(RESULT_DIR / f'{args.output_stem}_report.md').resolve()}")


if __name__ == "__main__":
    main()
