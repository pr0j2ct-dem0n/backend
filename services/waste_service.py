from pathlib import Path
from typing import Any

import pandas as pd


class WasteDataError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


CSV_PATH = Path("data/waste_generation.csv")
REQUIRED_COLUMNS = ["자치구", "발생량"]


def _to_float(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).replace(",", "").strip()
    if text == "":
        return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _load_dataframe() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise WasteDataError(500, "CSV 파일 없음", f"{CSV_PATH} 파일을 찾을 수 없습니다.")

    try:
        df = pd.read_csv(CSV_PATH, header=[1, 2])
    except Exception as exc:
        raise WasteDataError(500, "CSV 읽기 실패", str(exc)) from exc

    rename_map: dict[Any, str] = {}
    for col in df.columns:
        if not isinstance(col, tuple):
            continue
        top = str(col[0]).strip()
        sub = str(col[1]).strip()
        if top == "구분별(2)" or sub == "구분별(2)":
            rename_map[col] = "자치구"
        elif top == "발생량" and sub == "소계":
            rename_map[col] = "발생량"

    normalized_columns: list[str] = []
    for col in df.columns:
        if col in rename_map:
            normalized_columns.append(rename_map[col])
        elif isinstance(col, tuple):
            normalized_columns.append(f"{col[0]}_{col[1]}")
        else:
            normalized_columns.append(str(col).strip())
    df.columns = normalized_columns

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise WasteDataError(
            500,
            "필수 컬럼 누락",
            f"필요 컬럼: {', '.join(REQUIRED_COLUMNS)} / 누락: {', '.join(missing)}",
        )

    return df


def get_raw_columns() -> list[str]:
    df = _load_dataframe()
    return [str(col) for col in df.columns]


def list_waste_by_gu() -> list[dict[str, Any]]:
    df = _load_dataframe().copy()
    df["발생량"] = df["발생량"].apply(_to_float)
    df["자치구"] = df["자치구"].astype(str).str.strip()

    # 표 상단의 소계/처리비율/헤더 반복 행 제거
    df = df[df["자치구"].str.endswith("구", na=False)]

    grouped = df.groupby("자치구", as_index=False)["발생량"].sum()
    grouped = grouped.rename(columns={"자치구": "gu", "발생량": "waste_generation"})

    result = grouped.to_dict(orient="records")
    result.sort(key=lambda item: item["gu"])
    return result


def get_waste_summary_by_gu(gu_name: str) -> dict[str, Any] | None:
    items = list_waste_by_gu()
    for item in items:
        if item["gu"] == gu_name:
            return item
    return None
