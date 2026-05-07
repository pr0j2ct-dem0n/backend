from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

try:
    import geopandas as gpd
except Exception:  # pragma: no cover
    gpd = None


class FloodHistoryDataError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


CSV_PATH = Path("data/flood_history.csv")
SHAPE_PATH = Path("data/flood/침수흔적도 최종2.shp")

GU_CODE_MAP = {
    "11110": "종로구",
    "11140": "중구",
    "11170": "용산구",
    "11200": "성동구",
    "11215": "광진구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11290": "성북구",
    "11305": "강북구",
    "11320": "도봉구",
    "11350": "노원구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11470": "양천구",
    "11500": "강서구",
    "11530": "구로구",
    "11545": "금천구",
    "11560": "영등포구",
    "11590": "동작구",
    "11620": "관악구",
    "11650": "서초구",
    "11680": "강남구",
    "11710": "송파구",
    "11740": "강동구",
}


def _normalize_gu_name(name: Any) -> str:
    gu = str(name).strip()
    if not gu.endswith("구"):
        gu = f"{gu}구"
    return gu


def _score_from_count(flood_count: int) -> int:
    if flood_count >= 5:
        return 20
    if flood_count >= 3:
        return 15
    if flood_count >= 1:
        return 10
    return 0


def _risk_from_score(score: int) -> float:
    # predict_service(0~100 스케일) 호환을 위해 함께 제공
    return round((score / 20.0) * 100.0, 2)


def _load_source_dataframe() -> pd.DataFrame:
    if CSV_PATH.exists():
        try:
            return pd.read_csv(CSV_PATH)
        except Exception as exc:
            raise FloodHistoryDataError(500, "CSV 읽기 실패", str(exc)) from exc

    if SHAPE_PATH.exists():
        if gpd is None:
            raise FloodHistoryDataError(
                500,
                "의존성 누락",
                "geopandas가 설치되어 있지 않습니다. requirements 설치가 필요합니다.",
            )
        try:
            gdf = gpd.read_file(SHAPE_PATH)
            return pd.DataFrame(gdf)
        except Exception as exc:
            raise FloodHistoryDataError(500, "Shapefile 읽기 실패", str(exc)) from exc

    raise FloodHistoryDataError(
        500,
        "데이터 파일 없음",
        f"{CSV_PATH} 또는 {SHAPE_PATH} 파일을 찾을 수 없습니다.",
    )


def _resolve_gu_name(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    if "gu_name" in df.columns:
        df["gu_name"] = df["gu_name"].astype(str).map(_normalize_gu_name)
        return df

    if "자치구" in df.columns:
        df["gu_name"] = df["자치구"].astype(str).map(_normalize_gu_name)
        return df

    if "자치구명" in df.columns:
        df["gu_name"] = df["자치구명"].astype(str).map(_normalize_gu_name)
        return df

    # shapefile에서 자주 쓰이는 구 컬럼들
    for col in ("GU_NM", "SIG_KOR_NM", "SGG_NM", "SIGNGU_NM", "F_ZONE_NM"):
        if col in df.columns:
            df["gu_name"] = df[col].astype(str).map(_normalize_gu_name)
            return df

    if "ADM_CD" in df.columns:
        adm = df["ADM_CD"].astype(str)
        # 1111012300 / 11110.0 / '11110-...' 등 혼재 대응: 처음 5자리 숫자 추출
        df["gu_code"] = adm.str.extract(r"(\d{5})", expand=False)
        df["gu_name"] = df["gu_code"].map(GU_CODE_MAP)
        return df

    raise FloodHistoryDataError(
        500,
        "자치구 컬럼 미확인",
        f"사용 가능한 컬럼: {list(df.columns)}",
    )


def load_flood_history() -> list[dict[str, Any]]:
    df = _load_source_dataframe()
    if df.empty:
        return []

    df = _resolve_gu_name(df)
    df = df.dropna(subset=["gu_name"])
    if df.empty:
        return []

    grouped = df.groupby("gu_name", as_index=False).size().rename(columns={"size": "flood_count"})

    result: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        flood_count = int(row["flood_count"])
        score = _score_from_count(flood_count)
        result.append(
            {
                "gu_name": str(row["gu_name"]),
                "flood_count": flood_count,
                "flood_history_score": score,
                "flood_history_risk": _risk_from_score(score),
                "has_flood_history": flood_count > 0,
            }
        )

    result.sort(key=lambda x: x["gu_name"])
    return result


def get_flood_history_score_by_gu(gu_name: str) -> dict[str, Any]:
    normalized = _normalize_gu_name(gu_name)
    for item in load_flood_history():
        if item["gu_name"] == normalized:
            return item
    return {
        "gu_name": normalized,
        "flood_count": 0,
        "flood_history_score": 0,
        "flood_history_risk": 0.0,
        "has_flood_history": False,
    }


def get_flood_history_risk_by_gu(gu_name: str) -> dict[str, Any] | None:
    # 기존 predict_service 호환
    item = get_flood_history_score_by_gu(gu_name)
    return item if item else None
