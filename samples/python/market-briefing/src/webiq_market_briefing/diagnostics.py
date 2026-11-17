# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import os
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import get_ident

from webiq.telemetry import TelemetryEvent

logger = logging.getLogger("webiq_market_briefing")


class _RunTraceHandler(logging.Handler):
    def __init__(self, on_line: Callable[[str], None]) -> None:
        super().__init__(level=logging.INFO)
        self._on_line = on_line
        self._thread_id = get_ident()
        self._secrets = sorted({
            value for name in (
                "WEBIQ_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_AD_TOKEN",
                "AZURE_CLIENT_SECRET", "AZURE_CLIENT_CERTIFICATE_PASSWORD",
            )
            if (value := os.environ.get(name)) and value.strip()
        }, key=len, reverse=True)

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._thread_id:
            return
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, "[REDACTED]")
        message = message.replace("\r", "\\r").replace("\n", "\\n")
        timestamp = datetime.fromtimestamp(record.created, timezone.utc).isoformat(
            timespec="milliseconds",
        ).replace("+00:00", "Z")
        self._on_line(f"{timestamp} {record.levelname} {message}")


@contextmanager
def capture_run_logs(on_line: Callable[[str], None]) -> Iterator[None]:
    handler = _RunTraceHandler(on_line)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()


def safe_identifier(value: object) -> str:
    if not isinstance(value, str):
        return "-"
    return re.sub(r"[^A-Za-z0-9_.:-]", "_", value[:128])


def error_code(body: object) -> str:
    # Keep only the machine-readable code, never messages or arbitrary bodies.
    if not isinstance(body, Mapping):
        return "-"
    error = body.get("error")
    if isinstance(error, Mapping):
        return safe_identifier(error.get("code"))
    return safe_identifier(body.get("errorCode") or body.get("code"))


def log_webiq_attempt(event: TelemetryEvent) -> None:
    level = logging.WARNING if event.error or (event.status_code or 0) >= 400 else logging.INFO
    logger.log(
        level,
        "service=webiq operation=%s status=%s request_id=%s trace_id=%s "
        "error_code=%s exception=%s elapsed_ms=%s",
        safe_identifier(event.path),
        event.status_code,
        safe_identifier(event.request_id),
        safe_identifier(event.trace_id),
        error_code(event.error_body),
        type(event.error).__name__ if event.error else "-",
        event.elapsed_ms if event.elapsed_ms is not None else "-",
    )
