from collections import defaultdict
from typing import Any


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
        result.append(
            {
                "gu": gu_name,
                "pipe_level_avg": sum(values) / len(values),
                "pipe_level_max": max(values),
                "station_count": len(values),
            }
        )

    result.sort(key=lambda item: item["gu"])
    return result
