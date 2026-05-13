from fastapi import FastAPI

from app.api.v1.router import router
from app.core.observability import setup_observability

app = FastAPI(
    title="SRM Credit Engine",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

setup_observability(app)
app.include_router(router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
