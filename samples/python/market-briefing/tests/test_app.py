# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import tomllib
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from webiq.errors import APIStatusError

from webiq_market_briefing import demo
from webiq_market_briefing.diagnostics import logger

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("WEBIQ_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    return AppTest.from_file(str(APP), default_timeout=20).run()


def test_live_only_ui_has_general_title_and_collapsed_connection_setup(app):
    assert not app.exception
    assert app.title[0].value == "Web IQ Insight Studio"
    assert not app.radio
    assert app.text_input[0].label == "Your question or topic"
    assert not app.text_input[0].disabled
    setup = next(item for item in app.sidebar.expander if item.label == "Connection & setup")
    assert setup.proto.expanded is False
    assert app.button[0].disabled
    assert any("Expand Connection & setup" in message.value for message in app.info)
    assert not any("Illustrative" in block.value for block in app.markdown)


def test_live_ui_requires_consent_and_does_not_autorun(monkeypatch):
    monkeypatch.setattr(demo, "live_requirements", lambda path: [])
    run = MagicMock(return_value=replace(demo.example_briefing(), is_example=False))
    monkeypatch.setattr(demo, "run_live", run)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert app.button[0].disabled
    run.assert_not_called()
    consent = next(item for item in app.checkbox if item.label == "Allow billable live requests")
    consent.check().run()
    app.button[0].click().run()
    assert not app.exception
    run.assert_called_once()
    assert any("Live APIs completed" in message.value for message in app.success)
    assert run.call_args.kwargs["max_results"] == 3
    app.text_input[0].set_value("A different topic").run()
    assert not any("Live APIs completed" in message.value for message in app.success)


def test_service_error_is_explicit_and_never_looks_like_sample_success(monkeypatch):
    monkeypatch.setattr(demo, "live_requirements", lambda path: [])
    monkeypatch.setattr(
        demo, "run_live",
        MagicMock(side_effect=APIStatusError(401, "PRIVATE-SERVICE-ERROR")),
    )
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(item for item in app.checkbox if item.label == "Allow billable live requests").check().run()
    app.button[0].click().run()
    assert not app.exception
    assert any("No fresh report was created" in message.value for message in app.error)
    assert not app.success
    assert not app.warning
    assert not any("PRIVATE-SERVICE-ERROR" in message.value for message in app.error)
    assert app.session_state["run_trace_state"] == "failed"
    trace = "\n".join(app.session_state["run_trace_lines"])
    assert "state=failed" in trace
    assert "PRIVATE-SERVICE-ERROR" not in trace


def test_how_it_works_explains_startup_and_six_step_flow_without_api_calls(monkeypatch):
    run = MagicMock(side_effect=AssertionError("The explanation must not call live APIs"))
    monkeypatch.setattr(demo, "run_live", run)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert "How it works" in [tab.label for tab in app.tabs]
    architecture = next(
        block.value for block in app.markdown if 'class="iq-architecture"' in block.value
    )
    assert architecture.count('class="iq-node"') == 6
    for component in ("Your question", "Python app", "Web IQ", "Evidence", "Azure OpenAI", "Cited briefing"):
        assert component in architecture
    assert any("Start-Live.ps1" in code.value for code in app.code)
    assert any("No database or vector index" in caption.value for caption in app.caption)
    assert any("do not prove factual accuracy" in caption.value for caption in app.caption)
    run.assert_not_called()


def test_ignite_inspired_theme_preserves_local_only_settings():
    settings = tomllib.loads((APP.parent / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert settings["theme"]["primaryColor"] == "#F472C8"
    assert settings["theme"]["backgroundColor"] == "#050423"
    assert settings["server"]["address"] == "127.0.0.1"
    assert settings["browser"]["gatherUsageStats"] is False


def test_live_trace_is_retained_and_can_be_cleared_without_rerunning_services(monkeypatch):
    monkeypatch.setenv("WEBIQ_API_KEY", "PRIVATE-WEB-KEY")
    monkeypatch.setattr(demo, "live_requirements", lambda path: [])

    def generate(**kwargs):
        logger.info("service=webiq operation=_search_web query=Energy PRIVATE-WEB-KEY")
        logger.info("service=webiq status=200 elapsed_ms=23 trace_id=test-trace")
        return replace(demo.example_briefing(), is_example=False)

    run = MagicMock(side_effect=generate)
    monkeypatch.setattr(demo, "run_live", run)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert "Live trace" in [tab.label for tab in app.tabs]
    assert any("Earlier PowerShell logs" in message.value for message in app.info)
    next(item for item in app.checkbox if item.label == "Allow billable live requests").check().run()
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["run_trace_state"] == "complete"
    trace = "\n".join(app.session_state["run_trace_lines"])
    assert "operation=_search_web" in trace
    assert "elapsed_ms=23" in trace
    assert "PRIVATE-WEB-KEY" not in trace
    assert "[REDACTED]" in trace
    app.text_input[0].set_value("Next topic").run()
    assert "\n".join(app.session_state["run_trace_lines"]) == trace
    next(button for button in app.button if button.label == "Clear trace").click().run()
    assert not app.exception
    assert "run_trace_lines" not in app.session_state
    assert any("Earlier PowerShell logs" in message.value for message in app.info)
    run.assert_called_once()


def test_live_only_ui_does_not_run_or_create_trace_without_consent(monkeypatch):
    monkeypatch.setattr(demo, "live_requirements", lambda path: [])
    run = MagicMock(side_effect=AssertionError("Consent is required"))
    monkeypatch.setattr(demo, "run_live", run)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert not app.radio
    assert app.button[0].disabled
    assert "run_trace_lines" not in app.session_state
    assert not app.success
    run.assert_not_called()
