from collections import defaultdict
from datetime import datetime
import json
import os
import time
from threading import RLock
from typing import Any

from dotenv import load_dotenv

from services.public_sewer_treatment_service import get_infra_by_gu_index, normalize_gu
from services.seoul_api_service import SeoulAPIError, fetch_raw_rain_pump_xml, fetch_raw_ts_rainfall_xml

load_dotenv()

DEFAULT_PIPE_CAPACITY = 2.0
WATER_RISK_WEIGHT = float(os.getenv("WATER_RISK_WEIGHT", "0.5"))
RAIN_RISK_WEIGHT = float(os.getenv("RAIN_RISK_WEIGHT", "0.2"))
INFRA_SCORE_WEIGHT = float(os.getenv("INFRA_SCORE_WEIGHT", "0.15"))
PUMP_SCORE_WEIGHT = float(os.getenv("PUMP_SCORE_WEIGHT", "0.15"))
RAIN_RISK_NORMALIZER_MM = float(os.getenv("RAIN_RISK_NORMALIZER_MM", "50"))
RAIN_CACHE_TTL = int(os.getenv("RAIN_CACHE_TTL_SEC", "60"))
PUMP_CACHE_TTL = int(os.getenv("PUMP_CACHE_TTL_SEC", "86400"))
DEFAULT_GU_POPULATION = float(os.getenv("DEFAULT_GU_POPULATION", "300000"))
GU_POPULATION_JSON = os.getenv("GU_POPULATION_JSON", "{}")

_RAIN_CACHE_LOCK = RLock()
_RAIN_BY_GU_CACHE: tuple[float, dict[str, float]] | None = None
_PUMP_CACHE_LOCK = RLock()
_PUMP_BY_GU_CACHE: tuple[float, dict[str, dict[str, float]]] | None = None

PIPE_CAPACITY: dict[str, float] = {
    "강남구": 2.0,
    "강서구": 1.8,
    "마포구": 1.5,
}

try:
    _POP_RAW = json.loads(GU_POPULATION_JSON)
except json.JSONDecodeError:
    _POP_RAW = {}
