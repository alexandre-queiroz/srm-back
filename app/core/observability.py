from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings


def setup_observability() -> None:
    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})

    exporter = OTLPSpanExporter(
        endpoint="https://api.axiom.co/v1/traces",
        headers={
            "Authorization": f"Bearer {settings.AXIOM_TOKEN}",
            "X-Axiom-Dataset": settings.AXIOM_DATASET,
        },
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
