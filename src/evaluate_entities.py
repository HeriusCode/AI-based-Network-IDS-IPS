"""Evaluate source-IP/time-window alert aggregation from exported flow scores.

The flow-level queue is the wrong unit for flood campaigns: one attacker can
produce thousands of flows.  This script groups flows by ``source_ip`` inside a
fixed time window, aggregates their scores (``max``, ``mean`` or ``sum``), and
then applies the alert budget to entities instead of flows.  ``sum`` is the
useful default for floods because it rewards entities with many suspicious
flows; ``max`` is better when one abnormal flow is enough.  Budgets can be a
fraction of entities, a fixed entity count, or a fixed number of reviewed flows.

It needs score files that still contain ``source_ip`` and ``timestamp``.  Those
columns are optional in the training pipeline because the packaged
CIC-IDS2018 Parquet files do not contain them.  When the original CSV/Parquet
with ``Source IP`` and ``Timestamp`` is available, rerun preprocessing and
``train_normalized.py --save-scores``; this script will then consume the
metadata automatically.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

try:
    from src.common import RESULT_DIR, save_json
except ModuleNotFoundError:  # Allows: python src/evaluate_entities.py
    from common import RESULT_DIR, save_json


REQUIRED_COLUMNS = {
    "fold",
    "capture_date",
    "target",
    "score",
    "family",
    "source_ip",
    "timestamp",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scores",
        type=Path,
        default=None,
        help="Thư mục chứa fold_*.parquet. Mặc định results/lodo_scores/<variant>.",
    )
    parser.add_argument(
        "--variant",
        default="raw",
        help="Tên biến thể dùng khi không truyền --scores (mặc định raw).",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=5,
        help="Độ dài cửa sổ thời gian để gộp flow thành entity (mặc định 5 phút).",
    )
    parser.add_argument(
        "--budget-q",
        type=float,
        default=0.05,
        help="Tỷ lệ entity nhận alert mỗi ngày (mặc định 5%%).",
    )
    parser.add_argument(
        "--budget-k",
        type=int,
        default=0,
        help="Số entity alert cố định mỗi ngày; nếu > 0 sẽ thay thế --budget-q.",
    )
    parser.add_argument(
        "--budget-flows",
        type=int,
        default=0,
        help=(
            "Chọn entity cho đến khi đạt N flow review mỗi ngày; nếu > 0 sẽ thay "
            "thế --budget-q/--budget-k. Entity cuối có thể làm vượt nhẹ ngân sách."
        ),
    )
    parser.add_argument(
        "--entity-score",
        choices=["max", "mean", "sum", "sum_topk"],
        default="max",
        help=(
            "Cách gộp score các flow trong cùng entity (mặc định max). "
            "sum phù hợp với chiến dịch flood có nhiều flow/entity; max phù hợp "
            "khi chỉ cần một flow bất thường là đủ; sum_topk cộng K score cao "
            "nhất để tránh entity benign lưu lượng lớn."
        ),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Số flow score cao nhất dùng cho sum_topk (mặc định 10).",
    )
    parser.add_argument(
        "--review-per-entity",
        type=int,
        default=0,
        help=(
            "Giới hạn số flow review cho mỗi entity alert (mặc định 0 = xem "
            "toàn bộ entity). Dùng để mô phỏng queue triage thực tế."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULT_DIR / "entity_evaluation.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=RESULT_DIR / "entity_evaluation.md",
    )
    return parser.parse_args()


def load_score_frames(directory: Path) -> list[pd.DataFrame]:
    files = sorted(directory.glob("fold_*.parquet"))
    if not files:
        raise FileNotFoundError(f"Không tìm thấy score fold_*.parquet trong {directory}.")

    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_parquet(path)
        missing = REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            raise ValueError(
                f"{path.name} thiếu cột: {sorted(missing)}. "
                "Entity evaluation cần score được xuất từ dữ liệu gốc còn "
                "'Source IP' và 'Timestamp'. Hãy chạy preprocess.py trên CSV gốc, "
                "rồi train_normalized.py --save-scores. Parquet sạch hiện tại đã "
                "mất hai cột này nên không thể đánh giá entity."
            )
        frame["target"] = frame["target"].astype(int)
        frame["score"] = pd.to_numeric(frame["score"], errors="coerce").fillna(0.0)
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"], errors="coerce", utc=True, dayfirst=True, format="mixed"
        )
        if frame["timestamp"].isna().any():
            bad = int(frame["timestamp"].isna().sum())
            raise ValueError(f"{path.name} có {bad} timestamp không đọc được.")
        frame["source_ip"] = frame["source_ip"].astype("string").fillna("unknown")
        frames.append(frame)
    return frames


def entity_table(
    frame: pd.DataFrame,
    window_minutes: int,
    entity_score: str,
    top_k: int = 10,
) -> pd.DataFrame:
    window = f"{window_minutes}min"
    entity = (
        frame["source_ip"].astype(str)
        + "|"
        + frame["timestamp"].dt.floor(window).astype(str)
    )
    work = frame.assign(entity=entity)
    if entity_score == "sum_topk":
        # Sum only the K highest flow scores per entity.  Raw ``sum`` gives
        # high-volume benign servers an unfair advantage; top-k keeps the
        # flood signal without counting thousands of ordinary flows.
        k = max(int(top_k), 1)
        score = (
            work.groupby("entity", sort=False)["score"]
            .nlargest(k)
            .groupby(level=0)
            .sum()
        )
        table = (
            work.groupby("entity", sort=False)
            .agg(
                flows=("target", "size"),
                attacks=("target", "sum"),
                source_ip=("source_ip", "first"),
                window_start=("timestamp", "min"),
                window_end=("timestamp", "max"),
            )
            .reset_index()
        )
        table["score"] = table["entity"].map(score)
    else:
        score_agg = {"max": "max", "mean": "mean", "sum": "sum"}[entity_score]
        table = (
            work.groupby("entity", sort=False)
            .agg(
                score=("score", score_agg),
                flows=("target", "size"),
                attacks=("target", "sum"),
                source_ip=("source_ip", "first"),
                window_start=("timestamp", "min"),
                window_end=("timestamp", "max"),
            )
            .reset_index()
        )
    table["score"] = pd.to_numeric(table["score"], errors="coerce").fillna(0.0)
    table["attacks"] = table["attacks"].astype(int)
    table["flows"] = table["flows"].astype(int)
    table["is_attack"] = (table["attacks"] > 0).astype(int)
    return table


def metric_block(tp: int, fp: int, fn: int, tn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fp / (fp + tn)) if fp + tn else 0.0,
    }


def evaluate_day(
    frame: pd.DataFrame,
    budget_k: int | None,
    budget_q: float,
    window_minutes: int,
    entity_score: str,
    budget_flows: int | None = None,
    top_k: int = 10,
    review_per_entity: int = 0,
) -> dict[str, object]:
    table = entity_table(frame, window_minutes, entity_score, top_k=top_k)
    n_flows = int(len(frame))
    n_entities = int(len(table))
    attacks = int(frame["target"].sum())
    benign = n_flows - attacks

    table = table.sort_values(
        ["score", "entity"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    cap = max(int(review_per_entity), 0)
    table["review_cost"] = (
        table["flows"].clip(upper=cap) if cap > 0 else table["flows"]
    )
    if budget_flows is not None:
        # Pick entities until the review budget is reached.  With
        # ``--review-per-entity`` the cost is capped, so a single huge entity
        # cannot blow up the queue.
        cumulative_flows = table["review_cost"].cumsum()
        budget = int(cumulative_flows.searchsorted(budget_flows, side="left") + 1)
        budget = min(max(budget, 1), n_entities)
    elif budget_k is not None:
        budget = min(max(int(budget_k), 1), n_entities)
    else:
        budget = min(max(math.ceil(budget_q * n_entities), 1), n_entities)

    selected = table.head(budget)
    selected_entities = set(selected["entity"])

    # Build the exact reviewed-flow set.  Without a cap this is every flow in
    # the selected entities; with a cap it is the top-scoring flows per entity,
    # which is what a triage queue can realistically show.
    entity_of_flow = (
        frame["source_ip"].astype(str)
        + "|"
        + frame["timestamp"].dt.floor(f"{window_minutes}min").astype(str)
    )
    work = frame.assign(_entity=entity_of_flow)
    work["_selected"] = work["_entity"].isin(selected_entities)
    if cap > 0:
        ranked = work.loc[work["_selected"]].sort_values(
            ["score"], ascending=False, kind="mergesort"
        )
        reviewed_index = ranked.groupby("_entity", sort=False).head(cap).index
        work["_reviewed"] = work.index.isin(reviewed_index)
    else:
        work["_reviewed"] = work["_selected"]

    reviewed_flows = int(work["_reviewed"].sum())
    tp = int(work.loc[work["_reviewed"], "target"].sum())
    fp = reviewed_flows - tp
    fn = attacks - tp
    tn = benign - fp
    flow_metrics = metric_block(tp, fp, fn, tn)

    entity_tp = int((selected["is_attack"] == 1).sum())
    entity_fp = budget - entity_tp
    attack_entities = int(table["is_attack"].sum())
    entity_fn = attack_entities - entity_tp
    entity_tn = n_entities - attack_entities - entity_fp
    entity_metrics = metric_block(entity_tp, entity_fp, entity_fn, entity_tn)

    flow_order = frame.sort_values(
        ["score"], ascending=False, kind="mergesort"
    ).reset_index(drop=True)
    same_alert_flows = min(budget, n_flows)
    same_alert = flow_order.head(same_alert_flows)
    same_alert_tp = int(same_alert["target"].sum())
    same_alert_recall = same_alert_tp / attacks if attacks else 0.0

    same_review_flows = min(reviewed_flows, n_flows)
    same_review = flow_order.head(same_review_flows)
    same_review_tp = int(same_review["target"].sum())
    same_review_recall = same_review_tp / attacks if attacks else 0.0

    family_rows: list[dict[str, object]] = []
    if "family" in frame:
        attack_flows = work[work["target"] == 1]
        for family, group in attack_flows.groupby("family", sort=True):
            detected = int(group["_reviewed"].sum())
            total = int(len(group))
            family_rows.append(
                {
                    "family": str(family),
                    "attacks": total,
                    "detected": detected,
                    "recall": detected / total if total else 0.0,
                }
            )

    return {
        "fold": int(frame["fold"].iloc[0]),
        "capture_date": str(frame["capture_date"].iloc[0]),
        "rows": n_flows,
        "unknown_ip_flows": int((frame["source_ip"].astype(str) == "unknown").sum()),
        "attacks": attacks,
        "benign": benign,
        "entities": n_entities,
        "attack_entities": attack_entities,
        "entity_alerts": budget,
        "reviewed_flows": reviewed_flows,
        **{f"flow_{key}": value for key, value in flow_metrics.items()},
        **{f"entity_{key}": value for key, value in entity_metrics.items()},
        "flow_same_alert_count": same_alert_flows,
        "flow_same_alert_tp": same_alert_tp,
        "flow_same_alert_recall": float(same_alert_recall),
        "flow_same_review_count": same_review_flows,
        "flow_same_review_tp": same_review_tp,
        "flow_same_review_recall": float(same_review_recall),
        "by_family": family_rows,
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {}

    def total(prefix: str, key: str) -> int:
        return sum(int(row[f"{prefix}_{key}"]) for row in rows)

    flow = metric_block(
        total("flow", "tp"),
        total("flow", "fp"),
        total("flow", "fn"),
        total("flow", "tn"),
    )
    entity = metric_block(
        total("entity", "tp"),
        total("entity", "fp"),
        total("entity", "fn"),
        total("entity", "tn"),
    )
    same_alert_tp = sum(int(row["flow_same_alert_tp"]) for row in rows)
    same_review_tp = sum(int(row["flow_same_review_tp"]) for row in rows)
    attacks = sum(int(row["attacks"]) for row in rows)
    return {
        "days": len(rows),
        "rows": sum(int(row["rows"]) for row in rows),
        "unknown_ip_flows": sum(int(row["unknown_ip_flows"]) for row in rows),
        "attacks": attacks,
        "entities": sum(int(row["entities"]) for row in rows),
        "entity_alerts": sum(int(row["entity_alerts"]) for row in rows),
        "reviewed_flows": sum(int(row["reviewed_flows"]) for row in rows),
        "flow": flow,
        "entity": entity,
        "flow_baseline_same_alerts": {
            "alerts": sum(int(row["flow_same_alert_count"]) for row in rows),
            "tp": same_alert_tp,
            "recall": same_alert_tp / attacks if attacks else 0.0,
        },
        "flow_baseline_same_review": {
            "flows": sum(int(row["flow_same_review_count"]) for row in rows),
            "tp": same_review_tp,
            "recall": same_review_tp / attacks if attacks else 0.0,
        },
    }


def write_report(payload: dict[str, object], path: Path) -> None:
    config = payload["config"]
    pooled = payload["pooled"]
    lines = [
        "# Đánh giá cảnh báo theo entity (source IP + cửa sổ thời gian)",
        "",
        f"- Thư mục score: `{config['scores']}`",
        f"- Cửa sổ: {config['window_minutes']} phút; gộp score: `{config['entity_score']}`",
        f"- Ngân sách: {config['budget_description']}",
    ]
    if config.get("review_per_entity", 0) > 0:
        lines.append(
            "- Mỗi alert entity chỉ review các flow score cao nhất trong entity; "
            "recall flow phản ánh phần thực sự được review."
        )
    else:
        lines.append("- Mỗi alert entity = xem toàn bộ flow của source IP trong cửa sổ đó.")
    if config["entity_score"] == "sum_topk":
        lines.append(f"- `sum_topk` dùng {config['top_k']} flow score cao nhất mỗi entity.")
    if pooled["unknown_ip_flows"]:
        lines.append(
            f"- **Cảnh báo:** {pooled['unknown_ip_flows']:,} flow không có source IP; "
            "các flow này bị gộp vào entity `unknown`, nên kết quả entity có thể bị lệch."
        )
    lines.extend(
        [
            "",
            "## Kết quả gộp",
            "",
            "| Đơn vị | Alert | Flow/alert | Recall | Precision | F1 |",
            "|---|---:|---:|---:|---:|---:|",
            f"| Entity | {pooled['entity_alerts']:,} | "
            f"{pooled['reviewed_flows'] / max(pooled['entity_alerts'], 1):.2f} | "
            f"{pooled['flow']['recall']:.4f} | {pooled['flow']['precision']:.4f} | "
            f"{pooled['flow']['f1']:.4f} |",
            f"| Flow cùng số alert | {pooled['flow_baseline_same_alerts']['alerts']:,} | 1.00 | "
            f"{pooled['flow_baseline_same_alerts']['recall']:.4f} | - | - |",
            f"| Flow cùng số flow review | {pooled['flow_baseline_same_review']['flows']:,} | 1.00 | "
            f"{pooled['flow_baseline_same_review']['recall']:.4f} | - | - |",
            "",
            "## Từng ngày",
            "",
            "| Ngày | Flow | Entity | Attack flow | Entity alert | Flow review | "
            "Recall flow | Precision flow | Recall entity | Precision entity |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["days"]:
        lines.append(
            f"| {row['capture_date']} | {row['rows']:,} | {row['entities']:,} | "
            f"{row['attacks']:,} | {row['entity_alerts']:,} | {row['reviewed_flows']:,} | "
            f"{row['flow_recall']:.4f} | {row['flow_precision']:.4f} | "
            f"{row['entity_recall']:.4f} | {row['entity_precision']:.4f} |"
        )

    lines.extend(["", "## Theo họ tấn công (recall flow)", ""])
    family_totals: dict[str, dict[str, int]] = {}
    for row in payload["days"]:
        for family_row in row["by_family"]:
            entry = family_totals.setdefault(
                family_row["family"], {"attacks": 0, "detected": 0}
            )
            entry["attacks"] += int(family_row["attacks"])
            entry["detected"] += int(family_row["detected"])
    if family_totals:
        lines.extend(["| Họ | Attack flow | Phát hiện | Recall |", "|---|---:|---:|---:|"])
        for family, entry in sorted(family_totals.items()):
            recall = entry["detected"] / entry["attacks"] if entry["attacks"] else 0.0
            lines.append(
                f"| {family} | {entry['attacks']:,} | {entry['detected']:,} | {recall:.4f} |"
            )
    else:
        lines.append("Không có cột `family` trong score.")

    lines.extend(
        [
            "",
            "## Cách đọc",
            "",
            "- `Recall flow` là tỷ lệ flow tấn công nằm trong các entity được chọn.",
            "- `Entity alert` là số cửa sổ/source IP cần điều tra, không phải số flow.",
            "- `Flow same alert` là baseline xếp hạng flow với đúng số alert entity; "
            "đây là so sánh công bằng về số alert nhưng bỏ qua việc một entity chứa nhiều flow.",
            "- `Flow same review` là baseline xếp hạng flow với đúng số flow bị review; "
            "so sánh này kiểm tra liệu việc gộp entity có chọn flow tốt hơn không.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.window_minutes <= 0:
        raise ValueError("--window-minutes phải > 0.")
    if args.budget_k < 0:
        raise ValueError("--budget-k không được âm.")
    if args.budget_flows < 0:
        raise ValueError("--budget-flows không được âm.")
    if not 0 < args.budget_q <= 1:
        raise ValueError("--budget-q phải nằm trong (0, 1].")
    if args.top_k <= 0:
        raise ValueError("--top-k phải > 0.")
    if args.review_per_entity < 0:
        raise ValueError("--review-per-entity không được âm.")

    scores = args.scores or (RESULT_DIR / "lodo_scores" / args.variant)
    frames = load_score_frames(scores)

    budget_k = args.budget_k if args.budget_k > 0 else None
    budget_flows = args.budget_flows if args.budget_flows > 0 else None
    review_per_entity = max(int(args.review_per_entity), 0)
    rows = [
        evaluate_day(
            frame,
            budget_k=budget_k,
            budget_q=args.budget_q,
            window_minutes=args.window_minutes,
            entity_score=args.entity_score,
            budget_flows=budget_flows,
            top_k=args.top_k,
            review_per_entity=review_per_entity,
        )
        for frame in frames
    ]
    pooled = summarize(rows)
    if budget_flows is not None:
        budget_description = f"tối đa {budget_flows:,} flow review/ngày"
    elif budget_k is not None:
        budget_description = f"{budget_k} entity/ngày"
    else:
        budget_description = f"top {args.budget_q:.1%} entity/ngày"
    if review_per_entity > 0:
        budget_description += (
            f"; review tối đa {review_per_entity:,} flow/entity đã chọn"
        )
    payload = {
        "protocol": (
            "Gộp flow theo source_ip + cửa sổ thời gian, xếp hạng entity, "
            "rồi đo recall flow và precision flow trong các flow được review."
        ),
        "config": {
            "scores": str(scores),
            "window_minutes": args.window_minutes,
            "entity_score": args.entity_score,
            "top_k": args.top_k,
            "review_per_entity": review_per_entity,
            "budget_q": args.budget_q,
            "budget_k": budget_k,
            "budget_flows": budget_flows,
            "budget_description": budget_description,
        },
        "days": rows,
        "pooled": pooled,
    }
    save_json(payload, args.output)
    write_report(payload, args.report)

    print(f"Đã ghi {args.output}")
    print(f"Đã ghi {args.report}")
    print(
        f"entity alerts={pooled['entity_alerts']:,} "
        f"reviewed_flows={pooled['reviewed_flows']:,} "
        f"flow recall={pooled['flow']['recall']:.4f} "
        f"flow precision={pooled['flow']['precision']:.4f} "
        f"entity recall={pooled['entity']['recall']:.4f}"
    )


if __name__ == "__main__":
    main()
