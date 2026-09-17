"""Minimal Phoenix bridge: trace transport, never canonical Skill state."""

from __future__ import annotations

import asyncio

import httpx
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from .config import Settings


class PhoenixUnavailable(RuntimeError):
    pass


class PhoenixTraceClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.phoenix_base_url.rstrip("/")
        self.collector_endpoint = settings.phoenix_collector_endpoint
        self.project_name = settings.phoenix_project_name

    async def healthcheck(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(self.base_url)
            return response.is_success, f"{self.base_url}: HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            return False, f"{self.base_url}: {type(exc).__name__}"

    async def record_execution(self, *, skill_version_id: str, input_summary: str, output_summary: str | None, status: str) -> str:
        available, detail = await self.healthcheck()
        if not available:
            raise PhoenixUnavailable(f"Phoenix trace collector is unavailable ({detail}).")
        return await asyncio.to_thread(self._emit, skill_version_id, input_summary, output_summary, status)

    def _emit(self, skill_version_id: str, input_summary: str, output_summary: str | None, status: str) -> str:
        provider = TracerProvider(resource=Resource.create({"service.name": self.project_name, "openinference.project.name": self.project_name}))
        provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=self.collector_endpoint, timeout=5)))
        tracer = provider.get_tracer("octopus-skill-lab")
        with tracer.start_as_current_span("skill.execution") as span:
            context = span.get_span_context()
            span.set_attribute("skill.version_id", skill_version_id)
            span.set_attribute("execution.status", status)
            span.set_attribute("input.value", input_summary)
            if output_summary is not None:
                span.set_attribute("output.value", output_summary)
            trace_id = f"{context.trace_id:032x}"
        provider.shutdown()
        return trace_id
