from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.rainfall_service import aggregate_rainfall_by_gu
from services.seoul_api_service import SeoulAPIError, extract_rows, fetch_raw_rainfall

router = APIRouter(tags=["rainfall"])


def _error_response(exc: SeoulAPIError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get("/rainfall/raw")
def get_rainfall_raw(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=100, ge=1),
) -> Any:
    try:
        return fetch_raw_rainfall(start=start, end=end)
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get("/rainfall/gu")
def get_rainfall_by_gu(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=100, ge=1),
) -> Any:
    try:
        payload = fetch_raw_rainfall(start=start, end=end)
        rows = extract_rows(payload)
        return aggregate_rainfall_by_gu(rows)
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get("/rainfall/gu/{gu_name}/summary")
def get_rainfall_gu_summary(
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
        return gu_stats[0]
    except SeoulAPIError as exc:
        return _error_response(exc)
