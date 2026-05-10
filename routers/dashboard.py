from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, DashboardGuItem
from services.sewer_service import SewerDataError, get_dashboard_data

router = APIRouter(tags=["dashboard"])


def _error_response(exc: SewerDataError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/api/dashboard/all",
    summary="전체 자치구 대시보드 데이터",
    description="전체 자치구의 예측 부하율과 상태를 반환합니다.",
    response_model=list[DashboardGuItem],
    responses={500: {"model": ErrorResponse}},
)
def dashboard_all() -> Any:
    try:
        return get_dashboard_data()
    except SewerDataError as exc:
        return _error_response(exc)
