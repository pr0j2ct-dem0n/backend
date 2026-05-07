from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from constants.region_codes import REGION_CODE_TO_GU
from services.drainpipe_service import get_drainpipe_measurements
from services.flood_history_service import FloodHistoryDataError, get_flood_history_risk_by_gu
from services.integrated_service import get_integrated_data_by_gu
from services.rain_facility_service import RainFacilityDataError, load_rain_facility
from services.rainfall_service import aggregate_rainfall_by_gu
from services.river_service import aggregate_river_by_gu
from services.seoul_api_service import SeoulAPIError, extract_rows, fetch_raw_rainfall, fetch_raw_river_stage
from services.sewer_pipe_service import calculate_pipe_ratio, get_max_capacity


class PredictDataError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


def _clamp_0_100(value: float) -> float:
    return max(0.0, min(value, 100.0))


def _load_rainwater_stats() -> dict[str, dict[str, float]]:
    try:
        items = load_rain_facility(start=1, end=1000)
    except RainFacilityDataError:
        return {}

    result: dict[str, dict[str, float]] = {}
    for item in items:
        result[item["gu_name"]] = {
            "water_area_m2": float(item["water_area_m2"]),
            "effective_capacity_m3": float(item["effective_capacity_m3"]),
        }
    return result


def calculate_inflow(water_area_m2: float, rainfall_mm: float) -> float:
    return (water_area_m2 * rainfall_mm) / 1000


def calculate_effective_capacity(prcs_cpct: float, fclt_qy: float, use_qy: float) -> float:
    remaining_capacity = max(fclt_qy - use_qy, 0.0)
    return max(prcs_cpct + remaining_capacity, 0.0)


def calculate_danger_rainfall(effective_capacity_m3: float, water_area_m2: float) -> float:
    if water_area_m2 <= 0:
        return 0.0
    return ((effective_capacity_m3 * 0.8) / water_area_m2) * 1000


def calculate_rain_capacity_risk(current_rainfall_mm: float, danger_rainfall_mm: float) -> float:
    if danger_rainfall_mm <= 0:
        return 100.0
    score = (current_rainfall_mm / danger_rainfall_mm) * 100
    return _clamp_0_100(score)


def calculate_drainpipe_level_risk(occupancy_ratio: float) -> float:
    return _clamp_0_100(occupancy_ratio)


def calculate_river_level_risk(
    river_level: float,
    min_level: float | None = None,
    max_level: float | None = None,
) -> float:
    # 1) 구별 관측 분포가 있으면 min-max 정규화 우선
    if min_level is not None and max_level is not None and max_level > min_level:
        normalized = ((river_level - min_level) / (max_level - min_level)) * 100
        return _clamp_0_100(normalized)

    # 2) 분포가 없으면 임시 스케일링 fallback
    return _clamp_0_100(river_level * 20.0)


def calculate_flood_history_risk(flood_history_score: float) -> float:
    return _clamp_0_100(flood_history_score)


def calculate_sewer_structure_risk(gu_name: str) -> float:
    integrated = get_integrated_data_by_gu(gu_name)
    score = float(integrated["structural_risk"]["score"])
    return _clamp_0_100(score)


def normalize_gu_name(gu_name: str) -> str:
    name = gu_name.strip()
    if not name.endswith("구"):
        name = f"{name}구"
    return name


def calculate_final_risk_score(
    rain_capacity_risk: float,
    drainpipe_level_risk: float,
    river_level_risk: float,
    flood_history_risk: float,
    sewer_structure_risk: float,
) -> float:
    score = (
        (rain_capacity_risk * 0.35)
        + (drainpipe_level_risk * 0.25)
        + (river_level_risk * 0.15)
        + (flood_history_risk * 0.15)
        + (sewer_structure_risk * 0.10)
    )
    return _clamp_0_100(score)


def classify_risk_level(final_risk_score: float) -> str:
    if final_risk_score >= 85:
        return "CRITICAL"
    if final_risk_score >= 70:
        return "DANGER"
    if final_risk_score >= 40:
        return "CAUTION"
    return "SAFE"


def _get_default_area_capacity(gu_name: str) -> tuple[float, float]:
    try:
        sewer = get_integrated_data_by_gu(gu_name)
        capacity_total = float(sewer["sewer_capacity"].get("capacity_total", 0.0))
    except Exception:
        capacity_total = 100000.0

    water_area_m2 = max(capacity_total / 7.0, 10000.0)
    effective_capacity_m3 = max(capacity_total / 140.0, 1000.0)
    return water_area_m2, effective_capacity_m3


