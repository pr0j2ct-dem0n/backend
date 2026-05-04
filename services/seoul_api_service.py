import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class SeoulAPIError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SeoulAPIError(500, "환경 변수 누락", f"{name} 값이 없습니다.")
    return value


def fetch_raw_rainfall(start: int = 1, end: int = 100) -> dict[str, Any]:
    if start < 1 or end < 1 or start > end:
        raise SeoulAPIError(400, "잘못된 범위", "start/end 값을 확인하세요.")

    base_url = _require_env("SEOUL_API_URL")
    api_key = _require_env("SEOUL_API_KEY")
    url = f"{base_url}/{api_key}/SeoulRtdFndRgnQly/{start}/{end}/"

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        raise SeoulAPIError(502, "서울시 API 요청 실패", str(exc)) from exc

    if response.status_code != 200:
        raise SeoulAPIError(response.status_code, "서울시 API 응답 오류")

    try:
        return response.json()
    except ValueError as exc:
        preview = response.text[:200] if response.text else ""
        raise SeoulAPIError(502, "JSON 변환 실패", preview) from exc


def extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data_obj: dict[str, Any] | None = None

    if "SeoulRtdFndRgnQly" in payload and isinstance(payload["SeoulRtdFndRgnQly"], dict):
        data_obj = payload["SeoulRtdFndRgnQly"]
    else:
        for value in payload.values():
            if isinstance(value, dict) and isinstance(value.get("row"), list):
                data_obj = value
                break

    if not data_obj:
        return []

    rows = data_obj.get("row", [])
    return rows if isinstance(rows, list) else []
