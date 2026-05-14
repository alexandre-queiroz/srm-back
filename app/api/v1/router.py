from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    batches,
    companies,
    currencies,
    exchange_rates,
    internal,
    product_types,
    receivables,
    reports,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(receivables.router)
router.include_router(batches.router)
router.include_router(exchange_rates.router)
router.include_router(internal.router)
router.include_router(reports.router)
router.include_router(companies.router)
router.include_router(currencies.router)
router.include_router(product_types.router)
