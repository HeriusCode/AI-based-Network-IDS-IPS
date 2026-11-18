"""FastAPI service for detection, attack-type prediction, and traffic forecast."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import json
import os
import warnings

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from src.common import DETECTION_MODEL, MODEL_DIR, load_bundle, prepare_features
    from src.predict import compute_scores
    from src.predict_traffic import forecast_frame, validate_bundle
except ModuleNotFoundError:  # Allows: python src/api.py
    from common import DETECTION_MODEL, MODEL_DIR, load_bundle, prepare_features
    from predict import compute_scores
    from predict_traffic import forecast_frame, validate_bundle


MODEL_PATH = Path(os.environ.get("IDS_MODEL", DETECTION_MODEL))
TRAFFIC_MODEL_PATH = Path(
    os.environ.get("IDS_TRAFFIC_MODEL", MODEL_DIR / "traffic_forecast.joblib")
)
ATTACK_TYPE_MODEL_PATH = Path(
    os.environ.get("IDS_ATTACK_TYPE_MODEL", MODEL_DIR / "attack_type_model.joblib")
)

model_bundle: dict[str, Any] | None = None
traffic_bundle: dict[str, Any] | None = None
attack_type_bundle: dict[str, Any] | None = None


class TrafficPoint(BaseModel):
    timestamp: str
    packets_per_second: float | None = None
    bytes_per_second: float | None = None


class ForecastRequest(BaseModel):
    history: list[TrafficPoint]
    horizon: int = 12


@asynccontextmanager
async def lifespan(_: FastAPI):
    global model_bundle, traffic_bundle, attack_type_bundle
    try:
        model_bundle = load_bundle(MODEL_PATH)
    except FileNotFoundError as error:
        warnings.warn(str(error), stacklevel=2)
        model_bundle = None
    yield
    model_bundle = None
    traffic_bundle = None
    attack_type_bundle = None


app = FastAPI(
    title="AI Network IDS API",
    version="1.2.0",
    description=(
        "Phát hiện bất thường flow, dự báo lưu lượng packets/s–bytes/s, "
        "và phân loại loại tấn công."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "System",
            "description": "Trạng thái API và các model đã đóng gói.",
        },
        {
            "name": "Detection",
            "description": "Phát hiện flow hiện tại là BENIGN hay ATTACK.",
        },
        {
            "name": "Classification",
            "description": "Phân loại loại tấn công của flow hiện tại.",
        },
        {
            "name": "Forecast",
            "description": "Dự báo lưu lượng mạng trong tương lai.",
        },
    ],
)


def _model_version(bundle: dict[str, Any]) -> str:
    return str(bundle.get("version") or bundle.get("created_at") or "unknown")


def _risk_level(score: float, threshold: float) -> str:
    if score >= 0.8:
        return "HIGH"
    if score >= threshold:
        return "MEDIUM"
    return "LOW"


def get_traffic_bundle() -> dict[str, Any]:
    global traffic_bundle
    if traffic_bundle is None:
        if not TRAFFIC_MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Chưa có model traffic tại {TRAFFIC_MODEL_PATH}. "
                    "Hãy chạy src/train_traffic_forecast.py trước."
                ),
            )
        bundle = joblib.load(TRAFFIC_MODEL_PATH)
        try:
            validate_bundle(bundle)
        except ValueError as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
        traffic_bundle = bundle
    return traffic_bundle


def get_attack_type_bundle() -> dict[str, Any]:
    global attack_type_bundle
    if attack_type_bundle is None:
        if not ATTACK_TYPE_MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Chưa có model attack-type tại {ATTACK_TYPE_MODEL_PATH}. "
                    "Hãy chạy src/train_prediction.py trước."
                ),
            )
        try:
            bundle = load_bundle(ATTACK_TYPE_MODEL_PATH)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
        if bundle.get("task") != "attack_type_prediction":
            raise HTTPException(
                status_code=500,
                detail=f"Model {ATTACK_TYPE_MODEL_PATH} không phải attack-type model.",
            )
        attack_type_bundle = bundle
    return attack_type_bundle


def _record_dict(point: TrafficPoint) -> dict[str, Any]:
    return point.model_dump() if hasattr(point, "model_dump") else point.dict()


def _validated_feature_frame(
    records: list[dict[str, Any]], bundle: dict[str, Any]
) -> pd.DataFrame:
    """Validate the request schema before model imputation.

    Missing values inside an existing feature are handled by the model's
    imputer, but silently inventing an entirely missing feature column can turn
    a broken collector request into a plausible BENIGN response.  Phase-one
    integrations therefore require the complete training schema.
    """
    normalized = [
        {str(key).strip(): value for key, value in record.items()}
        for record in records
    ]
    required = [str(column) for column in bundle["feature_columns"]]
    missing_by_record = [
        [column for column in required if column not in record]
        for record in normalized
    ]
    first_missing = next(
        ((index, missing) for index, missing in enumerate(missing_by_record) if missing),
        None,
    )
    if first_missing is not None:
        index, missing = first_missing
        preview = ", ".join(missing[:10])
        suffix = "..." if len(missing) > 10 else ""
        raise HTTPException(
            status_code=422,
            detail=(
                f"Dòng {index + 1} thiếu {len(missing)}/{len(required)} đặc trưng bắt buộc: "
                f"{preview}{suffix}"
            ),
        )
    return prepare_features(pd.DataFrame(normalized), required)


@app.get("/health", tags=["System"], summary="Check API and model health")
def health() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok" if model_bundle is not None else "model_not_loaded",
        "model": str(MODEL_PATH),
        "traffic_model": str(TRAFFIC_MODEL_PATH),
        "traffic_model_available": TRAFFIC_MODEL_PATH.exists(),
        "attack_type_model": str(ATTACK_TYPE_MODEL_PATH),
        "attack_type_model_available": ATTACK_TYPE_MODEL_PATH.exists(),
    }
    if model_bundle is not None:
        payload["task"] = model_bundle.get("task", "binary_detection")
        payload["threshold"] = float(model_bundle.get("decision_threshold", 0.5))
        payload["model_version"] = _model_version(model_bundle)
        payload["detection_feature_count"] = len(model_bundle["feature_columns"])
    if TRAFFIC_MODEL_PATH.exists():
        try:
            traffic = get_traffic_bundle()
            payload["traffic_model_version"] = _model_version(traffic)
            payload["forecast_targets"] = list(traffic.get("targets", []))
        except (FileNotFoundError, ValueError, KeyError) as error:
            payload["traffic_model_error"] = str(error)
    if ATTACK_TYPE_MODEL_PATH.exists():
        try:
            attack = get_attack_type_bundle()
            payload["attack_type_model_version"] = _model_version(attack)
            payload["attack_families"] = list(attack.get("classes", []))
            payload["attack_type_confidence_threshold"] = float(
                attack.get("confidence_threshold", 0.50)
            )
        except (FileNotFoundError, ValueError, KeyError) as error:
            payload["attack_type_model_error"] = str(error)
    return payload


@app.post(
    "/detect",
    tags=["Detection"],
    summary="Detect whether the current flow is BENIGN or ATTACK",
)
@app.post("/predict", include_in_schema=False, deprecated=True)
def detect(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if model_bundle is None:
        raise HTTPException(status_code=503, detail="Model chưa được tải.")
    records = payload if isinstance(payload, list) else [payload]
    if not records:
        raise HTTPException(status_code=422, detail="Danh sách input không được rỗng.")

    X = _validated_feature_frame(records, model_bundle)
    scores = compute_scores(model_bundle, X)
    threshold = float(model_bundle.get("decision_threshold", 0.5))
    labels = (scores >= threshold).astype(int)
    is_anomaly = model_bundle.get("task") == "anomaly_detection"
    version = _model_version(model_bundle)

    results = []
    for label, score in zip(labels, scores, strict=True):
        item: dict[str, Any] = {
            "prediction": int(label),
            "label": "ATTACK" if label == 1 else "BENIGN",
            "attack_score": float(score),
            "threshold": threshold,
            "risk_level": _risk_level(float(score), threshold),
            "model_version": version,
        }
        if is_anomaly:
            item["anomaly_score"] = float(score)
        else:
            item["attack_probability"] = float(score)
        results.append(item)
    return {"count": len(results), "model_version": version, "predictions": results}


@app.post(
    "/classify-attack",
    tags=["Classification"],
    summary="Classify the current attack type",
)
@app.post("/predict/type", include_in_schema=False, deprecated=True)
def classify_attack(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Predict the attack type of one or more flows."""
    bundle = get_attack_type_bundle()
    records = payload if isinstance(payload, list) else [payload]
    if not records:
        raise HTTPException(status_code=422, detail="Danh sách input không được rỗng.")

    normalized: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("features"), dict):
            record = record["features"]
        normalized.append(record)

    X = _validated_feature_frame(normalized, bundle)
    probabilities = bundle["pipeline"].predict_proba(X)
    classes = [str(value) for value in bundle["pipeline"].named_steps["classifier"].classes_]
    version = _model_version(bundle)

    predictions = []
    for row in probabilities:
        order = np.argsort(-row)[:5]
        predictions.append(
            {
                "label": classes[int(np.argmax(row))],
                "confidence": float(np.max(row)),
                "top_probabilities": [
                    {"label": classes[int(index)], "probability": float(row[index])}
                    for index in order
                ],
            }
        )
    return {"count": len(predictions), "model_version": version, "predictions": predictions}


