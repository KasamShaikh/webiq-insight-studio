# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from webiq.telemetry import TelemetryEvent

from webiq_market_briefing.diagnostics import capture_run_logs, log_webiq_attempt, logger


@pytest.fixture(autouse=True)
def enable_sample_logs(caplog):
    caplog.set_level(logging.INFO, logger=logger.name)


def test_capture_is_scoped_timestamped_and_does_not_change_console_messages():
    lines = []
    before = tuple(logger.handlers)
    with capture_run_logs(lines.append):
        logger.info("service=webiq query=%s", "energy")
        logging.getLogger("unrelated").warning("Not part of this run")
    logger.info("After this run")
    assert len(lines) == 1
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z INFO ", lines[0])
    assert lines[0].endswith("service=webiq query=energy")
    assert tuple(logger.handlers) == before


def test_known_credentials_and_raw_exception_details_are_not_shown(monkeypatch):
    monkeypatch.setenv("WEBIQ_API_KEY", "PRIVATE-WEB-KEY")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "PRIVATE-MODEL-KEY")
    monkeypatch.setenv("AZURE_OPENAI_AD_TOKEN", "PRIVATE-ACCESS-TOKEN")
    lines = []
    with capture_run_logs(lines.append):
        logger.info("PRIVATE-WEB-KEY PRIVATE-MODEL-KEY PRIVATE-ACCESS-TOKEN\nnext line")
        logger.error(
            "Request failed: exception=RuntimeError",
            exc_info=(RuntimeError, RuntimeError("PRIVATE-ERROR-BODY"), None),
        )
    text = "\n".join(lines)
    for value in ("PRIVATE-WEB-KEY", "PRIVATE-MODEL-KEY", "PRIVATE-ACCESS-TOKEN", "PRIVATE-ERROR-BODY"):
        assert value not in text
    assert lines[0].count("[REDACTED]") == 3
    assert "\\nnext line" in lines[0]
    assert "\n" not in lines[0]


def test_capture_handler_is_removed_when_a_run_fails():
    lines = []
    before = tuple(logger.handlers)
    with pytest.raises(RuntimeError, match="Run failed"):
        with capture_run_logs(lines.append):
            logger.warning("Before failure")
            raise RuntimeError("Run failed")
    logger.info("Outside failed run")
    assert len(lines) == 1
    assert tuple(logger.handlers) == before


def test_overlapping_run_threads_do_not_share_trace_entries():
    barrier = Barrier(2, timeout=5)

    def capture(name):
        lines = []
        with capture_run_logs(lines.append):
            barrier.wait()
            logger.info("run=%s", name)
            barrier.wait()
        return lines

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(capture, "first")
        second = pool.submit(capture, "second")
        first_lines = first.result(timeout=10)
        second_lines = second.result(timeout=10)
    assert len(first_lines) == len(second_lines) == 1
    assert first_lines[0].endswith("run=first")
    assert second_lines[0].endswith("run=second")


@pytest.mark.parametrize("elapsed, expected", [(42, "42"), (None, "-")])
def test_webiq_telemetry_includes_real_elapsed_time(elapsed, expected):
    lines = []
    with capture_run_logs(lines.append):
        log_webiq_attempt(TelemetryEvent(
            method="POST", path="/search/web", transport="http", attempt=1,
            status_code=200, trace_id="trace-123", elapsed_ms=elapsed,
        ))
    assert f"elapsed_ms={expected}" in lines[0]
    assert "trace_id=trace-123" in lines[0]
