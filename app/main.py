import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

from app.api.v1.router import router
from app.core.observability import setup_observability

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SRM Credit Engine",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

setup_observability(app)
app.add_middleware(OpenTelemetryMiddleware)
app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocorreu um erro interno no servidor."},
    )


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
