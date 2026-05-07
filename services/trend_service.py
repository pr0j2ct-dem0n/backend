from typing import Any

from services.drainpipe_service import get_drainpipe_levels


def calculate_level_trend(levels: list[dict[str, Any]]) -> dict[str, Any]:
    if not levels:
        return {
            "start_level": 0.0,
            "current_level": 0.0,
            "change": 0.0,
            "change_rate": 0.0,
            "trend_status": "STABLE",
        }

    start_level = float(levels[0]["level"])
    current_level = float(levels[-1]["level"])
    change = current_level - start_level
    if start_level == 0:
        change_rate = 0.0
    else:
        change_rate = (change / start_level) * 100

    if change_rate >= 30:
        trend_status = "RISING_FAST"
    elif change_rate >= 10:
        trend_status = "RISING"
    elif change_rate <= -10:
        trend_status = "FALLING"
    else:
        trend_status = "STABLE"

    return {
        "start_level": round(start_level, 2),
        "current_level": round(current_level, 2),
        "change": round(change, 2),
        "change_rate": round(change_rate, 2),
        "trend_status": trend_status,
    }


def get_drainpipe_trend(region: str, start_time: str, end_time: str) -> dict[str, Any]:
    levels = get_drainpipe_levels(region=region, start_time=start_time, end_time=end_time)
    trend = calculate_level_trend(levels)
    return {
        "region": region,
        "start_time": start_time,
        "end_time": end_time,
        "trend": trend,
        "points": levels,
    }
