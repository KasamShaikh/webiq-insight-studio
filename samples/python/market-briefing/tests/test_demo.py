# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import logging
from dataclasses import replace
from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
from openai import AzureOpenAI
from webiq import WebIQClient

from webiq_market_briefing import demo, report, retrieval
from webiq_market_briefing.diagnostics import capture_run_logs
from webiq_market_briefing.models import Evidence


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBIQ_API_KEY", "test-web-key")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-model-key")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"azure_openai": {
        "endpoint": "https://example.openai.azure.com/",
        "deployment": "test-deployment",
        "api_version": "test-version",
    }}), encoding="utf-8")
    return config


def test_example_is_explicitly_curated_and_does_not_call_services(monkeypatch):
    retrieve = MagicMock(side_effect=AssertionError("No API calls allowed"))
    generate = MagicMock(side_effect=AssertionError("No model calls allowed"))
    monkeypatch.setattr(demo, "retrieve_evidence", retrieve)
    monkeypatch.setattr(demo, "generate_report_body", generate)
    result = demo.example_briefing()
    assert result.is_example
    assert result.queries == []
    assert len(result.evidence) == 3
    assert {item.result_type for item in result.evidence} == {"curated"}
    assert "ILLUSTRATIVE WALKTHROUGH" in result.markdown
    assert "not a captured API response" in result.markdown
    assert "_Assembled locally without APIs:" in result.markdown
    assert result.retrieval_seconds == result.generation_seconds == 0
    assert "https://www.eia.gov/outlooks/steo/" in demo.source_linked_body(result)
    retrieve.assert_not_called()
    generate.assert_not_called()


@pytest.mark.parametrize(("full_run", "count"), [(False, 1), (True, 3)])
def test_quick_mode_uses_first_upstream_query(full_run, count):
    queries = demo.planned_queries("  Energy  ", 7, full_run, date(2026, 11, 17))
    assert len(queries) == count
    assert queries[0] == "Energy major developments 2026-11-10 through 2026-11-17"


@pytest.mark.parametrize(("topic", "days"), [("", 7), ("  ", 7), ("x" * 501, 7), ("Energy", 0), ("Energy", 31)])
def test_query_validation(topic, days):
    with pytest.raises(ValueError):
        demo.planned_queries(topic, days)


def test_live_readiness_reports_missing_settings_without_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("WEBIQ_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", " ")
    missing = demo.live_requirements(tmp_path / "missing.json")
    assert len(missing) == 2
    assert "WEBIQ_API_KEY" in missing[0]
    assert "not found" in missing[1]


def test_live_readiness_and_https_endpoint_validation(configured):
    assert demo.live_requirements(configured) == []
    data = json.loads(configured.read_text(encoding="utf-8"))
    data["azure_openai"]["endpoint"] = "http://example.openai.azure.com/"
    configured.write_text(json.dumps(data), encoding="utf-8")
    assert "HTTPS" in demo.live_requirements(configured)[0]


def test_live_readiness_surfaces_non_object_configuration(configured):
    configured.write_text("[]", encoding="utf-8")
    assert demo.live_requirements(configured) == ["Configuration must be a JSON object."]


def test_azure_cli_configuration_requires_no_model_key(monkeypatch, configured):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    data = json.loads(configured.read_text(encoding="utf-8"))
    data["azure_openai"]["auth_mode"] = "azure-cli"
    configured.write_text(json.dumps(data), encoding="utf-8")
    assert demo.live_requirements(configured) == []
    monkeypatch.setattr(demo, "retrieve_evidence", lambda **kwargs: [
        Evidence("Title", "https://example.com", "Passage", "query", "web"),
    ])
    generate = MagicMock(return_value="Finding [1].")
    monkeypatch.setattr(demo, "generate_report_body", generate)
    demo.run_live(
        topic="Energy", lookback_days=7, max_results=3, region="US",
        full_run=False, config_path=configured, progress=lambda message: None,
    )
    assert generate.call_args.kwargs["azure_openai_api_key"] is None
    assert generate.call_args.kwargs["azure_openai_auth_mode"] == "azure-cli"


def test_live_run_reuses_upstream_retrieval_and_citation_rendering(monkeypatch, configured):
    evidence = [
        Evidence("Title", "https://example.com/a(b)", "Passage", "query", "news"),
    ]
    retrieve = MagicMock(return_value=evidence)
    generate = MagicMock(return_value="## Executive Summary\n\nA finding [1].")
    monkeypatch.setattr(demo, "retrieve_evidence", retrieve)
    monkeypatch.setattr(demo, "generate_report_body", generate)
    progress = []
    result = demo.run_live(
        topic="  Energy  ", lookback_days=7, max_results=3, region="US",
        full_run=False, config_path=configured, progress=progress.append,
    )
    assert not result.is_example
    assert result.topic == "Energy"
    assert len(result.queries) == 1
    assert retrieve.call_args.kwargs["max_results"] == 3
    assert retrieve.call_args.kwargs["region"] == "US"
    assert generate.call_args.kwargs["deployment"] == "test-deployment"
    assert generate.call_args.kwargs["evidence"] == evidence
    assert len(progress) == 2
    assert "Retrieved 1 unique sources" in progress[1]
    assert "[[1]](#source-1)" in result.markdown
    assert "[[1]](https://example.com/a%28b%29)" in demo.source_linked_body(result)
    assert "test-web-key" not in result.markdown
    assert "test-model-key" not in result.markdown


