# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from urllib.parse import quote, urlsplit

from .config import load_azure_openai_settings
from .diagnostics import logger
from .models import Evidence
from .queries import build_queries
from .report import build_markdown, generate_report_body
from .retrieval import retrieve_evidence

EXAMPLE_TOPIC = "North American energy market"
EXAMPLE_NOTICE = (
    "ILLUSTRATIVE WALKTHROUGH - no Web IQ or Azure OpenAI calls were made. "
    "The evidence is manually curated public background, not a captured API response "
    "or a current market briefing. The displayed date window is a rehearsal setting, "
    "not a freshness filter applied to these sources."
)


@dataclass(frozen=True)
class Briefing:
    topic: str
    queries: list[str]
    evidence: list[Evidence]
    body: str
    markdown: str
    is_example: bool
    retrieval_seconds: float = 0.0
    generation_seconds: float = 0.0


def planned_queries(
    topic: str,
    lookback_days: int,
    full_run: bool = False,
    as_of: date | None = None,
) -> list[str]:
    topic = topic.strip()
    if not topic or len(topic) > 500:
        raise ValueError("Enter a topic between 1 and 500 characters.")
    if not 1 <= lookback_days <= 30:
        raise ValueError("The demo reporting window must be between 1 and 30 days.")
    queries = build_queries(topic, lookback_days, as_of)
    return queries if full_run else queries[:1]


def live_requirements(config_path: Path) -> list[str]:
    missing = []
    if not os.environ.get("WEBIQ_API_KEY", "").strip():
        missing.append("Set WEBIQ_API_KEY in the server's environment.")
    try:
        settings = load_azure_openai_settings(config_path)
        if settings.auth_mode == "api-key" and not os.environ.get("AZURE_OPENAI_API_KEY", "").strip():
            missing.append("Set AZURE_OPENAI_API_KEY in the server's environment.")
        endpoint = urlsplit(settings.endpoint)
        if (
            endpoint.scheme != "https"
            or not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            missing.append("Use an HTTPS Azure OpenAI endpoint without credentials or query parameters.")
    except (ValueError, OSError) as error:
        missing.append(str(error))
    return missing


def run_live(
    *,
    topic: str,
    lookback_days: int,
    max_results: int,
    region: str,
    full_run: bool,
    config_path: Path,
    progress: Callable[[str], None],
) -> Briefing:
    end_date = date.today()
    queries = planned_queries(topic, lookback_days, full_run, end_date)
    if not 1 <= max_results <= 10:
        raise ValueError("Results per search must be between 1 and 10.")
    if not re.fullmatch(r"[A-Z]{2}", region):
        raise ValueError("Use a two-letter uppercase region code.")
    missing = live_requirements(config_path)
    if missing:
        raise ValueError("Live setup incomplete: " + " ".join(missing))
    settings = load_azure_openai_settings(config_path)
    start_date = end_date - timedelta(days=lookback_days)
    topic = topic.strip()

    progress(f"Searching Web IQ Web + News for {len(queries)} query(s)...")
    logger.info("stage=retrieval state=started query_count=%s", len(queries))
    started = perf_counter()
    evidence = retrieve_evidence(
        api_key=os.environ["WEBIQ_API_KEY"],
        queries=queries,
        max_results=max_results,
        region=region,
    )
    retrieval_seconds = perf_counter() - started
    logger.info(
        "stage=evidence selected_sources=%s elapsed_ms=%.0f",
        len(evidence), retrieval_seconds * 1000,
    )
    for index, item in enumerate(evidence, start=1):
        logger.info(
            "stage=evidence source=%s type=%s source_url=%s",
            index, item.result_type, json.dumps(item.url),
        )
    if not evidence:
        raise ValueError("Web IQ returned no usable evidence. No model call was made.")

    progress(f"Retrieved {len(evidence)} unique sources. Azure OpenAI is writing the briefing...")
    started = perf_counter()
    body = generate_report_body(
        azure_openai_api_key=(
            os.environ["AZURE_OPENAI_API_KEY"] if settings.auth_mode == "api-key" else None
        ),
        azure_openai_endpoint=settings.endpoint,
        azure_openai_api_version=settings.api_version,
        deployment=settings.deployment,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        evidence=evidence,
        azure_openai_auth_mode=settings.auth_mode,
    )
    generation_seconds = perf_counter() - started
    markdown = build_markdown(topic, start_date, end_date, body, evidence)
    logger.info(
        "stage=report state=complete citation_numbers=validated elapsed_ms=%.0f",
        generation_seconds * 1000,
    )
    return Briefing(
        topic, queries, evidence, body, markdown, False,
        retrieval_seconds, generation_seconds,
    )


def source_linked_body(briefing: Briefing) -> str:
    def link(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if not 1 <= number <= len(briefing.evidence):
            raise ValueError("The briefing references an unknown source.")
        url = briefing.evidence[number - 1].url
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("The briefing contains an unsupported source URL.")
        return f"[[{number}]]({quote(url, safe='/:?#[]@!$&*+,;=%')})"

    return re.sub(r"\[(\d+)\]", link, briefing.body)


def example_briefing() -> Briefing:
    query = "Manually curated background; not retrieved by Web IQ"
    evidence = [
        Evidence(
            "EIA: Short-Term Energy Outlook",
            "https://www.eia.gov/outlooks/steo/",
            "The Short-Term Energy Outlook provides forecasts and data covering oil, "
            "natural gas, electricity, coal and renewable energy.",
            query, "curated", "U.S. Energy Information Administration",
        ),
        Evidence(
            "EIA: Natural gas prices",
            "https://www.eia.gov/energyexplained/natural-gas/prices.php",
            "Natural gas bills include the commodity cost and transmission and distribution "
            "costs. Infrastructure, demand and regulation can affect consumer prices.",
            query, "curated", "U.S. Energy Information Administration",
        ),
        Evidence(
            "EIA: Electricity prices and factors affecting prices",
            "https://www.eia.gov/energyexplained/electricity/prices-and-factors-affecting-prices.php",
            "Electricity prices reflect generation and grid costs. Fuel prices, weather, "
            "demand and regulation can influence those costs.",
            query, "curated", "U.S. Energy Information Administration",
        ),
    ]
    body = """## Executive Summary

Energy-market briefings can combine an outlook source with explanations of gas and
electricity price drivers. This example uses EIA background information. [1] [2] [3]

## Key Developments

- **Where to investigate:** the Short-Term Energy Outlook covers multiple energy
  markets and provides forecasts and data. This is a source to inspect, not a new
  market development established by this walkthrough. [1]
- **Gas cost drivers:** consumer costs include the commodity and the infrastructure
  used to transport and distribute it. [2]
- **Electricity cost drivers:** fuel, generation and grid costs matter; weather,
  demand and regulation also influence prices. [3]

## Risks and Uncertainties

No live searches were made. These background pages do not establish this week's
prices, breaking news or a current investment outlook. No market forecast is made.

## Outlook

For a real briefing, run the live Web + News searches, inspect the retrieved
passages and dates, and verify each claim against its original source.
"""
    end_date = date.today()
    markdown = build_markdown(
        EXAMPLE_TOPIC, end_date - timedelta(days=7), end_date, body, evidence,
    )
    markdown = (
        f"> {EXAMPLE_NOTICE}\n\n"
        + markdown.replace("_Generated:", "_Assembled locally without APIs:", 1)
    )
    return Briefing(EXAMPLE_TOPIC, [], evidence, body, markdown, True)
