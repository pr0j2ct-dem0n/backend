from pathlib import Path
from typing import Any

import pandas as pd


class SewerFacilityDataError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


CSV_PATH = Path("data/sewer_facility.csv")
REQUIRED_COLUMNS = ["자치구별(2)", "암거", "개거", "관거", "U형측구", "횡단하수거"]


def _to_float(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).replace(",", "").strip()
    if text in ("", "-"):
        return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _load_dataframe() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise SewerFacilityDataError(500, "CSV 파일 없음", f"{CSV_PATH} 파일을 찾을 수 없습니다.")

    try:
        df = pd.read_csv(CSV_PATH, header=[1, 2])
    except Exception as exc:
        raise SewerFacilityDataError(500, "CSV 읽기 실패", str(exc)) from exc

    rename_map: dict[Any, str] = {}
    for col in df.columns:
        if not isinstance(col, tuple):
            continue
        top = str(col[0]).strip()
        sub = str(col[1]).strip()
        if top == "자치구별(2)" or sub == "자치구별(2)":
            rename_map[col] = "자치구별(2)"
        elif sub in ("암거", "개거", "관거", "U형측구"):
            rename_map[col] = sub
        elif top == "횡단하수거 (m)":
            rename_map[col] = "횡단하수거"

    normalized_columns: list[str] = []
    for col in df.columns:
        if col in rename_map:
            normalized_columns.append(rename_map[col])
        elif isinstance(col, tuple):
            normalized_columns.append(str(col[1]).strip())
        else:
            normalized_columns.append(str(col).strip())
    df.columns = normalized_columns

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise SewerFacilityDataError(
            500,
            "필수 컬럼 누락",
            f"필요 컬럼: {', '.join(REQUIRED_COLUMNS)} / 누락: {', '.join(missing)}",
        )

    return df


def load_sewer_facility() -> list[dict[str, Any]]:
    df = _load_dataframe().copy()
    for col in REQUIRED_COLUMNS[1:]:
        df[col] = df[col].apply(_to_float)

    df["자치구별(2)"] = df["자치구별(2)"].astype(str).str.strip()
    df = df[df["자치구별(2)"].str.endswith("구", na=False)]

    grouped = df.groupby("자치구별(2)", as_index=False)[REQUIRED_COLUMNS[1:]].sum()
    grouped["capacity_total"] = grouped[REQUIRED_COLUMNS[1:]].sum(axis=1)

    component_max = {
        "암거": float(grouped["암거"].max()) if not grouped.empty else 0.0,
        "개거": float(grouped["개거"].max()) if not grouped.empty else 0.0,
        "관거": float(grouped["관거"].max()) if not grouped.empty else 0.0,
        "U형측구": float(grouped["U형측구"].max()) if not grouped.empty else 0.0,
        "횡단하수거": float(grouped["횡단하수거"].max()) if not grouped.empty else 0.0,
    }

    result: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        components = {
            "암거": float(row["암거"]),
            "개거": float(row["개거"]),
            "관거": float(row["관거"]),
            "U형측구": float(row["U형측구"]),
            "횡단하수거": float(row["횡단하수거"]),
        }
        component_scores: dict[str, float] = {}
        for name, value in components.items():
            max_value = component_max[name]
            component_scores[name] = round((value / max_value) * 100, 2) if max_value > 0 else 0.0
        capacity_score = round(sum(component_scores.values()) / len(component_scores), 2) if component_scores else 0.0

        result.append(
            {
                "gu_name": row["자치구별(2)"],
                "capacity_total": float(row["capacity_total"]),
                "capacity_score": capacity_score,
                "components": components,
                "component_scores": component_scores,
            }
        )

    result.sort(key=lambda item: item["gu_name"])
    return result


def get_sewer_capacity_by_gu(gu_name: str) -> dict[str, Any] | None:
    for item in load_sewer_facility():
        if item["gu_name"] == gu_name:
            return item
    return None
