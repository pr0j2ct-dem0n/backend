from typing import Any

from services.sewer_facility_service import SewerFacilityDataError, get_sewer_capacity_by_gu


class IntegratedDataError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(error)


def calculate_structural_risk(component_scores: dict[str, float]) -> dict[str, Any]:
    component_values = list(component_scores.values())
    if not component_values:
        score = 100.0
    else:
        component_average = sum(component_values) / len(component_values)
        component_min = min(component_values)
        score = ((100 - component_average) * 0.7) + ((100 - component_min) * 0.3)

    if score >= 85:
        level = "CRITICAL"
        message = "핵심 하수도 시설이 매우 취약하여 구조적 침수 위험이 매우 높습니다."
    elif score >= 70:
        level = "HIGH"
        message = "일부 핵심 하수도 시설이 취약하여 구조적 침수 위험이 높습니다."
    elif score >= 40:
        level = "MEDIUM"
        message = "일부 하수도 시설이 상대적으로 취약합니다."
    else:
        level = "LOW"
        message = "하수도 시설 기준 구조적 위험은 낮은 편입니다."

    return {
        "score": round(float(score), 2),
        "level": level,
        "message": message,
    }


def get_integrated_data_by_gu(gu_name: str) -> dict[str, Any]:
    try:
        sewer = get_sewer_capacity_by_gu(gu_name)
    except SewerFacilityDataError as exc:
        raise IntegratedDataError(exc.status_code, exc.error, exc.detail) from exc

    if not sewer:
        raise IntegratedDataError(404, "데이터 없음", f"{gu_name} 하수도 시설 데이터를 찾을 수 없습니다.")

    component_scores = sewer.get("component_scores", {})
    structural_risk = calculate_structural_risk(component_scores=component_scores)
    weakest_score = min(component_scores.values()) if component_scores else None
    weakest_components = (
        [name for name, score in component_scores.items() if score == weakest_score] if weakest_score is not None else []
    )
    problem_factors: list[str] = []
    if weakest_components:
        problem_factors.append(f"취약 시설 항목: {', '.join(weakest_components)}")
    if not problem_factors:
        problem_factors.append("시설 지표 기준으로 즉시 취약 요인은 크지 않습니다.")

    return {
        "gu_name": gu_name,
        "sewer_capacity": sewer,
        "structural_risk": structural_risk,
        "score_breakdown": {
            "formula": "structural_risk = (100 - component_average) * 0.7 + (100 - component_min) * 0.3",
            "component_average": round(sum(component_scores.values()) / len(component_scores), 2) if component_scores else 0.0,
            "component_min": round(min(component_scores.values()), 2) if component_scores else 0.0,
            "component_scores": component_scores,
        },
        "problem_factors": problem_factors,
    }
