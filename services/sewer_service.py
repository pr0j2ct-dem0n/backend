from pathlib import Path
from typing import Any

import pandas as pd


class SewerDataError(Exception):
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
    if text == "":
        return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _load_dataframe() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise SewerDataError(500, "CSV 파일 없음", f"{CSV_PATH} 파일을 찾을 수 없습니다.")

    try:
        df = pd.read_csv(CSV_PATH, header=[1, 2])
    except Exception as exc:
        raise SewerDataError(500, "CSV 읽기 실패", str(exc)) from exc

    # 2단 헤더를 정규화: ('하수도 (m)', '암거') -> '암거'
    rename_map: dict[str, str] = {}
    for col in df.columns:
        if not isinstance(col, tuple):
            continue
        top = str(col[0]).strip()
        sub = str(col[1]).strip()
        if sub in ("암거", "개거", "관거", "U형측구"):
            rename_map[col] = sub
        elif top == "횡단하수거 (m)":
            rename_map[col] = "횡단하수거"
        elif top == "자치구별(2)" or sub == "자치구별(2)":
            rename_map[col] = "자치구별(2)"

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
        raise SewerDataError(500, "필수 컬럼 누락", f"필요 컬럼: {', '.join(REQUIRED_COLUMNS)} / 누락: {', '.join(missing)}")

    return df


def get_raw_columns() -> list[str]:
    df = _load_dataframe()
    return [str(col) for col in df.columns]


def list_sewer_by_gu() -> list[dict[str, Any]]:
    df = _load_dataframe().copy()

    for col in REQUIRED_COLUMNS[1:]:
        df[col] = df[col].apply(_to_float)

    grouped = (
        df.groupby("자치구별(2)", as_index=False)[REQUIRED_COLUMNS[1:]]
        .sum()
        .rename(columns={"자치구별(2)": "gu"})
    )

    result: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        gu_name = str(row["gu"]).strip()
        if gu_name in ("", "소계"):
            continue
        result.append(
            {
                "gu": gu_name,
                "underpass_length": row["암거"],
                "open_channel_length": row["개거"],
                "pipe_length": row["관거"],
                "u_ditch_length": row["U형측구"],
                "cross_sewer_length": row["횡단하수거"],
            }
        )

    result.sort(key=lambda item: item["gu"])
    return result


def get_sewer_summary_by_gu(gu_name: str) -> dict[str, Any] | None:
    items = list_sewer_by_gu()
    for item in items:
        if item["gu"] == gu_name:
            return item
    return None
