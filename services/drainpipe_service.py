import os
from collections import defaultdict
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from services.seoul_api_service import SeoulAPIError, extract_rows, fetch_raw_sewer_pipe_level_in_range

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SeoulAPIError(500, "환경 변수 누락", f"{name} 값이 없습니다.")
    return value


def get_drainpipe_raw(region: str, start_time: str, end_time: str) -> dict[str, Any]:
    _require_env("SEOUL_API_URL")
    _require_env("SEOUL_API_KEY")
    return fetch_raw_sewer_pipe_level_in_range(region_code=region, start_time=start_time, end_time=end_time)


def _pick_time(row: dict[str, Any]) -> str | None:
    for key in ("MSRMT_YMD", "MESURE_DE", "MEASURE_TIME", "TM", "TIME", "DT"):
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
    rows = extract_rows(payload)

    measurements: list[dict[str, Any]] = []
    for row in rows:
        gu = _pick_gu(row)
        tm = _pick_time(row)
        level = _pick_level(row)
        if not gu or not tm or level is None or level < 0:
            continue
        measurements.append({"gu_name": gu, "time": tm, "level": level})

    measurements.sort(key=lambda item: (item["gu_name"], item["time"]))
    return measurements


def get_drainpipe_levels(region: str, start_time: str, end_time: str) -> list[dict[str, Any]]:
    payload = get_drainpipe_raw(region=region, start_time=start_time, end_time=end_time)
    rows = extract_rows(payload)

    levels: list[dict[str, Any]] = []
    for row in rows:
        tm = _pick_time(row)
        level = _pick_level(row)
        if not tm or level is None or level < 0:
            continue
        levels.append({"time": tm, "level": level})

    levels.sort(key=lambda item: item["time"])
    return levels


def _parse_time(value: str) -> datetime | None:
    text = value.strip().replace(".0", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def get_drainpipe_5m_avg_levels(region: str, start_time: str, end_time: str) -> list[dict[str, Any]]:
    levels = get_drainpipe_levels(region=region, start_time=start_time, end_time=end_time)
    buckets: dict[datetime, list[float]] = defaultdict(list)

    for item in levels:
        measured_at = _parse_time(str(item["time"]))
        if measured_at is None:
            continue
        minute = (measured_at.minute // 5) * 5
        bucket = measured_at.replace(minute=minute, second=0, microsecond=0)
        buckets[bucket].append(float(item["level"]))

    result: list[dict[str, Any]] = []
    for bucket, values in sorted(buckets.items(), key=lambda x: x[0]):
        result.append({"time": bucket.strftime("%Y-%m-%d %H:%M:%S"), "level": round(sum(values) / len(values), 3)})
    return result
