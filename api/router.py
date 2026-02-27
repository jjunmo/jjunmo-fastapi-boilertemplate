from fastapi import APIRouter

from api.routes import health
from schemas.common import COMMON_ERROR_RESPONSES

api_router = APIRouter(prefix="/api/v1", responses=COMMON_ERROR_RESPONSES)
api_router.include_router(health.router)
