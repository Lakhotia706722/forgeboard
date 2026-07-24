from fastapi import APIRouter

from app.api.v1.endpoints import auth, connectors, agents, runs, governance, voice

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(runs.router, tags=["runs"])
api_router.include_router(governance.router, prefix="/governance", tags=["governance"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])


@api_router.get("/ping", tags=["health"])
async def ping():
    return {"pong": True}
