from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(..., description="오류 유형 또는 메시지 (error message)")
    detail: str | None = Field(default=None, description="오류 상세 설명 (error detail)")


class NotFoundGuResponse(BaseModel):
    error: str = Field(..., description="오류 메시지 (데이터 없음, not found)")
    gu: str = Field(..., description="조회한 자치구 이름 (district name)")


class HealthResponse(BaseModel):
    message: str = Field(..., description="서버 상태 메시지 (server status message)")


class RainfallGuItem(BaseModel):
    gu: str = Field(..., description="자치구 이름 (district name)")
    rainfall_avg_10min: float = Field(..., description="자치구 평균 10분 강우량 (10-min rainfall average)")
    rainfall_max_10min: float = Field(..., description="자치구 최대 10분 강우량 (10-min rainfall maximum)")
    station_count: int = Field(..., description="집계에 사용된 관측소 개수 (number of stations)")


class RiverGuItem(BaseModel):
    gu: str = Field(..., description="자치구 이름 (district name)")
    river_level_avg: float = Field(..., description="자치구 평균 하천 수위 (average river level)")
    river_level_max: float = Field(..., description="자치구 최대 하천 수위 (maximum river level)")
    station_count: int = Field(..., description="집계에 사용된 관측소 개수 (number of stations)")


class SewerGuItem(BaseModel):
    gu: str = Field(..., description="자치구 이름 (district name)")
    underpass_length: float = Field(..., description="암거 길이(m) (underpass sewer length)")
    open_channel_length: float = Field(..., description="개거 길이(m) (open channel length)")
    pipe_length: float = Field(..., description="관거 길이(m) (pipe sewer length)")
    u_ditch_length: float = Field(..., description="U형측구 길이(m) (U-shaped ditch length)")
    cross_sewer_length: float = Field(..., description="횡단하수거 길이(m) (cross sewer length)")


class SewerPipeGuItem(BaseModel):
    gu: str = Field(..., description="자치구 이름 (district name)")
    pipe_level_avg: float = Field(..., description="자치구 평균 하수관로 수위 (average sewer pipe level)")
    pipe_level_max: float = Field(..., description="자치구 최대 하수관로 수위 (maximum sewer pipe level)")
    occupancy_ratio: float = Field(..., description="기준 수위 대비 점유율(%) (occupancy ratio)")
    status: str = Field(..., description="점유율 기반 상태 (NORMAL/WARNING/CRITICAL)")
    overflow_risk: bool = Field(..., description="점유율 100% 초과 여부 (overflow risk)")
    station_count: int = Field(..., description="집계에 사용된 관측 지점 개수 (number of stations)")


class IntegratedStructuralRisk(BaseModel):
    score: float = Field(..., description="구조적 위험 점수 (0-100)")
    level: str = Field(..., description="구조적 위험 등급 (LOW/MEDIUM/HIGH/CRITICAL)")
    message: str = Field(..., description="구조적 위험 설명")


class IntegratedScoreBreakdown(BaseModel):
    formula: str = Field(..., description="구조적 위험 계산식")
    component_average: float = Field(..., description="시설 항목 점수 평균")
    component_min: float = Field(..., description="시설 항목 점수 최솟값")
    component_scores: dict[str, float] = Field(..., description="시설 항목별 상대 점수")


class IntegratedResponse(BaseModel):
    gu_name: str = Field(..., description="자치구 이름")
    sewer_capacity: dict = Field(..., description="하수도 시설 총량/항목/점수")
    structural_risk: IntegratedStructuralRisk
    score_breakdown: IntegratedScoreBreakdown
    problem_factors: list[str] = Field(..., description="취약 요인 목록")


class PredictScores(BaseModel):
    rain_capacity_risk: float
    drainpipe_level_risk: float
    river_level_risk: float
    flood_history_risk: float
    sewer_structure_risk: float


class PredictMetrics(BaseModel):
    rainfall_mm: float
    danger_rainfall_mm: float
    inflow_m3: float
    effective_capacity_m3: float
    drainpipe_occupancy_ratio: float


class PredictFloodHistory(BaseModel):
    flood_count: int


class PredictAreaItem(BaseModel):
    gu_name: str
    scores: PredictScores
    final_risk_score: float
    risk_level: str
    metrics: PredictMetrics
    flood_history: PredictFloodHistory
    debug: dict
    reasons: list[str]


class PredictResponse(BaseModel):
    base_time: str
    areas: list[PredictAreaItem]


class FloodHistoryItem(BaseModel):
    gu_name: str
    flood_count: int
    flood_history_risk: float


class RainFacilityItem(BaseModel):
    gu_name: str
    water_area_m2: float
    prcs_cpct: float
    fclt_qy: float
    use_qy: float
    remaining_capacity_m3: float
    effective_capacity_m3: float
