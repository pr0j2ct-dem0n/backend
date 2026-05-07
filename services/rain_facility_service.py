from __future__ import annotations

from typing import Any

import pandas as pd

from services.seoul_api_service import SeoulAPIError, fetch_raw_rainwater_facility


class RainFacilityDataError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


def clean_number(value: Any) -> float:
    if value is None:
        return 0.0

    text = str(value).replace(",", "").replace("-", "0").strip()
    if text == "":
        return 0.0

    try:
        return float(text)
    except ValueError:
        return 0.0


def get_rain_facility_raw(start: int = 1, end: int = 1000) -> dict[str, Any]:
    try:
        return fetch_raw_rainwater_facility(start=start, end=end)
    except SeoulAPIError as exc:
        raise RainFacilityDataError(exc.status_code, exc.error, exc.detail) from exc


def get_rain_facility_by_gu(start: int = 1, end: int = 1000) -> list[dict[str, Any]]:
    raw = get_rain_facility_raw(start=start, end=end)
    data = raw.get("TbUseRainwaterFacilityV", {})
    rows = data.get("row", []) if isinstance(data, dict) else []

    if not rows:
        return []

    df = pd.DataFrame(rows)
    df.columns = [str(col).strip() for col in df.columns]

    gu_col = None
    for candidate in ("SIGUNGU_NM", "CGG_NM", "GU_NM", "자치구", "자치구명"):
        if candidate in df.columns:
            gu_col = candidate
            break

    required_cols = ["WATER_AREA", "PRCS_CPCT", "FCLT_QY", "USE_QY"]
    missing = [col for col in required_cols if col not in df.columns]
    if not gu_col:
        missing = ["(자치구 컬럼: SIGUNGU_NM/CGG_NM/GU_NM/자치구/자치구명)"] + missing
    if missing:
        raise RainFacilityDataError(
            500,
            "필수 컬럼 누락",
            f"누락 컬럼: {missing}, 사용 가능한 컬럼: {list(df.columns)}",
        )

    df = df.rename(columns={gu_col: "gu_name"})
    df["gu_name"] = df["gu_name"].astype(str).str.strip()
    df = df[df["gu_name"].str.endswith("구", na=False)]

    for col in ["WATER_AREA", "PRCS_CPCT", "FCLT_QY", "USE_QY"]:
        df[col] = df[col].apply(clean_number)

    grouped = (
        df.groupby("gu_name", as_index=False)
        .agg(
            {
                "WATER_AREA": "sum",
                "PRCS_CPCT": "sum",
                "FCLT_QY": "sum",
                "USE_QY": "sum",
            }
        )
        .sort_values("gu_name")
    )

    grouped["remaining_capacity_m3"] = (grouped["FCLT_QY"] - grouped["USE_QY"]).clip(lower=0)
    grouped["effective_capacity_m3"] = grouped[["PRCS_CPCT", "FCLT_QY", "remaining_capacity_m3"]].max(axis=1)

    result: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        result.append(
            {
                "gu_name": row["gu_name"],
                "water_area_m2": round(float(row["WATER_AREA"]), 2),
                "prcs_cpct": round(float(row["PRCS_CPCT"]), 2),
                "fclt_qy": round(float(row["FCLT_QY"]), 2),
                "use_qy": round(float(row["USE_QY"]), 2),
                "remaining_capacity_m3": round(float(row["remaining_capacity_m3"]), 2),
                "effective_capacity_m3": round(float(row["effective_capacity_m3"]), 2),
            }
        )

    return result


def load_rain_facility(start: int = 1, end: int = 1000) -> list[dict[str, Any]]:
    # backward compatibility
    return get_rain_facility_by_gu(start=start, end=end)


def get_rain_facility_by_gu_name(gu_name: str, start: int = 1, end: int = 1000) -> dict[str, Any] | None:
    normalized = gu_name.strip()
    if not normalized.endswith("구"):
        normalized = f"{normalized}구"

    for item in get_rain_facility_by_gu(start=start, end=end):
        if item["gu_name"] == normalized:
            return item
    return None


def get_rain_facility_by_gu_summary(gu_name: str, start: int = 1, end: int = 1000) -> dict[str, Any] | None:
    return get_rain_facility_by_gu_name(gu_name=gu_name, start=start, end=end)
