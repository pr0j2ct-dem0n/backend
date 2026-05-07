from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, NotFoundGuResponse, WasteGuItem
from services.waste_service import (
    WasteDataError,
    get_raw_columns,
    get_waste_summary_by_gu,
    list_waste_by_gu,
)

router = APIRouter(tags=["waste"])


def _error_response(exc: WasteDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/waste/raw-columns",
    summary="생활폐기물 CSV 컬럼 조회",
    description="생활계폐기물 발생량 CSV의 컬럼명을 반환합니다.",
    response_model=list[str],
    responses={500: {"model": ErrorResponse}},
)
def waste_raw_columns() -> Any:
    try:
        return get_raw_columns()
    except WasteDataError as exc:
        return _error_response(exc)


@router.get(
    "/waste/gu",
    summary="자치구별 생활폐기물 발생량 조회",
    description="자치구별 생활폐기물 발생량(waste_generation)을 반환합니다.",
    response_model=list[WasteGuItem],
    responses={500: {"model": ErrorResponse}},
)
def waste_by_gu() -> Any:
    try:
        return list_waste_by_gu()
    except WasteDataError as exc:
        return _error_response(exc)


@router.get(
    "/waste/gu/{gu_name}/summary",
    summary="특정 자치구 생활폐기물 발생량 조회",
    description="요청한 자치구의 생활폐기물 발생량을 반환합니다.",
    response_model=WasteGuItem,
    responses={404: {"model": NotFoundGuResponse}, 500: {"model": ErrorResponse}},
)
def waste_gu_summary(gu_name: str) -> Any:
    try:
        item = get_waste_summary_by_gu(gu_name)
        if not item:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return item
    except WasteDataError as exc:
        return _error_response(exc)
