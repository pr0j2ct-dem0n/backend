import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from constants.region_codes import REGION_CODE_TO_GU

load_dotenv()


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
    *, base_url: str, api_key: str, region_code: str, start_time: str, end_time: str
) -> dict[str, Any]:
    url = (
        f"{base_url}/{api_key}/json/DrainpipeMonitoringInfo/1/100/"
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


def fetch_raw_sewer_pipe_level(region_code: str = "all") -> dict[str, Any]:
    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")
    kst = timezone(timedelta(hours=9))
    end_dt = datetime.now(kst).replace(minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(hours=1)
    start_time = start_dt.strftime("%Y%m%d%H")
    end_time = end_dt.strftime("%Y%m%d%H")

    normalized = region_code.strip().lower()
    if normalized == "all":
        payloads = [
            _fetch_sewer_pipe_level_single(
                base_url=base_url,
                api_key=api_key,
                region_code=code,
                start_time=start_time,
                end_time=end_time,
            )
            for code in sorted(REGION_CODE_TO_GU.keys())
        ]
        return _merge_drainpipe_payloads(payloads)

    return _fetch_sewer_pipe_level_single(
        base_url=base_url,
        api_key=api_key,
        region_code=region_code,
        start_time=start_time,
        end_time=end_time,
    )


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
