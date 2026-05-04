from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.prediction import router as prediction_router

app = FastAPI(title="Seoul Under-Dash")

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

app.include_router(prediction_router)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"message": "Seoul Under-Dash API is running"}
