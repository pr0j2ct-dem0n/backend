from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.prediction_service import aggregate_rainfall_by_gu, predict_risk
from services.seoul_api_service import SeoulAPIError, extract_rows, fetch_raw_rainfall

router = APIRouter(tags=["prediction"])


def _error_response(exc: SeoulAPIError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get("/predict")
def predict_all(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=100, ge=1),
) -> Any:
    try:
        payload = fetch_raw_rainfall(start=start, end=end)
        rows = extract_rows(payload)
        gu_stats = aggregate_rainfall_by_gu(rows)
        return [predict_risk(gu_stat) for gu_stat in gu_stats]
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get("/predict/{gu_name}")
def predict_one(
    gu_name: str,
    start: int = Query(default=1, ge=1),
    end: int = Query(default=100, ge=1),
) -> Any:
    try:
        payload = fetch_raw_rainfall(start=start, end=end)
        rows = extract_rows(payload)
        gu_rows = [row for row in rows if row.get("GU_NM") == gu_name]
        gu_stats = aggregate_rainfall_by_gu(gu_rows)
        if not gu_stats:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return predict_risk(gu_stats[0])
    except SeoulAPIError as exc:
        return _error_response(exc)
