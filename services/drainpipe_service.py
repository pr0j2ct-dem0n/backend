import os
from typing import Any

import requests
from dotenv import load_dotenv

from services.seoul_api_service import SeoulAPIError

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SeoulAPIError(500, "환경 변수 누락", f"{name} 값이 없습니다.")
    return value


def get_drainpipe_raw(region: str, start_time: str, end_time: str) -> dict[str, Any]:
    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")

    url = (
        f"{base_url}/{api_key}/json/DrainpipeMonitoringInfo/1/100/"
        f"{region}/{start_time}/{end_time}"
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


def _pick_time(row: dict[str, Any]) -> str | None:
    for key in ("MESURE_DE", "MEASURE_TIME", "TM", "TIME", "DT"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _pick_level(row: dict[str, Any]) -> float | None:
    for key in ("PIPE_LEVEL", "WL", "LEVEL", "WATER_LEVEL", "CURR_LEVEL", "RLTM_WL", "SEWER_LEVEL"):
        value = row.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _pick_gu(row: dict[str, Any]) -> str | None:
    for key in ("GU_NM", "GU_OFC_NM", "SGG_NM", "SIGNGU_NM", "MGMT_INST_NM", "MGMT_NM"):
        value = row.get(key)
        if value:
            return str(value).strip()
    return None


def get_drainpipe_measurements(region: str, start_time: str, end_time: str) -> list[dict[str, Any]]:
    payload = get_drainpipe_raw(region=region, start_time=start_time, end_time=end_time)

    rows: list[dict[str, Any]] = []
    for value in payload.values():
        if isinstance(value, dict) and isinstance(value.get("row"), list):
            rows = value["row"]
            break

    measurements: list[dict[str, Any]] = []
    for row in rows:
        gu = _pick_gu(row)
        tm = _pick_time(row)
        level = _pick_level(row)
        if not gu or not tm or level is None:
            continue
        measurements.append({"gu_name": gu, "time": tm, "level": level})

    measurements.sort(key=lambda item: (item["gu_name"], item["time"]))
    return measurements


def get_drainpipe_levels(region: str, start_time: str, end_time: str) -> list[dict[str, Any]]:
    payload = get_drainpipe_raw(region=region, start_time=start_time, end_time=end_time)

    rows: list[dict[str, Any]] = []
    for value in payload.values():
        if isinstance(value, dict) and isinstance(value.get("row"), list):
            rows = value["row"]
            break

    levels: list[dict[str, Any]] = []
    for row in rows:
        tm = _pick_time(row)
        level = _pick_level(row)
        if not tm or level is None:
            continue
        levels.append({"time": tm, "level": level})

    levels.sort(key=lambda item: item["time"])
    return levels
