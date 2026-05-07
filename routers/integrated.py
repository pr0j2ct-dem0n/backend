from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, IntegratedResponse, NotFoundGuResponse
from services.integrated_service import IntegratedDataError, get_integrated_data_by_gu

router = APIRouter(tags=["integrated"])


def _error_response(exc: IntegratedDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/integrated/gu/{gu_name}",
    summary="자치구 통합 구조 위험도 조회",
    description="하수도 capacity 기반 구조적 위험도를 반환합니다.",
    response_model=IntegratedResponse,
    responses={404: {"model": NotFoundGuResponse}, 500: {"model": ErrorResponse}},
)
def integrated_gu_summary(gu_name: str) -> Any:
    try:
        return get_integrated_data_by_gu(gu_name)
    except IntegratedDataError as exc:
        return _error_response(exc)
