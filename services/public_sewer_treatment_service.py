import os
import time
from threading import RLock
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

DATASET_PATH = "/3073222/v1/uddi:dacf5c58-5dd0-4bd1-8cf0-923d27aaf9d2"
INFRA_CACHE_TTL = int(os.getenv("INFRA_CACHE_TTL_SEC", "86400"))
DATA_API_TIMEOUT_SECONDS = float(os.getenv("DATA_API_TIMEOUT_SEC", "8"))

_CACHE_LOCK = RLock()
_INFRA_CACHE: tuple[float, dict[str, dict[str, float]]] | None = None


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} 값이 없습니다.")
    return value


def normalize_gu(name: str) -> str:
    text = str(name).strip()
    text = text.replace("서울특별시", "").replace("서울시", "").replace(" ", "")
    if text.endswith("구"):
        text = text[:-1]
    return text.strip()


def _to_float_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("-", "0", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _fetch_raw_items() -> list[dict[str, Any]]:
    base_url = _require_env("DATA_API_URL").rstrip("/")
    api_key = _require_env("DATA_API_KEY")
    url = f"{base_url}{DATASET_PATH}"
    params = {
        "page": 1,
        "perPage": 1000,
        "returnType": "JSON",
        "serviceKey": api_key,
    }
    response = requests.get(url, params=params, timeout=DATA_API_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def _build_index(items: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    if not items:
        return {}

    df = pd.DataFrame(items)
    sido_col = _pick_column(df, ["시도", "시도명"])
    gu_col = _pick_column(df, ["구군", "구군명", "행정구역명"])
    facility_name_col = _pick_column(df, ["시설명", "공공하수처리시설명"])
    capacity_col = _pick_column(df, ["시설용량", "시설용량(㎥/일)", "시설용량(톤/일)"])
    inflow_col = _pick_column(df, ["유입하수량", "유입하수량(㎥/일)", "유입량"])
    discharge_col = _pick_column(df, ["방류량", "방류량(㎥/일)"])

    if not sido_col or not gu_col:
        return {}

    seoul_df = df[df[sido_col].astype(str).str.contains("서울", na=False)].copy()
    if seoul_df.empty:
        return {}

    seoul_df["gu_norm"] = seoul_df[gu_col].apply(normalize_gu)
    if facility_name_col:
        seoul_df["facility_name"] = seoul_df[facility_name_col].astype(str)
    else:
        seoul_df["facility_name"] = "UNKNOWN"

    if capacity_col:
        seoul_df["facility_capacity"] = _to_float_series(seoul_df[capacity_col])
    else:
        seoul_df["facility_capacity"] = 0.0
    if inflow_col:
        seoul_df["inflow_amount"] = _to_float_series(seoul_df[inflow_col])
    else:
        seoul_df["inflow_amount"] = 0.0
    if discharge_col:
        seoul_df["discharge_amount"] = _to_float_series(seoul_df[discharge_col])
    else:
        seoul_df["discharge_amount"] = 0.0

    grouped = (
        seoul_df.groupby("gu_norm", as_index=False)
        .agg(
            facility_count=("facility_name", "count"),
            facility_capacity=("facility_capacity", "sum"),
            inflow_amount=("inflow_amount", "sum"),
            discharge_amount=("discharge_amount", "sum"),
        )
        .reset_index(drop=True)
    )

    index: dict[str, dict[str, float]] = {}
    for _, row in grouped.iterrows():
        gu_norm = str(row["gu_norm"]).strip()
        capacity = float(row["facility_capacity"])
        inflow = float(row["inflow_amount"])
        discharge = float(row["discharge_amount"])
        margin_ratio = ((capacity - inflow) / capacity) if capacity > 0 else 0.0
        infra_score = max(0.0, min(margin_ratio * 100.0, 100.0))
        index[gu_norm] = {
            "facility_count": float(row["facility_count"]),
            "facility_capacity": capacity,
            "inflow_amount": inflow,
            "discharge_amount": discharge,
            "infra_score": infra_score,
        }
    return index


def get_infra_by_gu_index() -> dict[str, dict[str, float]]:
    global _INFRA_CACHE
    now = time.monotonic()
    with _CACHE_LOCK:
        if _INFRA_CACHE and _INFRA_CACHE[0] > now:
            return _INFRA_CACHE[1]

    try:
        items = _fetch_raw_items()
        index = _build_index(items)
    except Exception:
        index = {}

    with _CACHE_LOCK:
        _INFRA_CACHE = (time.monotonic() + INFRA_CACHE_TTL, index)
    return index
