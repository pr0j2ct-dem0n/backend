from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.rainfall import router as rainfall_router
from routers.river import router as river_router
from routers.sewer import router as sewer_router
from routers.sewer_pipe import router as sewer_pipe_router
from routers.waste import router as waste_router
from schemas.api_models import HealthResponse

openapi_tags = [
    {
        "name": "rainfall",
        "description": "서울시 강우량 데이터 조회 API",
    },
    {
        "name": "river",
        "description": "서울시 하천 수위 데이터 조회 API",
    },
    {
        "name": "sewer",
        "description": "서울시 하수도 시설 현황 CSV 조회 API",
    },
    {
        "name": "waste",
        "description": "서울시 생활계폐기물 발생량 CSV 조회 API",
    },
    {
        "name": "sewer-pipe",
        "description": "서울시 하수관로 수위 조회 API",
    },
]

app = FastAPI(
    title="Seoul Under-Dash",
    description="서울시 공공 API 기반 강우량/하천 수위 조회 백엔드",
    openapi_tags=openapi_tags,
)

allowed_origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rainfall_router)
app.include_router(river_router)
app.include_router(sewer_router)
app.include_router(waste_router)
app.include_router(sewer_pipe_router)


@app.get(
    "/",
    summary="서버 상태 확인",
    description="백엔드 서버의 실행 상태를 확인합니다.",
    response_model=HealthResponse,
)
def health_check() -> dict[str, str]:
    return {"message": "Seoul Under-Dash API is running"}
