from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import APP_NAME
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router

app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    description="Backend API for Alba Mora portfolio chat",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://albamora.dev",
        "https://www.albamora.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")