@app.post(
    "/forecast/traffic",
    tags=["Forecast"],
    summary="Forecast future packets/s and bytes/s",
)
@app.post("/forecast", include_in_schema=False, deprecated=True)
def forecast_traffic(request: ForecastRequest) -> dict[str, Any]:
    """Forecast the next ``horizon`` intervals from recent history."""
    bundle = get_traffic_bundle()
    if not request.history:
        raise HTTPException(status_code=422, detail="History không được rỗng.")
    if request.horizon <= 0 or request.horizon > 1440:
        raise HTTPException(status_code=422, detail="horizon phải trong khoảng 1..1440.")

    history = pd.DataFrame([_record_dict(point) for point in request.history])
    for target in bundle["targets"]:
        if target not in history or history[target].isna().all():
            raise HTTPException(
                status_code=422,
                detail=f"History thiếu target bắt buộc: {target}",
            )

    try:
        result, overall_risk = forecast_frame(history, bundle, request.horizon)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    forecast_records = json.loads(result.to_json(orient="records", date_format="iso"))
    return {
        "model_version": _model_version(bundle),
        "risk_level": overall_risk,
        "horizon": request.horizon,
        "interval_seconds": int(bundle.get("interval_seconds", 1)),
        "evaluation_metrics": bundle.get("evaluation_metrics", {}),
        "risk_thresholds": bundle.get("risk_thresholds", {}),
        "prediction_intervals": bundle.get("prediction_intervals", {}),
        "forecast": forecast_records,
    }
