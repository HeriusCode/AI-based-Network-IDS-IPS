"""Background CSV-to-AI pipeline used by the phase-one desktop demo."""

from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app.services.ai_client import AiClient


# GeneratedLabelledFlows (CIC-IDS2017) uses these legacy spellings while the
# packaged detection model follows the CIC-IDS2018 schema.
FEATURE_RENAMES = {
    "Total Length of Fwd Packets": "Fwd Packets Length Total",
    "Total Length of Bwd Packets": "Bwd Packets Length Total",
    "Min Packet Length": "Packet Length Min",
    "Max Packet Length": "Packet Length Max",
    "Average Packet Size": "Avg Packet Size",
    "Init_Win_bytes_forward": "Init Fwd Win Bytes",
    "Init_Win_bytes_backward": "Init Bwd Win Bytes",
    "act_data_pkt_fwd": "Fwd Act Data Packets",
    "min_seg_size_forward": "Fwd Seg Size Min",
}


class DetectionWorkerSignals(QObject):
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)


class HealthWorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class AiHealthWorker(QRunnable):
    def __init__(self, client: AiClient) -> None:
        super().__init__()
        self.client = client
        self.signals = HealthWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.completed.emit(self.client.health())
        except Exception as error:
            self.signals.failed.emit(str(error))


def _clean_value(value: object) -> object:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    return number if math.isfinite(number) else None


class DetectionCsvWorker(QRunnable):
    """Stream a CSV in batches and retain only alert rows for the UI."""

    def __init__(
        self,
        path: str | Path,
        client: AiClient,
        batch_size: int = 500,
        max_rows: int = 20_000,
        max_visible_alerts: int = 1_000,
    ) -> None:
        super().__init__()
        self.path = Path(path)
        self.client = client
        self.batch_size = max(1, batch_size)
        self.max_rows = max(1, max_rows)
        self.max_visible_alerts = max(1, max_visible_alerts)
        self.signals = DetectionWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._run_pipeline()
        except Exception as error:  # Worker must report failures to the Qt thread.
            self.signals.failed.emit(str(error))
            return
        self.signals.completed.emit(result)

    def _run_pipeline(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Không tìm thấy CSV: {self.path}")

        total = benign = attack = high = 0
        score_sum = 0.0
        model_version = "unknown"
        alerts: list[dict[str, Any]] = []
        attack_types: Counter[str] = Counter()
        trend: list[list[int]] = []

        # CIC feature headers are ASCII. Replacing an occasional non-UTF-8
        # label byte keeps the large file streaming instead of loading it all
        # in memory solely to retry another encoding.
        handle = self.path.open("r", encoding="utf-8-sig", errors="replace", newline="")
        try:
            reader = csv.DictReader(handle)
            batch: list[dict[str, Any]] = []
            for raw in reader:
                record = {
                    FEATURE_RENAMES.get(str(key).strip(), str(key).strip()): _clean_value(value)
                    for key, value in raw.items()
                    if key is not None
                }
                batch.append(record)
                if len(batch) >= self.batch_size:
                    stats = self._process_batch(batch, len(alerts))
                    batch = []
                    total, benign, attack, high, score_sum, model_version = self._merge(
                        stats, total, benign, attack, high, score_sum, model_version
                    )
                    alerts.extend(stats["alerts"][: max(0, self.max_visible_alerts - len(alerts))])
                    attack_types.update(stats["attack_types"])
                    trend.append([stats["benign"], stats["attack"]])
                    self.signals.progress.emit(total, self.max_rows)
                if total + len(batch) >= self.max_rows:
                    break

            if batch and total < self.max_rows:
                batch = batch[: self.max_rows - total]
                stats = self._process_batch(batch, len(alerts))
                total, benign, attack, high, score_sum, model_version = self._merge(
                    stats, total, benign, attack, high, score_sum, model_version
                )
                alerts.extend(stats["alerts"][: max(0, self.max_visible_alerts - len(alerts))])
                attack_types.update(stats["attack_types"])
                trend.append([stats["benign"], stats["attack"]])
                self.signals.progress.emit(total, self.max_rows)
        finally:
            if not handle.closed:
                handle.close()

        if total == 0:
            raise ValueError("CSV không có dòng dữ liệu để phân tích.")
        return {
            "file": str(self.path),
            "total": total,
            "benign": benign,
            "attack": attack,
            "high": high,
            "average_score": score_sum / total,
            "alerts": alerts,
            "attack_types": dict(attack_types),
            "trend": trend[-32:],
            "model_version": model_version,
            "limited": total >= self.max_rows,
            "max_rows": self.max_rows,
        }

    def _process_batch(self, batch: list[dict[str, Any]], alert_offset: int) -> dict[str, Any]:
        response = self.client.detect(batch)
        predictions = response.get("predictions", [])
        if len(predictions) != len(batch):
            raise RuntimeError("Số kết quả detection không khớp số dòng gửi lên.")

        attack_indexes = [index for index, item in enumerate(predictions) if item.get("label") == "ATTACK"]
        type_results: list[dict[str, Any]] = []
        if attack_indexes:
            classified = self.client.classify_attack([batch[index] for index in attack_indexes])
            type_results = classified.get("predictions", [])
        types_by_index = {
            source_index: type_results[position]
            for position, source_index in enumerate(attack_indexes)
            if position < len(type_results)
        }

        alerts: list[dict[str, Any]] = []
        type_counts: Counter[str] = Counter()
        high = 0
        score_sum = 0.0
        for index, (record, prediction) in enumerate(zip(batch, predictions, strict=True)):
            score = float(prediction.get("attack_score", 0.0))
            score_sum += score
            if prediction.get("label") != "ATTACK":
                continue
            risk = str(prediction.get("risk_level", "MEDIUM"))
            high += int(risk == "HIGH")
            classification = types_by_index.get(index, {})
            attack_type = str(classification.get("label") or "Chưa xác định")
            type_confidence = float(classification.get("confidence", 0.0))
            if attack_type.lower() == "benign" or type_confidence < 0.50:
                attack_type = "Chưa xác định"
            type_counts[attack_type] += 1
            alerts.append(
                {
                    "id": f"AI-{alert_offset + len(alerts) + 1:05d}",
                    "record": record,
                    "score": score,
                    "risk": risk,
                    "attack_type": attack_type,
                    "type_confidence": type_confidence,
                }
            )
        attacks = len(attack_indexes)
        return {
            "total": len(batch), "benign": len(batch) - attacks, "attack": attacks,
            "high": high, "score_sum": score_sum, "alerts": alerts,
            "attack_types": type_counts, "model_version": response.get("model_version", "unknown"),
        }

    @staticmethod
    def _merge(
        stats: dict[str, Any], total: int, benign: int, attack: int, high: int,
        score_sum: float, model_version: str,
    ) -> tuple[int, int, int, int, float, str]:
        return (
            total + stats["total"], benign + stats["benign"], attack + stats["attack"],
            high + stats["high"], score_sum + stats["score_sum"],
            str(stats.get("model_version") or model_version),
        )
