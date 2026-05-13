from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from app.core.config import settings
from app.core.database import engine

_tracer: trace.Tracer | None = None


def setup_observability() -> None:
    global _tracer
    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})

    exporter = OTLPSpanExporter(
        endpoint="https://api.axiom.co/v1/traces",
        headers={
            "Authorization": f"Bearer {settings.AXIOM_TOKEN.strip()}",
            "X-Axiom-Dataset": settings.AXIOM_DATASET.strip(),
        },
    )

    provider = TracerProvider(resource=resource)
    # SimpleSpanProcessor for serverless (Vercel) — exports synchronously before function terminates.
    # The worker uses the same setup; BatchSpanProcessor would be marginally better there,
    # but Simple is safe for both and keeps a single code path.
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME)

    # Automatic Instrumentation
    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()


def get_tracer() -> trace.Tracer:
    if _tracer is None:
        return trace.get_tracer(settings.OTEL_SERVICE_NAME)
    return _tracer
