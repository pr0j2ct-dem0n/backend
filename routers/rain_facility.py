from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, NotFoundGuResponse, RainFacilityItem
from services.rain_facility_service import (
    RainFacilityDataError,
    get_rain_facility_by_gu,
    get_rain_facility_by_gu_summary,
)

router = APIRouter(tags=["rain-facility"])


def _error_response(exc: RainFacilityDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/rain-facility/gu",
    summary="자치구별 빗물이용시설 통계 조회",
    description="WATER_AREA/PRCS_CPCT/FCLT_QY/USE_QY 기반 자치구별 시설 통계를 반환합니다.",
    response_model=list[RainFacilityItem],
    responses={500: {"model": ErrorResponse}},
)
def rain_facility_by_gu() -> Any:
    try:
        return get_rain_facility_by_gu()
    except RainFacilityDataError as exc:
        return _error_response(exc)


@router.get(
    "/rain-facility/gu/{gu_name}/summary",
    summary="특정 자치구 빗물이용시설 통계 조회",
    description="요청한 자치구의 빗물이용시설 통계를 반환합니다.",
    response_model=RainFacilityItem,
    responses={404: {"model": NotFoundGuResponse}, 500: {"model": ErrorResponse}},
)
def rain_facility_gu_summary(gu_name: str) -> Any:
    try:
        item = get_rain_facility_by_gu_summary(gu_name)
        if not item:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return item
    except RainFacilityDataError as exc:
        return _error_response(exc)
