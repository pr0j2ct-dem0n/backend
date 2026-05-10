import os
import time
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

import requests
from dotenv import load_dotenv

from constants.region_codes import REGION_CODE_TO_GU

load_dotenv()

CACHE_TTL_SECONDS = float(os.getenv("SEOUL_API_CACHE_TTL_SEC", "45"))
_CACHE_LOCK = RLock()
_SEOUL_API_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class SeoulAPIError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SeoulAPIError(500, "환경 변수 누락", f"{name} 값이 없습니다.")
    return value


def _cache_get(key: str) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        cached = _SEOUL_API_CACHE.get(key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at < time.monotonic():
            _SEOUL_API_CACHE.pop(key, None)
            return None
        return payload


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _SEOUL_API_CACHE[key] = (time.monotonic() + CACHE_TTL_SECONDS, payload)


def fetch_raw_rainfall(start: int = 1, end: int = 100) -> dict[str, Any]:
    if start < 1 or end < 1 or start > end:
        raise SeoulAPIError(400, "잘못된 범위", "start/end 값을 확인하세요.")

    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")
    url = f"{base_url}/{api_key}/json/ListRainfallService/{start}/{end}/"

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        raise SeoulAPIError(502, "서울시 API 요청 실패", str(exc)) from exc

    if response.status_code != 200:
        raise SeoulAPIError(response.status_code, "서울시 API 응답 오류")

    try:
        return response.json()
    except ValueError as exc:
        preview = response.text[:200] if response.text else ""
        raise SeoulAPIError(502, "JSON 변환 실패", preview) from exc


def fetch_raw_river_stage(start: int = 1, end: int = 100) -> dict[str, Any]:
    if start < 1 or end < 1 or start > end:
        raise SeoulAPIError(400, "잘못된 범위", "start/end 값을 확인하세요.")

    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")
    url = f"{base_url}/{api_key}/json/ListRiverStageService/{start}/{end}/"

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        raise SeoulAPIError(502, "서울시 API 요청 실패", str(exc)) from exc

    if response.status_code != 200:
        raise SeoulAPIError(response.status_code, "서울시 API 응답 오류")

    try:
        return response.json()
    except ValueError as exc:
        preview = response.text[:200] if response.text else ""
        raise SeoulAPIError(502, "JSON 변환 실패", preview) from exc


def _fetch_sewer_pipe_level_single(
    *,
    base_url: str,
    api_key: str,
    region_code: str,
    start_time: str,
    end_time: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    url = (
        f"{base_url}/{api_key}/json/DrainpipeMonitoringInfo/{start}/{end}/"
        f"{region_code}/{start_time}/{end_time}"
    )

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        raise SeoulAPIError(502, "서울시 API 요청 실패", str(exc)) from exc

    if response.status_code != 200:
        raise SeoulAPIError(response.status_code, "서울시 API 응답 오류")

    try:
        return response.json()
    except ValueError as exc:
        preview = response.text[:200] if response.text else ""
        raise SeoulAPIError(502, "JSON 변환 실패", preview) from exc


def _extract_first_data_obj(payload: dict[str, Any]) -> dict[str, Any] | None:
    for value in payload.values():
        if isinstance(value, dict) and isinstance(value.get("row"), list):
            return value
    return None


def _fetch_sewer_pipe_level_all_pages(
    *, base_url: str, api_key: str, region_code: str, start_time: str, end_time: str
) -> dict[str, Any]:
    page_size = 1000
    first = _fetch_sewer_pipe_level_single(
        base_url=base_url,
        api_key=api_key,
        region_code=region_code,
        start_time=start_time,
        end_time=end_time,
        start=1,
        end=page_size,
    )

    first_obj = _extract_first_data_obj(first)
    if not first_obj:
        return first

    all_rows = extract_rows(first)
    total_count = first_obj.get("list_total_count")
    try:
        total = int(total_count)
    except (TypeError, ValueError):
        total = len(all_rows)

    if total <= len(all_rows):
        return first

    start = page_size + 1
    while start <= total:
        end = min(start + page_size - 1, total)
        page_payload = _fetch_sewer_pipe_level_single(
            base_url=base_url,
            api_key=api_key,
            region_code=region_code,
            start_time=start_time,
            end_time=end_time,
            start=start,
            end=end,
        )
        all_rows.extend(extract_rows(page_payload))
        start = end + 1

    return {
        "DrainpipeMonitoringInfo": {
            "list_total_count": len(all_rows),
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다"},
            "row": all_rows,
        }
    }


def _merge_drainpipe_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    merged_rows: list[dict[str, Any]] = []
    for payload in payloads:
        merged_rows.extend(extract_rows(payload))

    return {
        "DrainpipeMonitoringInfo": {
            "list_total_count": len(merged_rows),
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다"},
            "row": merged_rows,
        }
    }


def fetch_raw_sewer_pipe_level_in_range(region_code: str, start_time: str, end_time: str) -> dict[str, Any]:
    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")
    normalized = region_code.strip().lower()
    cache_key = f"drainpipe:{normalized}:{start_time}:{end_time}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if normalized == "all":
        payloads = [
            _fetch_sewer_pipe_level_all_pages(
                base_url=base_url,
                api_key=api_key,
                region_code=code,
                start_time=start_time,
                end_time=end_time,
            )
            for code in sorted(REGION_CODE_TO_GU.keys())
        ]
        merged = _merge_drainpipe_payloads(payloads)
        _cache_set(cache_key, merged)
        return merged

    payload = _fetch_sewer_pipe_level_all_pages(
        base_url=base_url,
        api_key=api_key,
        region_code=region_code,
        start_time=start_time,
        end_time=end_time,
    )
    _cache_set(cache_key, payload)
    return payload


def fetch_raw_sewer_pipe_level(region_code: str = "all") -> dict[str, Any]:
    kst = timezone(timedelta(hours=9))
    end_dt = datetime.now(kst).replace(minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(hours=1)
    start_time = start_dt.strftime("%Y%m%d%H")
    end_time = end_dt.strftime("%Y%m%d%H")
    return fetch_raw_sewer_pipe_level_in_range(region_code=region_code, start_time=start_time, end_time=end_time)


def fetch_raw_rainwater_facility(start: int = 1, end: int = 1000) -> dict[str, Any]:
    if start < 1 or end < 1 or start > end:
        raise SeoulAPIError(400, "잘못된 범위", "start/end 값을 확인하세요.")

    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")
    url = f"{base_url}/{api_key}/json/TbUseRainwaterFacilityV/{start}/{end}/"

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        raise SeoulAPIError(502, "서울시 API 요청 실패", str(exc)) from exc

    if response.status_code != 200:
        raise SeoulAPIError(response.status_code, "서울시 API 응답 오류")

    try:
        return response.json()
    except ValueError as exc:
        preview = response.text[:200] if response.text else ""
        raise SeoulAPIError(502, "JSON 변환 실패", preview) from exc


def extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data_obj: dict[str, Any] | None = None

    if "SeoulRtdFndRgnQly" in payload and isinstance(payload["SeoulRtdFndRgnQly"], dict):
        data_obj = payload["SeoulRtdFndRgnQly"]
    else:
        for value in payload.values():
            if isinstance(value, dict) and isinstance(value.get("row"), list):
                data_obj = value
                break

    if not data_obj:
        return []

    rows = data_obj.get("row", [])
    return rows if isinstance(rows, list) else []
