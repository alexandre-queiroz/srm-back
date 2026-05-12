from fastapi import FastAPI

app = FastAPI(
    title="SRM Credit Engine",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
