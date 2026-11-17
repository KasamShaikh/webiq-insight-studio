# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from dataclasses import asdict
from pathlib import Path

import streamlit as st
from azure.core.exceptions import AzureError
from openai import OpenAIError
from webiq.errors import WebIQError

from webiq_market_briefing.demo import (
    EXAMPLE_TOPIC,
    live_requirements,
    planned_queries,
    run_live,
    source_linked_body,
)
from webiq_market_briefing.diagnostics import capture_run_logs, logger
from webiq_market_briefing.retrieval import MAX_CONTENT_CHARACTERS

SAMPLE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SAMPLE_DIR / "config.local.json"
if not CONFIG_PATH.exists():
    CONFIG_PATH = SAMPLE_DIR / "config.json"

st.set_page_config(page_title="Web IQ | Insight Studio", layout="wide")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger.setLevel(logging.INFO)
st.markdown(
    """<style>
    .block-container { max-width: 1180px; padding-top: 2rem; }
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 92% 8%, #34116b66, transparent 48%),
            radial-gradient(ellipse at 8% 95%, #243b8a33, transparent 45%),
            #050423;
    }
    [data-testid="stHeader"] { background: #050423ee; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #15103d, #090725);
        border-right: 1px solid #392568;
    }
    h1 {
        letter-spacing: -0.045em;
        background: linear-gradient(100deg, #ffffff 20%, #f6c4ee 62%, #ffad76);
        background-clip: text;
        -webkit-text-fill-color: transparent;
        width: fit-content;
    }
    [data-testid="stMain"] {
        border-top: 3px solid transparent;
        border-image: linear-gradient(90deg, #ff6a00, #d62aaa, #8254ef, #47d6ed) 1;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #241447, #15103d);
        border: 1px solid #51316e;
        border-radius: 12px; padding: 1rem;
    }
    div[data-testid="stTabs"] button { font-size: 1rem; }
    [role="tab"][aria-selected="true"] { color: #ffb0dd; }
    button[kind="primary"]:not(:disabled) {
        background: linear-gradient(105deg, #ee78ce, #ffac76);
        border: 0;
        color: #170925;
    }
    button[kind="primary"]:not(:disabled) p { color: #170925; font-weight: 650; }
    .iq-architecture {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 1.15rem;
        margin: 1.25rem 0 0.75rem;
    }
    .iq-node {
        position: relative;
        padding: 0.9rem 0.75rem;
        border: 1px solid #51316e;
        border-top: 3px solid #ee78ce;
        border-radius: 12px;
        background: linear-gradient(145deg, #241447, #15103d);
        min-width: 0;
    }
    .iq-node:nth-child(3n) { border-top-color: #ffac76; }
    .iq-node:nth-child(3n + 2) { border-top-color: #a894ff; }
    .iq-node:not(:last-child)::after {
        content: ">";
        position: absolute;
        right: -0.9rem;
        top: 40%;
        color: #ffac76;
        font-weight: 700;
    }
    .iq-node small { display: block; color: #c8bde6; font-size: 0.78rem; }
    .iq-node strong { display: block; color: #fff3fc; margin: 0.3rem 0; }
    .iq-node span { color: #d7d0ee; font-size: 0.83rem; line-height: 1.4; }
    @media (max-width: 1000px) {
        .iq-architecture { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .iq-node:nth-child(3)::after { content: none; }
    }
    @media (max-width: 550px) {
        .iq-architecture { grid-template-columns: 1fr; gap: 1.4rem; }
        .iq-node:not(:last-child)::after {
            content: ">";
            right: 50%; top: auto; bottom: -1.35rem; transform: rotate(90deg);
        }
    }
    </style>""",
    unsafe_allow_html=True,
)

