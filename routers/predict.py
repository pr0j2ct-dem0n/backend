from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, PredictAreaItem, PredictResponse
from services.predict_service import PredictDataError, predict_flood_area_by_gu, predict_flood_areas

router = APIRouter(tags=["predict"])


def _error_response(exc: PredictDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/predict/flood/areas",
    summary="자치구별 유입수량 기반 침수 위험 예측",
    description="강우량, 하수관로 현재 수위, 하천 수위, 침수흔적도, 배수 capability를 결합해 자치구별 침수 위험 점수를 반환합니다.",
    response_model=PredictResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def predict_flood_areas_endpoint(
    start_time: str = Query(...),
    end_time: str = Query(...),
) -> Any:
    try:
        return predict_flood_areas(start_time=start_time, end_time=end_time)
    except PredictDataError as exc:
        return _error_response(exc)


@router.get(
    "/predict/flood/areas/{gu_name}",
    summary="특정 자치구 침수 위험 상세 예측",
    description="요청한 자치구의 침수 위험 점수와 구성 요소를 상세 반환합니다.",
    response_model=PredictAreaItem,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def predict_flood_area_by_gu_endpoint(
    gu_name: str,
    start_time: str = Query(...),
    end_time: str = Query(...),
) -> Any:
    try:
        return predict_flood_area_by_gu(gu_name=gu_name, start_time=start_time, end_time=end_time)
    except PredictDataError as exc:
        return _error_response(exc)
