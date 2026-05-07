from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.river_service import aggregate_river_by_gu
from services.seoul_api_service import SeoulAPIError, extract_rows, fetch_raw_river_stage

router = APIRouter(tags=["river"])


def _error_response(exc: SeoulAPIError) -> JSONResponse:
    content: dict[str, Any] = {"error": exc.error}
    if exc.detail:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


@router.get(
    "/river/raw",
    summary="하천 수위 원본 조회",
    description="서울시 ListRiverStageService 원본 응답(JSON)을 반환합니다.",
)
def get_river_raw(
    start: int = Query(default=1, ge=1, description="조회 시작 인덱스"),
    end: int = Query(default=100, ge=1, description="조회 종료 인덱스"),
) -> Any:
    try:
        return fetch_raw_river_stage(start=start, end=end)
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get(
    "/river/gu",
    summary="자치구별 하천 수위 요약",
    description="자치구별 평균/최대 하천 수위와 관측소 개수를 반환합니다.",
)
def get_river_by_gu(
    start: int = Query(default=1, ge=1, description="조회 시작 인덱스"),
    end: int = Query(default=100, ge=1, description="조회 종료 인덱스"),
) -> Any:
    try:
        payload = fetch_raw_river_stage(start=start, end=end)
        rows = extract_rows(payload)
        return aggregate_river_by_gu(rows)
    except SeoulAPIError as exc:
        return _error_response(exc)


@router.get(
    "/river/gu/{gu_name}/summary",
    summary="특정 자치구 하천 수위 요약",
    description="요청한 자치구의 평균/최대 하천 수위와 관측소 개수를 반환합니다.",
)
def get_river_gu_summary(
    gu_name: str,
    start: int = Query(default=1, ge=1, description="조회 시작 인덱스"),
    end: int = Query(default=100, ge=1, description="조회 종료 인덱스"),
) -> Any:
    try:
        payload = fetch_raw_river_stage(start=start, end=end)
        rows = extract_rows(payload)
        gu_rows = [row for row in rows if row.get("GU_OFC_NM") == gu_name]
        gu_stats = aggregate_river_by_gu(gu_rows)
        if not gu_stats:
            return JSONResponse(status_code=404, content={"error": "데이터 없음", "gu": gu_name})
        return gu_stats[0]
    except SeoulAPIError as exc:
        return _error_response(exc)