missing = live_requirements(CONFIG_PATH)
with st.sidebar:
    st.subheader("Live APIs")
    with st.expander("Connection & setup", expanded=False):
        if missing:
            st.warning("Live access is not configured.")
            for requirement in missing:
                st.write(requirement)
            st.write("The Web IQ key must have both Web and News access.")
        else:
            st.info("Configured locally. Generate a briefing to verify end-to-end access in this page.")
        st.link_button(
            "Web IQ API key setup",
            "https://learn.microsoft.com/en-us/web-iq/get-started/authentication",
        )
        st.caption(
            "The Web IQ key stays in the server's environment. "
            "The model can use your Azure CLI sign-in instead of a key."
        )
        st.divider()
        st.markdown("**Five-minute story**")
        st.write("Ask a useful question. Show the evidence. Verify one claim. Let attendees try.")
    st.caption("Nothing runs until you allow live usage and generate a briefing.")

st.caption("WEB IQ DEMOS / FIVE-MINUTE LAB")
st.title("Web IQ Insight Studio")
st.markdown("### One question. Live web evidence. Insights you can verify.")
st.caption("Local visual adaptation of Microsoft's open-source market-briefing sample.")
steps = st.columns(3)
for column, heading, detail in zip(
    steps,
    ("01 / Ask", "02 / Retrieve", "03 / Verify"),
    (
        "Choose a question and a reporting window.",
        "Web IQ supplies web and news passages.",
        "Azure OpenAI drafts; you check the citations.",
    ),
):
    with column.container(border=True):
        st.markdown(f"**{heading}**")
        st.caption(detail)

topic = st.text_input(
    "Your question or topic", value=EXAMPLE_TOPIC, max_chars=500,
)
controls = st.columns(3)
lookback_days = controls[0].selectbox("Look back (days)", [7, 1, 14, 30])
max_results = controls[1].selectbox("Results per search", [3, 5, 10])
region = controls[2].selectbox("Region", ["US", "IN", "GB"])
full_run = st.checkbox("Use all 3 upstream queries (slower)")
st.caption(
    f"{6 if full_run else 2} initial Web IQ requests + 1 Azure OpenAI generation. "
    "Retries can add calls. Date-bounded queries do not guarantee publication dates."
)
if missing:
    st.info("Live access is not configured. Expand Connection & setup in the sidebar for details.")
consent = st.checkbox("Allow billable live requests", disabled=bool(missing))

signature = (topic, lookback_days, max_results, region, full_run)
if st.session_state.get("briefing_signature") != signature:
    st.session_state.pop("briefing", None)
    st.session_state["briefing_signature"] = signature

try:
    queries = planned_queries(topic, lookback_days, full_run)
    input_error = None
except ValueError as error:
    queries = []
    input_error = str(error)
    st.error(input_error)

clicked = st.button(
    "Generate live briefing",
    type="primary",
    disabled=bool(input_error) or bool(missing) or not consent,
)
st.caption("Logs stream below while running and remain in the Live trace tab afterward.")
if clicked:
    st.session_state.pop("briefing", None)
    trace_lines: list[str] = []
    st.session_state["run_trace_lines"] = trace_lines
    st.session_state["run_trace_topic"] = topic.strip()
    st.session_state["run_trace_state"] = "running"
    with st.status("Starting live run...", expanded=True) as status:
        with st.container(height=240):
            trace_output = st.empty()

        def append_trace(line: str) -> None:
            trace_lines.append(line)
            trace_output.code("\n".join(trace_lines), language="text")

        with capture_run_logs(append_trace):
            logger.info("stage=run state=started")
            try:
                briefing = run_live(
                    topic=topic,
                    lookback_days=lookback_days,
                    max_results=max_results,
                    region=region,
                    full_run=full_run,
                    config_path=CONFIG_PATH,
                    progress=lambda message: status.update(label=message),
                )
            except (WebIQError, OpenAIError, AzureError) as error:
                logger.error("stage=run state=failed exception=%s", type(error).__name__)
                st.session_state["run_trace_state"] = "failed"
                status.update(label="Live run failed", state="error")
                st.error(
                    "A service or authentication request failed. Check the sanitized "
                    "status and correlation IDs in Live trace below or the server terminal. "
                    "Verify both Web IQ entitlements and the Azure OpenAI deployment. "
                    "No fresh report was created."
                )
            except (ValueError, RuntimeError, OSError) as error:
                logger.error("stage=run state=failed exception=%s", type(error).__name__)
                st.session_state["run_trace_state"] = "failed"
                status.update(label="Live run failed", state="error")
                st.error(str(error))
            else:
                logger.info("stage=run state=complete")
                st.session_state["run_trace_state"] = "complete"
                status.update(
                    label="Briefing complete; numeric citations checked",
                    state="complete", expanded=False,
                )
                st.session_state["briefing"] = briefing

