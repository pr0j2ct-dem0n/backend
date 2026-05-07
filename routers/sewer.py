from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, NotFoundGuResponse, SewerGuItem
from services.sewer_service import (
    SewerDataError,
    get_raw_columns,
    get_sewer_summary_by_gu,
    list_sewer_by_gu,
)

router = APIRouter(tags=["sewer"])


def _error_response(exc: SewerDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/sewer/raw-columns",
    summary="하수도 CSV 컬럼 조회",
    description="하수도 시설 CSV의 컬럼명을 반환합니다.",
    response_model=list[str],
    responses={500: {"model": ErrorResponse}},
)
def sewer_raw_columns() -> Any:
    try:
        return get_raw_columns()
    except SewerDataError as exc:
        return _error_response(exc)


@router.get(
    "/sewer/gu",
    summary="자치구별 하수도 시설 요약",
    description="자치구별 하수도 시설 길이(암거/개거/관거/U형측구/횡단하수거)를 반환합니다.",
    response_model=list[SewerGuItem],
    responses={500: {"model": ErrorResponse}},
)
def sewer_by_gu() -> Any:
    try:
        return list_sewer_by_gu()
    except SewerDataError as exc:
        return _error_response(exc)


@router.get(
    "/sewer/gu/{gu_name}/summary",
    summary="특정 자치구 하수도 시설 요약",
    description="요청한 자치구의 하수도 시설 길이 요약을 반환합니다.",
    response_model=SewerGuItem,
    responses={404: {"model": NotFoundGuResponse}, 500: {"model": ErrorResponse}},
)
def sewer_gu_summary(gu_name: str) -> Any:
    try:
        item = get_sewer_summary_by_gu(gu_name)
        if not item:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return item
    except SewerDataError as exc:
        return _error_response(exc)
