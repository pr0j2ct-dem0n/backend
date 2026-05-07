from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, FloodHistoryItem, NotFoundGuResponse
from services.flood_history_service import (
    FloodHistoryDataError,
    get_flood_history_risk_by_gu,
    load_flood_history,
)

router = APIRouter(tags=["flood-history"])


def _error_response(exc: FloodHistoryDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/flood-history/gu",
    summary="자치구별 침수흔적도 위험도 조회",
    description="Shapefile 기반 과거 침수 이력 건수와 위험 점수를 자치구별로 반환합니다.",
    response_model=list[FloodHistoryItem],
    responses={500: {"model": ErrorResponse}},
)
def flood_history_by_gu() -> Any:
    try:
        return load_flood_history()
    except FloodHistoryDataError as exc:
        return _error_response(exc)


@router.get(
    "/flood-history/gu/{gu_name}/summary",
    summary="특정 자치구 침수흔적도 위험도 조회",
    description="요청한 자치구의 과거 침수 이력 건수와 위험 점수를 반환합니다.",
    response_model=FloodHistoryItem,
    responses={404: {"model": NotFoundGuResponse}, 500: {"model": ErrorResponse}},
)
def flood_history_gu_summary(gu_name: str) -> Any:
    try:
        item = get_flood_history_risk_by_gu(gu_name)
        if not item:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return item
    except FloodHistoryDataError as exc:
        return _error_response(exc)