def _get_current_drainpipe_levels_all_gu(start_time: str, end_time: str) -> dict[str, float]:
    latest_by_gu: dict[str, dict[str, Any]] = {}
    for region_code in sorted(REGION_CODE_TO_GU.keys()):
        try:
            measurements = get_drainpipe_measurements(region=region_code, start_time=start_time, end_time=end_time)
        except SeoulAPIError:
            continue
        for item in measurements:
            gu_name = item["gu_name"]
            current = latest_by_gu.get(gu_name)
            if current is None or str(item["time"]) >= str(current["time"]):
                latest_by_gu[gu_name] = item

    return {gu_name: float(v["level"]) for gu_name, v in latest_by_gu.items()}


def _build_area_item(
    gu_name: str,
    rainfall_mm: float,
    river_by_gu: dict[str, float],
    river_min_level: float | None,
    river_max_level: float | None,
    rainwater_stats: dict[str, dict[str, float]],
    drainpipe_current_levels: dict[str, float],
) -> dict[str, Any]:
    rainwater = rainwater_stats.get(gu_name)
    used_rainwater_fallback = rainwater is None
    if rainwater:
        water_area_m2 = rainwater["water_area_m2"]
        effective_capacity_m3 = rainwater["effective_capacity_m3"]
    else:
        water_area_m2, effective_capacity_m3 = _get_default_area_capacity(gu_name)

    inflow_m3 = calculate_inflow(water_area_m2=water_area_m2, rainfall_mm=rainfall_mm)
    danger_rainfall_mm = calculate_danger_rainfall(
        effective_capacity_m3=effective_capacity_m3,
        water_area_m2=water_area_m2,
    )

    current_drainpipe_level = drainpipe_current_levels.get(gu_name, 0.0)
    has_drainpipe_measurement = gu_name in drainpipe_current_levels
    occupancy_ratio = calculate_pipe_ratio(current_drainpipe_level, get_max_capacity(gu_name))

    rain_capacity_risk = calculate_rain_capacity_risk(
        current_rainfall_mm=rainfall_mm,
        danger_rainfall_mm=danger_rainfall_mm,
    )
    drainpipe_level_risk = calculate_drainpipe_level_risk(occupancy_ratio=occupancy_ratio)
    river_level_raw = river_by_gu.get(gu_name, 0.0)
    river_level_risk = calculate_river_level_risk(
        river_level=river_level_raw,
        min_level=river_min_level,
        max_level=river_max_level,
    )
    try:
        flood_info = get_flood_history_risk_by_gu(gu_name)
        flood_history_error = None
    except FloodHistoryDataError:
        flood_info = None
        flood_history_error = "flood_history_service_error"
    flood_history_risk = calculate_flood_history_risk(
        flood_info["flood_history_risk"] if flood_info else 0.0
    )
    sewer_structure_risk = calculate_sewer_structure_risk(gu_name=gu_name)

    final_risk_score = calculate_final_risk_score(
        rain_capacity_risk=rain_capacity_risk,
        drainpipe_level_risk=drainpipe_level_risk,
        river_level_risk=river_level_risk,
        flood_history_risk=flood_history_risk,
        sewer_structure_risk=sewer_structure_risk,
    )

    reasons: list[str] = [
        f"현재 강우량이 위험 기준선의 {round(rain_capacity_risk, 1)}% 수준입니다.",
    ]

    if occupancy_ratio >= 80:
        reasons.append("하수관 점유율이 위험 구간입니다.")
    elif occupancy_ratio >= 60:
        reasons.append("하수관 점유율이 주의 구간입니다.")

    if flood_history_risk > 0:
        reasons.append("과거 침수흔적이 존재합니다.")

    return {
        "gu_name": gu_name,
        "scores": {
            "rain_capacity_risk": round(rain_capacity_risk, 2),
            "drainpipe_level_risk": round(drainpipe_level_risk, 2),
            "river_level_risk": round(river_level_risk, 2),
            "flood_history_risk": round(flood_history_risk, 2),
            "sewer_structure_risk": round(sewer_structure_risk, 2),
        },
        "final_risk_score": round(final_risk_score, 2),
        "risk_level": classify_risk_level(final_risk_score),
        "metrics": {
            "rainfall_mm": round(rainfall_mm, 2),
            "danger_rainfall_mm": round(danger_rainfall_mm, 2),
            "inflow_m3": round(inflow_m3, 2),
            "effective_capacity_m3": round(effective_capacity_m3, 2),
            "drainpipe_occupancy_ratio": round(occupancy_ratio, 2),
        },
        "flood_history": {
            "flood_count": int(flood_info["flood_count"]) if flood_info else 0,
        },
        "debug": {
            "rainwater_source": "rainwater_csv" if not used_rainwater_fallback else "sewer_capacity_fallback",
            "water_area_raw": round(water_area_m2, 4),
            "effective_capacity_raw": round(effective_capacity_m3, 4),
            "danger_rainfall_formula": "((effective_capacity * 0.8) / water_area) * 1000",
            "rainfall_raw_mm": round(rainfall_mm, 4),
            "drainpipe_level_raw": round(current_drainpipe_level, 4),
            "has_drainpipe_measurement": has_drainpipe_measurement,
            "occupancy_ratio_raw": round(occupancy_ratio, 4),
            "river_level_raw": round(river_level_raw, 4),
            "river_min_level": round(river_min_level, 4) if river_min_level is not None else None,
            "river_max_level": round(river_max_level, 4) if river_max_level is not None else None,
            "river_risk_mode": "min_max_normalized"
            if river_min_level is not None and river_max_level is not None and river_max_level > river_min_level
            else "scaled_fallback",
            "flood_count_raw": int(flood_info["flood_count"]) if flood_info else 0,
            "flood_history_service_error": flood_history_error,
        },
        "reasons": reasons,
    }


