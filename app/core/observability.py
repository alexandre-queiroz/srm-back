from __future__ import annotations

import os
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

from app.core.config import settings
from app.core.database import engine

if TYPE_CHECKING:
    from fastapi import FastAPI

_tracer: trace.Tracer | None = None
_provider: TracerProvider | None = None


def setup_observability(app: FastAPI | None = None) -> None:
    global _tracer, _provider
    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME.strip()})

    exporter = OTLPSpanExporter(
        endpoint="https://api.axiom.co/v1/traces",
        headers={
            "Authorization": f"Bearer {settings.AXIOM_TOKEN.strip()}",
            "X-Axiom-Dataset": settings.AXIOM_DATASET.strip(),
        },
    )

    _provider = TracerProvider(resource=resource)

    # Environment-aware span processing:
    # Vercel needs SimpleSpanProcessor because the process is killed immediately after response.
    # The Worker (VPS) benefits from BatchSpanProcessor for better performance and reliability.
    if os.environ.get("VERCEL"):
        _provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)
    _tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME)

    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)


def get_tracer() -> trace.Tracer:
    if _tracer is None:
        return trace.get_tracer(settings.OTEL_SERVICE_NAME)
    return _tracer


def close_observability() -> None:
    """Flush and shutdown the tracer provider to ensure all spans are sent."""
    if _provider:
        _provider.shutdown()
