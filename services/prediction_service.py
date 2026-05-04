from collections import defaultdict
from typing import Any


def clamp_score(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    return max(min_value, min(max_value, value))


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


def _to_status(score: float) -> str:
    if score < 40:
        return "NORMAL"
    if score < 70:
        return "WARNING"
    return "CRITICAL"


def _to_message(gu_name: str, status: str) -> str:
    if status == "CRITICAL":
        return f"{gu_name} 하수도 용량 초과 위험"
    if status == "WARNING":
        return f"{gu_name} 하수도 수위 상승 주의"
    return f"{gu_name} 하수도 상태 정상"


def predict_risk(gu_stat: dict[str, Any]) -> dict[str, Any]:
    rainfall_avg_10min = float(gu_stat["rainfall_avg_10min"])
    rainfall_max_10min = float(gu_stat["rainfall_max_10min"])
    station_count = int(gu_stat["station_count"])

    risk_score_raw = rainfall_avg_10min * 12 + rainfall_max_10min * 18
    risk_score = clamp_score(risk_score_raw)

    predicted_load_raw = risk_score + station_count * 0.5
    predicted_load = clamp_score(predicted_load_raw)

    status = _to_status(risk_score)
    gu_name = str(gu_stat["gu"])

    return {
        "gu": gu_name,
        "risk_score": risk_score,
        "predicted_load": predicted_load,
        "status": status,
        "rainfall_avg_10min": rainfall_avg_10min,
        "rainfall_max_10min": rainfall_max_10min,
        "message": _to_message(gu_name, status),
    }