briefing = st.session_state.get("briefing")
if briefing:
    st.success("Live APIs completed. Inspect the sources before relying on the briefing.")
    metrics = [
        ("Unique sources", str(len(briefing.evidence))),
        ("News sources", str(sum(item.result_type == "news" for item in briefing.evidence))),
        ("Retrieval", f"{briefing.retrieval_seconds:.1f}s"),
        ("Generation", f"{briefing.generation_seconds:.1f}s"),
    ]
    for column, (label, value) in zip(st.columns(4), metrics):
        column.metric(label, value)

report_tab, evidence_tab, api_tab, trace_tab, how_tab, try_tab = st.tabs(
    ["Briefing", "Evidence", "API analysis", "Live trace", "How it works", "Try it yourself"],
)
with report_tab:
    if briefing:
        st.markdown(source_linked_body(briefing))
        st.download_button(
            "Download briefing (.md)",
            data=briefing.markdown,
            file_name="webiq-insights.md",
            mime="text/markdown",
        )
        st.caption("Citation checks validate source numbers, not factual support. Review every important claim.")
    else:
        st.info("Enter a question or topic and generate a live briefing to see the results here.")

with evidence_tab:
    if briefing:
        st.caption(
            "Normalized, deduplicated evidence sent to the model. Passages are untrusted data, not instructions."
        )
        for index, item in enumerate(briefing.evidence, start=1):
            with st.container(border=True):
                st.markdown(f"**Source {index} / {item.result_type.upper()}**")
                st.link_button(item.title, item.url)
                st.caption(
                    f"{item.publisher or 'Publisher not supplied'} | "
                    f"Updated: {item.updated_at or 'not supplied; do not infer freshness'}"
                )
                st.text(item.content)
    else:
        st.info("After a run, inspect the source links, dates and exact evidence here.")

with api_tab:
    st.markdown("#### What the application sends")
    st.caption(
        "Request preview only. No API calls are made by opening this tab."
    )
    st.code('x-apikey: <server-side secret>\nContent-Type: application/json', language="http")
    for query in queries:
        for endpoint in ("web", "news"):
            st.code(f"POST https://api.microsoft.ai/v3/search/{endpoint}", language="http")
            st.json({
                "query": query,
                "maxResults": max_results,
                "language": "en",
                "region": region,
                "contentFormat": "passage",
                "maxLength": MAX_CONTENT_CHARACTERS,
            }, expanded=True)
    st.caption(
        "Quick mode uses the first upstream query. The full CLI sample uses three. "
        "The sample selects at most 18 unique source URLs; generation uses a 3,000-token completion limit."
    )
    if briefing:
        with st.expander("Normalized evidence (not raw HTTP JSON)"):
            st.json([asdict(item) for item in briefing.evidence], expanded=False)
    st.caption(
        "Live diagnostics include queries and returned URLs in the local terminal. "
        "Review reports and logs before sharing. API keys and raw service errors are not displayed."
    )

