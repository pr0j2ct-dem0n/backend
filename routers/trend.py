from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse
from services.seoul_api_service import SeoulAPIError
from services.trend_service import get_drainpipe_trend

router = APIRouter(tags=["trend"])


def _error_response(exc: SeoulAPIError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/trend/drainpipe/{region}",
    summary="하수관로 수위 추세 분석",
    description="지정 구간의 하수관로 수위 시계열을 기반으로 상승/하락 추세를 계산합니다.",
    responses={500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def drainpipe_trend(region: str, start_time: str = Query(...), end_time: str = Query(...)) -> Any:
    try:
        return get_drainpipe_trend(region=region, start_time=start_time, end_time=end_time)
    except SeoulAPIError as exc:
        return _error_response(exc)
