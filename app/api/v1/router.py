from fastapi import APIRouter

from app.api.v1.routes import auth, batches, exchange_rates, internal, receivables

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(receivables.router)
router.include_router(batches.router)
router.include_router(exchange_rates.router)
router.include_router(internal.router)
