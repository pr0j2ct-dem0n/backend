from collections import defaultdict
from typing import Any


def aggregate_rainfall_by_gu(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        gu_name = row.get("GU_NM")
        rain_value = row.get("RN_10M")
        if not gu_name:
            continue
        try:
            grouped[str(gu_name)].append(float(rain_value))
        except (TypeError, ValueError):
            continue

    result: list[dict[str, Any]] = []
    for gu_name, values in grouped.items():
        if not values:
            continue
        result.append(
            {
                "gu": gu_name,
                "rainfall_avg_10min": sum(values) / len(values),
                "rainfall_max_10min": max(values),
                "station_count": len(values),
            }
        )
    result.sort(key=lambda item: item["gu"])
    return result
