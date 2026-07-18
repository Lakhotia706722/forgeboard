from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title="ForgeBoard API",
    description="Shopify for AI agents — backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — tighten origins before production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "forgeboard-api"}
