from collections import defaultdict
from typing import Any


def aggregate_river_by_gu(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        gu_name = row.get("GU_OFC_NM")
        level = row.get("RLTM_RVR_WATL_CNT")
        if not gu_name:
            continue
        try:
            grouped[str(gu_name)].append(float(level))
        except (TypeError, ValueError):
            continue

    result: list[dict[str, Any]] = []
    for gu_name, values in grouped.items():
        if not values:
            continue
        result.append(
            {
                "gu": gu_name,
                "river_level_avg": sum(values) / len(values),
                "river_level_max": max(values),
                "station_count": len(values),
            }
        )
    result.sort(key=lambda item: item["gu"])
    return result
