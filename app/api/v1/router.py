from fastapi import APIRouter

from app.api.v1.routes import auth

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
