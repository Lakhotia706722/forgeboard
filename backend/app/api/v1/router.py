from fastapi import APIRouter

from app.api.v1.endpoints import auth

api_router = APIRouter()

# Auth
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Phase 2+ — uncomment as each phase is completed
# from app.api.v1.endpoints import connectors, agents, runs
# api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
# api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
# api_router.include_router(runs.router, prefix="/runs", tags=["runs"])


@api_router.get("/ping", tags=["health"])
async def ping():
    return {"pong": True}
