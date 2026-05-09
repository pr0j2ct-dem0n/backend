from collections import defaultdict
from datetime import datetime
from typing import Any

DEFAULT_PIPE_CAPACITY = 2.0
PIPE_CAPACITY: dict[str, float] = {
    "강남구": 2.0,
    "강서구": 1.8,
    "마포구": 1.5,
}


def get_max_capacity(gu_name: str) -> float:
    if gu_name in PIPE_CAPACITY:
        return PIPE_CAPACITY[gu_name]

    normalized = gu_name.strip()
    if normalized.endswith("구"):
        without_suffix = normalized[:-1]
        return PIPE_CAPACITY.get(without_suffix, DEFAULT_PIPE_CAPACITY)

    with_suffix = f"{normalized}구"
    return PIPE_CAPACITY.get(with_suffix, DEFAULT_PIPE_CAPACITY)


def calculate_pipe_ratio(current_level: float, max_capacity: float) -> float:
    if max_capacity <= 0:
        max_capacity = DEFAULT_PIPE_CAPACITY
    return round((current_level / max_capacity) * 100, 1)


def get_pipe_status(ratio: float) -> str:
    if ratio >= 80:
        return "DANGER"
    if ratio >= 60:
        return "WARNING"
    if ratio >= 40:
        return "CAUTION"
    return "NORMAL"


def _pick_gu(row: dict[str, Any]) -> str | None:
    for key in ("GU_NM", "GU_OFC_NM", "SGG_NM", "SIGNGU_NM", "MGMT_INST_NM", "MGMT_NM", "SE_NM"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _pick_level(row: dict[str, Any]) -> float | None:
    for key in (
        "PIPE_LEVEL",
        "WL",
        "LEVEL",
        "WATER_LEVEL",
        "CURR_LEVEL",
        "RLTM_WL",
        "SEWER_LEVEL",
        "MSRMT_WATL",
    ):
        value = row.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _pick_sensor_id(row: dict[str, Any]) -> str | None:
    for key in ("UNQ_NO", "SENSOR_ID", "ID", "NODE_ID"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _pick_measured_at(row: dict[str, Any]) -> datetime | None:
    value = row.get("MSRMT_YMD")
    if not value:
        return None
    text = str(value).strip().replace(".0", "")
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _valid_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        level = _pick_level(row)
        if level is None or level < 0:
            continue
        result.append(row)
    return result


def aggregate_sewer_pipe_by_gu(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_levels: dict[str, list[float]] = defaultdict(list)
    grouped_sensors: dict[str, set[str]] = defaultdict(set)

    for row in _valid_rows(rows):
        gu_name = _pick_gu(row)
        level = _pick_level(row)
        if not gu_name or level is None:
            continue
        grouped_levels[gu_name].append(level)
        sensor_id = _pick_sensor_id(row)
        if sensor_id:
            grouped_sensors[gu_name].add(sensor_id)

    result: list[dict[str, Any]] = []
    for gu_name, values in grouped_levels.items():
        if not values:
            continue
        pipe_level_avg = sum(values) / len(values)
        pipe_level_max = max(values)
        capacity = get_max_capacity(gu_name)
        occupancy_ratio = calculate_pipe_ratio(pipe_level_max, capacity)
        result.append(
            {
                "gu": gu_name,
                "pipe_level_avg": pipe_level_avg,
                "pipe_level_max": pipe_level_max,
                "occupancy_ratio": occupancy_ratio,
                "status": get_pipe_status(occupancy_ratio),
                "overflow_risk": occupancy_ratio >= 80,
                "station_count": len(grouped_sensors[gu_name]) if grouped_sensors[gu_name] else len(values),
            }
        )

    result.sort(key=lambda item: item["gu"])
    return result


def build_sewer_pipe_trend(rows: list[dict[str, Any]], bucket_minutes: int = 5) -> list[dict[str, Any]]:
    valid = _valid_rows(rows)
    if not valid:
        return []

    buckets: dict[datetime, list[float]] = defaultdict(list)
    for row in valid:
        measured_at = _pick_measured_at(row)
        level = _pick_level(row)
        if measured_at is None or level is None:
            continue
        minute = (measured_at.minute // bucket_minutes) * bucket_minutes
        bucket = measured_at.replace(minute=minute, second=0, microsecond=0)
        buckets[bucket].append(level)

    result: list[dict[str, Any]] = []
    for bucket_time, levels in sorted(buckets.items(), key=lambda item: item[0]):
        avg = sum(levels) / len(levels)
        result.append(
            {
                "time": bucket_time.strftime("%Y-%m-%d %H:%M:%S"),
                "avg_level": round(avg, 3),
            }
        )
    return result