def predict_flood_areas(start_time: str, end_time: str) -> dict[str, Any]:
    try:
        rainfall_payload = fetch_raw_rainfall()
        rainfall_rows = extract_rows(rainfall_payload)
        rainfall_by_gu = {item["gu"]: float(item["rainfall_max_10min"]) for item in aggregate_rainfall_by_gu(rainfall_rows)}
    except SeoulAPIError as exc:
        raise PredictDataError(exc.status_code, exc.error, exc.detail) from exc

    try:
        river_payload = fetch_raw_river_stage()
        river_rows = extract_rows(river_payload)
        river_by_gu = {item["gu"]: float(item["river_level_avg"]) for item in aggregate_river_by_gu(river_rows)}
    except SeoulAPIError:
        river_by_gu = {}
    river_values = list(river_by_gu.values())
    river_min_level = min(river_values) if river_values else None
    river_max_level = max(river_values) if river_values else None

    rainwater_stats = _load_rainwater_stats()
    drainpipe_current_levels = _get_current_drainpipe_levels_all_gu(start_time=start_time, end_time=end_time)

    if not rainfall_by_gu:
        raise PredictDataError(404, "데이터 없음", "강우량 데이터가 없습니다.")

    areas: list[dict[str, Any]] = []
    for gu_name, rainfall_mm in rainfall_by_gu.items():
        area_item = _build_area_item(
            gu_name=gu_name,
            rainfall_mm=rainfall_mm,
            river_by_gu=river_by_gu,
            river_min_level=river_min_level,
            river_max_level=river_max_level,
            rainwater_stats=rainwater_stats,
            drainpipe_current_levels=drainpipe_current_levels,
        )
        areas.append(area_item)

    areas.sort(key=lambda x: x["final_risk_score"], reverse=True)

    kst = timezone(timedelta(hours=9))
    base_time = datetime.now(kst).strftime("%Y-%m-%d %H:%M")
    return {"base_time": base_time, "areas": areas}


def predict_flood_area_by_gu(gu_name: str, start_time: str, end_time: str) -> dict[str, Any]:
    normalized_gu = normalize_gu_name(gu_name)

    try:
        rainfall_payload = fetch_raw_rainfall()
        rainfall_rows = extract_rows(rainfall_payload)
        rainfall_by_gu = {item["gu"]: float(item["rainfall_max_10min"]) for item in aggregate_rainfall_by_gu(rainfall_rows)}
    except SeoulAPIError as exc:
        raise PredictDataError(exc.status_code, exc.error, exc.detail) from exc

    if normalized_gu not in rainfall_by_gu:
        raise PredictDataError(404, "데이터 없음", f"{normalized_gu} 강우량 데이터가 없습니다.")

    try:
        river_payload = fetch_raw_river_stage()
        river_rows = extract_rows(river_payload)
        river_by_gu = {item["gu"]: float(item["river_level_avg"]) for item in aggregate_river_by_gu(river_rows)}
    except SeoulAPIError:
        river_by_gu = {}
    river_values = list(river_by_gu.values())
    river_min_level = min(river_values) if river_values else None
    river_max_level = max(river_values) if river_values else None

    rainwater_stats = _load_rainwater_stats()
    drainpipe_current_levels = _get_current_drainpipe_levels_all_gu(start_time=start_time, end_time=end_time)

    return _build_area_item(
        gu_name=normalized_gu,
        rainfall_mm=rainfall_by_gu[normalized_gu],
        river_by_gu=river_by_gu,
        river_min_level=river_min_level,
        river_max_level=river_max_level,
        rainwater_stats=rainwater_stats,
        drainpipe_current_levels=drainpipe_current_levels,
    )