GU_POPULATION_MAP: dict[str, float] = {
    normalize_gu(str(key)): float(value)
    for key, value in _POP_RAW.items()
    if isinstance(value, (int, float, str))
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


def clamp(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    return max(min_value, min(max_value, value))


def calculate_water_risk(pipe_level_max: float) -> float:
    return round(clamp((pipe_level_max / DEFAULT_PIPE_CAPACITY) * 100), 1)


def _build_infra_index() -> dict[str, dict[str, float]]:
    return get_infra_by_gu_index()


def _normalize_gu_key(value: str) -> str:
    return normalize_gu(value)


def _pick_rainfall_value(row: dict[str, Any]) -> float | None:
    for key in ("RN_1HR", "RN_60M", "RN_30M", "RN_15M", "RN_10M", "RAINFALL", "RAINFALL_MM", "PRECIPITATION"):
        raw = row.get(key)
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _pick_rain_gu(row: dict[str, Any]) -> str | None:
    for key in ("GU_NM", "SIGUNGU_NM", "SGG_NM", "GU", "ADDR", "ADDRESS"):
        value = row.get(key)
        if value:
            text = str(value).strip()
            if key in ("ADDR", "ADDRESS"):
                for token in text.replace(",", " ").split():
                    if token.endswith("구"):
                        return token
            return text
    return None


def _build_rainfall_by_gu_index() -> dict[str, float]:
    global _RAIN_BY_GU_CACHE
    now = time.monotonic()
    with _RAIN_CACHE_LOCK:
        if _RAIN_BY_GU_CACHE and _RAIN_BY_GU_CACHE[0] > now:
            return _RAIN_BY_GU_CACHE[1]

    index: dict[str, list[float]] = defaultdict(list)
    try:
        rows = fetch_raw_ts_rainfall_xml(start=1, end=200)
        for row in rows:
            gu_name = _pick_rain_gu(row)
            rainfall = _pick_rainfall_value(row)
            if not gu_name or rainfall is None or rainfall < 0:
                continue
            index[_normalize_gu_key(gu_name)].append(rainfall)
    except SeoulAPIError:
        index = defaultdict(list)

    rain_by_gu = {
        gu: (sum(values) / len(values))
        for gu, values in index.items()
        if values
    }
    with _RAIN_CACHE_LOCK:
        _RAIN_BY_GU_CACHE = (time.monotonic() + RAIN_CACHE_TTL, rain_by_gu)
    return rain_by_gu


def calculate_rain_risk(rainfall: float) -> float:
    if RAIN_RISK_NORMALIZER_MM <= 0:
        return 0.0
    return round(clamp((rainfall / RAIN_RISK_NORMALIZER_MM) * 100), 1)


def _to_float(value: Any) -> float | None:
    try:
        text = str(value).replace(",", "").strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _pick_pump_gu(row: dict[str, Any]) -> str | None:
    for key in ("GU_NM", "SIGUNGU_NM", "SGG_NM", "BASIN_GU", "ADDR", "ADDRESS"):
        value = row.get(key)
        if value:
            text = str(value).strip()
            if key in ("ADDR", "ADDRESS"):
                for token in text.replace(",", " ").split():
                    if token.endswith("구"):
                        return token
            return text
    return None


def _pick_pump_capacity(row: dict[str, Any]) -> float | None:
    for key in (
        "PUMP_CAPACITY",
        "DRN_CPCTY",
        "TOT_CPCTY",
        "FACILITY_CAPACITY",
        "CAPACITY",
        "QTY",
    ):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None


def _pick_pump_name(row: dict[str, Any]) -> str | None:
    for key in ("PUMP_NM", "PUMP_NAME", "FCLT_NM", "NAME"):
        value = row.get(key)
        if value:
            return str(value).strip()
    return None


def _build_pump_by_gu_index() -> dict[str, dict[str, float]]:
    global _PUMP_BY_GU_CACHE
    now = time.monotonic()
    with _PUMP_CACHE_LOCK:
        if _PUMP_BY_GU_CACHE and _PUMP_BY_GU_CACHE[0] > now:
            return _PUMP_BY_GU_CACHE[1]

    grouped_capacity: dict[str, float] = defaultdict(float)
    grouped_count: dict[str, set[str]] = defaultdict(set)

    try:
        rows = fetch_raw_rain_pump_xml(start=1, end=1000)
        for row in rows:
            gu_name = _pick_pump_gu(row)
            if not gu_name:
                continue
            gu_key = _normalize_gu_key(gu_name)
            pump_name = _pick_pump_name(row) or f"pump-{len(grouped_count[gu_key]) + 1}"
            grouped_count[gu_key].add(pump_name)
            capacity = _pick_pump_capacity(row)
            if capacity is not None and capacity > 0:
                grouped_capacity[gu_key] += capacity
    except SeoulAPIError:
        pass

    pump_by_gu: dict[str, dict[str, float]] = {}
    all_keys = set(grouped_count.keys()) | set(grouped_capacity.keys())
    for gu_key in all_keys:
        pump_by_gu[gu_key] = {
            "pump_count": float(len(grouped_count.get(gu_key, set()))),
            "pump_capacity": float(grouped_capacity.get(gu_key, 0.0)),
        }

    with _PUMP_CACHE_LOCK:
        _PUMP_BY_GU_CACHE = (time.monotonic() + PUMP_CACHE_TTL, pump_by_gu)
    return pump_by_gu


def _get_population_by_gu(gu_name: str) -> float:
    return float(GU_POPULATION_MAP.get(_normalize_gu_key(gu_name), DEFAULT_GU_POPULATION))


def calculate_pump_score(pump_capacity: float, population: float) -> float:
    if population <= 0:
        return 0.0
    return round(clamp((pump_capacity / population) * 100), 1)


def calculate_total_risk_v2(water_risk: float, rain_risk: float, infra_score: float, pump_score: float) -> float:
    return round(
        clamp(
            (WATER_RISK_WEIGHT * water_risk)
            + (RAIN_RISK_WEIGHT * rain_risk)
            - (INFRA_SCORE_WEIGHT * infra_score)
            - (PUMP_SCORE_WEIGHT * pump_score)
        ),
        1,
    )


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
    infra_index = _build_infra_index()
    rain_by_gu = _build_rainfall_by_gu_index()
    pump_by_gu = _build_pump_by_gu_index()

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
        water_risk = calculate_water_risk(pipe_level_max)
        rainfall = round(float(rain_by_gu.get(_normalize_gu_key(gu_name), 0.0)), 2)
        rain_risk = calculate_rain_risk(rainfall)
        infra = infra_index.get(normalize_gu(gu_name), {})
        infra_score = float(infra.get("infra_score", 0.0))
        pump = pump_by_gu.get(_normalize_gu_key(gu_name), {})
        pump_count = int(pump.get("pump_count", 0.0))
        pump_capacity = round(float(pump.get("pump_capacity", 0.0)), 2)
        population = _get_population_by_gu(gu_name)
        pump_score = calculate_pump_score(pump_capacity=pump_capacity, population=population)
        total_risk = calculate_total_risk_v2(
            water_risk=water_risk,
            rain_risk=rain_risk,
            infra_score=infra_score,
            pump_score=pump_score,
        )
        result.append(
            {
                "gu": gu_name,
                "pipe_level_avg": pipe_level_avg,
                "pipe_level_max": pipe_level_max,
                "occupancy_ratio": occupancy_ratio,
                "water_risk": water_risk,
                "rainfall": rainfall,
                "rain_risk": rain_risk,
                "infra_score": infra_score,
                "pump_score": pump_score,
                "total_risk": total_risk,
                "status": get_pipe_status(total_risk),
                "overflow_risk": occupancy_ratio >= 80,
                "station_count": len(grouped_sensors[gu_name]) if grouped_sensors[gu_name] else len(values),
                "pump_count": pump_count,
                "pump_capacity": pump_capacity,
                "facility_count": int(infra.get("facility_count", 0.0)),
                "facility_capacity": round(float(infra.get("facility_capacity", 0.0)), 2),
                "inflow_amount": round(float(infra.get("inflow_amount", 0.0)), 2),
                "discharge_amount": round(float(infra.get("discharge_amount", 0.0)), 2),
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
