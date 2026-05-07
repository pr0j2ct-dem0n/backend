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


class WasteGuItem(BaseModel):
    gu: str = Field(..., description="자치구 이름 (district name)")
    waste_generation: float = Field(..., description="생활폐기물 발생량 (waste generation amount)")