with trace_tab:
    st.subheader("Live trace")
    st.caption(
        "Web IQ queries, request timing/status, retries, returned URLs, selected sources "
        "and model-call diagnostics. This is the app/API trace, not Web IQ's internal "
        "ranking logic or the model's private reasoning."
    )
    saved_trace = st.session_state.get("run_trace_lines", [])
    if saved_trace:
        st.text(
            f"Last live run: {st.session_state['run_trace_topic']} "
            f"| {st.session_state['run_trace_state']}"
        )
        with st.container(height=360):
            st.code("\n".join(saved_trace), language="text")
        download_column, clear_column = st.columns(2)
        download_column.download_button(
            "Download trace (.log)",
            data="\n".join(saved_trace) + "\n",
            file_name="webiq-run-trace.log",
            mime="text/plain",
        )
        if clear_column.button("Clear trace"):
            for key in ("run_trace_lines", "run_trace_topic", "run_trace_state"):
                st.session_state.pop(key, None)
            st.rerun()
    else:
        st.info(
            "Generate a new live briefing to populate this trace. Earlier PowerShell logs "
            "are not imported."
        )
    st.caption(
        "Times are UTC. Only the latest live run is kept in this browser session; nothing "
        "is saved to disk unless you download it. Known credential values are redacted; "
        "headers, prompts and passages are excluded. Queries and URLs can still be sensitive: "
        "review the log before sharing."
    )

with how_tab:
    st.caption("HOW THE PIECES FIT")
    st.subheader("From a question to a briefing you can check")
    st.write(
        "Python collects relevant sources. Azure OpenAI turns them into a briefing. "
        "You check the evidence."
    )
    st.markdown(
        """<div class="iq-architecture" role="img"
        aria-label="Your question, local Python app, Web IQ Web and News, selected evidence,
        Azure OpenAI, then a cited briefing back in your browser.">
        <div class="iq-node"><small>01 / BROWSER</small>
        <strong>Your question</strong><span>Topic, dates and region</span></div>
        <div class="iq-node"><small>02 / YOUR COMPUTER</small>
        <strong>Python app</strong><span>Builds the search query</span></div>
        <div class="iq-node"><small>03 / CLOUD</small>
        <strong>Web IQ</strong><span>Searches Web + News</span></div>
        <div class="iq-node"><small>04 / YOUR COMPUTER</small>
        <strong>Evidence</strong><span>Keeps unique source passages</span></div>
        <div class="iq-node"><small>05 / CLOUD</small>
        <strong>Azure OpenAI</strong><span>Drafts from those passages</span></div>
        <div class="iq-node"><small>06 / BACK IN THE APP</small>
        <strong>Cited briefing</strong><span>Checks source numbers; you review</span></div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Browser and Python/Streamlit run locally; Web IQ and Azure OpenAI run "
        "in the cloud. No database or vector index."
    )
    for column, heading, detail in zip(
        st.columns(3),
        ("1 / Start", "2 / Retrieve", "3 / Write and verify"),
        (
            "Run the launcher, enter the Web IQ key in its hidden prompt, and open "
            "the browser. The model uses Azure sign-in.",
            "Quick mode makes two initial searches: Web and News. Python removes "
            "duplicate URLs and selects passages.",
            "Azure OpenAI drafts. Python checks citation numbers and builds the "
            "download. You verify the claims.",
        ),
    ):
        with column.container(border=True):
            st.markdown(f"**{heading}**")
            st.write(detail)
    st.code(".\\Start-Live.ps1", language="powershell")
    st.caption(
        "Live generation needs your consent. Citation checks do not prove factual accuracy."
    )

with try_tab:
    st.markdown("#### Your turn: change one thing")
    st.write(
        "Use the official sample with your own keys. Try a different topic, then compare "
        "a one-day window with seven days. Open one citation and check the claim."
    )
    st.link_button(
        "Open the official runnable sample",
        "https://github.com/microsoft/web-iq-samples/tree/main/samples/python/market-briefing",
    )
    st.code(
        'webiq-market-briefing "North American energy market" '
        '--query "North American energy market latest developments" '
        '--max-results 3 --lookback-days 7 --output reports\\demo.md',
        language="powershell",
    )
    st.caption(
        "Run after completing the official README setup. Explicit --query text is used verbatim; "
        "--lookback-days does not rewrite it or guarantee source publication dates."
    )
