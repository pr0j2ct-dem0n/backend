from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from schemas.api_models import ErrorResponse, NotFoundGuResponse, SewerPipeGuItem
from services.seoul_api_service import SeoulAPIError, extract_rows, fetch_raw_sewer_pipe_level
from services.sewer_pipe_service import _pick_gu, _pick_level, aggregate_sewer_pipe_by_gu, build_sewer_pipe_trend

router = APIRouter(tags=["sewer-pipe"])


def _error_response(exc: SeoulAPIError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/sewer-pipe/raw",
    summary="하수관로 수위 원본 조회",
    description="DrainpipeMonitoringInfo API를 호출해 현재 시각 기준 최근 1시간 원본 데이터를 반환합니다.",
)
def get_sewer_pipe_raw(
    region_code: str = Query(default="all", description="권역 코드 (예: 01, 기본값: all)"),
) -> Any:
    try:
        payload = fetch_raw_sewer_pipe_level(region_code=region_code)
        rows = extract_rows(payload)
        filtered_rows = []
        for row in rows:
            level = _pick_level(row)
            if level is None or level < 0:
                continue
            filtered_rows.append(row)
        return {
            "DrainpipeMonitoringInfo": {
                "list_total_count": len(filtered_rows),
                "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다"},
                "row": filtered_rows,
            }
        }
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get(
    "/sewer-pipe/gu",
    summary="자치구별 하수관로 수위 요약",
    description="현재 시각 기준 최근 1시간 데이터로 자치구별 평균/최대 수위와 관측 지점 개수를 반환합니다.",
    response_model=list[SewerPipeGuItem],
    responses={500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def get_sewer_pipe_by_gu(
    region_code: str = Query(default="all", description="권역 코드 (예: 01, 기본값: all)"),
) -> Any:
    try:
        payload = fetch_raw_sewer_pipe_level(region_code=region_code)
        rows = extract_rows(payload)
        return aggregate_sewer_pipe_by_gu(rows)
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get(
    "/sewer-pipe/gu/{gu_name}/summary",
    summary="특정 자치구 하수관로 수위 요약",
    description="현재 시각 기준 최근 1시간 데이터에서 요청한 자치구의 하수관로 평균/최대 수위를 반환합니다.",
    response_model=SewerPipeGuItem,
    responses={404: {"model": NotFoundGuResponse}, 500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def get_sewer_pipe_gu_summary(
    gu_name: str,
    region_code: str = Query(default="all", description="권역 코드 (예: 01, 기본값: all)"),
) -> Any:
    try:
        payload = fetch_raw_sewer_pipe_level(region_code=region_code)
        rows = extract_rows(payload)
        gu_rows = [row for row in rows if _pick_gu(row) == gu_name]
        gu_stats = aggregate_sewer_pipe_by_gu(gu_rows)
        if not gu_stats:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return gu_stats[0]
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get(
    "/sewer-pipe/trend",
    summary="서울 평균 하수관로 수위 추세",
    description="최근 1시간 하수관로 원본 데이터에서 음수값을 제외하고 5분 평균 추세를 반환합니다.",
)
def get_sewer_pipe_trend(
    region_code: str = Query(default="all", description="권역 코드 (예: 01, 기본값: all)"),
) -> Any:
    try:
        payload = fetch_raw_sewer_pipe_level(region_code=region_code)
        rows = extract_rows(payload)
        return build_sewer_pipe_trend(rows, bucket_minutes=5)
    except SeoulAPIError as exc:
        return _error_response(exc)
