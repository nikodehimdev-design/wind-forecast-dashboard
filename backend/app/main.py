import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.forecast import router as forecast_router

app = FastAPI(title="Wind Forecast Analytics API", version="1.0.0")
origins = [x.strip() for x in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=False,
    allow_methods=["GET"], allow_headers=["*"]
)
app.include_router(forecast_router, prefix="/api")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "wind-forecast-analytics"}