def test_no_evidence_prevents_model_call(monkeypatch, configured):
    monkeypatch.setattr(demo, "retrieve_evidence", lambda **kwargs: [])
    generate = MagicMock()
    monkeypatch.setattr(demo, "generate_report_body", generate)
    with pytest.raises(ValueError, match="No model call"):
        demo.run_live(
            topic="Energy", lookback_days=7, max_results=3, region="US",
            full_run=False, config_path=configured, progress=lambda message: None,
        )
    generate.assert_not_called()


@pytest.mark.parametrize(("max_results", "region"), [(0, "US"), (11, "US"), (3, "invalid")])
def test_invalid_live_limits_prevent_retrieval(monkeypatch, configured, max_results, region):
    retrieve = MagicMock()
    monkeypatch.setattr(demo, "retrieve_evidence", retrieve)
    with pytest.raises(ValueError):
        demo.run_live(
            topic="Energy", lookback_days=7, max_results=max_results, region=region,
            full_run=False, config_path=configured, progress=lambda message: None,
        )
    retrieve.assert_not_called()


def test_retrieval_failure_is_not_replaced_with_example(monkeypatch, configured):
    monkeypatch.setattr(demo, "retrieve_evidence", MagicMock(side_effect=RuntimeError("Retrieval failed")))
    with pytest.raises(RuntimeError, match="Retrieval failed"):
        demo.run_live(
            topic="Energy", lookback_days=7, max_results=3, region="US",
            full_run=False, config_path=configured, progress=lambda message: None,
        )


def test_display_rejects_unknown_citation_and_unsafe_url():
    result = demo.example_briefing()
    with pytest.raises(ValueError, match="unknown source"):
        demo.source_linked_body(replace(result, body="Finding [9]."))
    unsafe = replace(result.evidence[0], url="javascript:alert(1)")
    with pytest.raises(ValueError, match="unsupported source URL"):
        demo.source_linked_body(replace(result, body="Finding [1].", evidence=[unsafe]))


@pytest.mark.parametrize(("full_run", "search_count", "source_count"), [(False, 2, 6), (True, 6, 18)])
def test_real_sdk_pipeline_offline_request_counts_and_payloads(
    monkeypatch, configured, full_run, search_count, source_count, caplog,
):
    caplog.set_level(logging.INFO, logger="webiq_market_briefing")
    searches = []
    generations = []

    def respond(request):
        payload = json.loads(request.content)
        if request.url.host == "example.openai.azure.com":
            generations.append(payload)
            return httpx.Response(200, headers={"x-request-id": "model-test-id"}, json={
                "id": "test-completion", "object": "chat.completion", "created": 0,
                "model": "test-deployment",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "A supported finding [1]."},
                    "finish_reason": "stop",
                }],
            })
        searches.append((request.url.path, payload))
        result_key = "webResults" if request.url.path.endswith("/web") else "newsResults"
        return httpx.Response(200, headers={"x-traceid": "web-test-id"}, json={result_key: [
            {
                "title": f"Source {len(searches)}-{index}",
                "url": f"https://example.com/{len(searches)}/{index}",
                "content": "A public evidence passage.",
            }
            for index in range(3)
        ]})

    monkeypatch.setattr(
        retrieval, "WebIQClient",
        lambda **kwargs: WebIQClient(http_client=httpx.Client(
            base_url="https://api.microsoft.ai/v3",
            transport=httpx.MockTransport(respond),
        ), **kwargs),
    )
    monkeypatch.setattr(
        report, "AzureOpenAI",
        lambda **kwargs: AzureOpenAI(http_client=httpx.Client(
            transport=httpx.MockTransport(respond),
        ), **kwargs),
    )
    trace_lines = []
    with capture_run_logs(trace_lines.append):
        result = demo.run_live(
            topic="Energy", lookback_days=7, max_results=3, region="US",
            full_run=full_run, config_path=configured, progress=lambda message: None,
        )
    assert len(searches) == search_count
    assert len(generations) == 1
    assert len(result.evidence) == source_count
    assert {item.result_type for item in result.evidence} == {"web", "news"}
    for path, payload in searches:
        assert path in {"/v3/search/web", "/v3/search/news"}
        assert payload["contentFormat"] == "passage"
        assert payload["maxLength"] == 3000
        assert payload["maxResults"] == 3
    assert generations[0]["max_completion_tokens"] == 3000
    assert "[[1]](#source-1)" in result.markdown
    trace = "\n".join(trace_lines)
    assert f"selected_sources={source_count}" in trace
    assert "returned_results=3 usable_results=3" in trace
    assert "trace_id=web-test-id" in trace
    assert "request_id=model-test-id" in trace
    assert "elapsed_ms=" in trace
    assert "citation_numbers=validated" in trace
    for private_value in ("test-web-key", "test-model-key", "A public evidence passage."):
        assert private_value not in trace
