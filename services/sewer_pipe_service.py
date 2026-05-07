from collections import defaultdict
from typing import Any

DEFAULT_PIPE_CAPACITY = 2.0
PIPE_CAPACITY: dict[str, float] = {
    "강남구": 2.0,
    "강서구": 1.8,
    "마포구": 1.5,
}


def get_max_capacity(gu_name: str) -> float:
    return PIPE_CAPACITY.get(gu_name, DEFAULT_PIPE_CAPACITY)


def calculate_pipe_ratio(current_level: float, max_capacity: float) -> float:
    if max_capacity <= 0:
        max_capacity = DEFAULT_PIPE_CAPACITY
    return round((current_level / max_capacity) * 100, 1)


def get_pipe_status(ratio: float) -> str:
    if ratio >= 80:
        return "CRITICAL"
    if ratio >= 60:
        return "WARNING"
    return "NORMAL"


def _pick_gu(row: dict[str, Any]) -> str | None:
    for key in ("GU_NM", "GU_OFC_NM", "SGG_NM", "SIGNGU_NM", "MGMT_INST_NM", "MGMT_NM"):
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


def aggregate_sewer_pipe_by_gu(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        gu_name = _pick_gu(row)
        level = _pick_level(row)
        if not gu_name or level is None:
            continue
        grouped[gu_name].append(level)

    result: list[dict[str, Any]] = []
    for gu_name, values in grouped.items():
        if not values:
            continue
        pipe_level_max = max(values)
        capacity = get_max_capacity(gu_name)
        occupancy_ratio = calculate_pipe_ratio(pipe_level_max, capacity)
        result.append(
            {
                "gu": gu_name,
                "pipe_level_avg": sum(values) / len(values),
                "pipe_level_max": pipe_level_max,
                "occupancy_ratio": occupancy_ratio,
                "status": get_pipe_status(occupancy_ratio),
                "overflow_risk": occupancy_ratio > 100,
                "station_count": len(values),
            }
        )

    result.sort(key=lambda item: item["gu"])
    return result
