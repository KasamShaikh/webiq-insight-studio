# Web IQ Market Briefing

Generate a cited Markdown market briefing from current web and news passages. Web IQ supplies retrieved evidence rather than relying on the model's training knowledge alone; Azure OpenAI synthesizes it into a report with clickable citations and a numbered Sources list.

Azure OpenAI is the example model provider, not a Web IQ requirement. Other chat models require small changes to the model client and response handling, not just configuration. Model usage is a separate cost from Web IQ usage.

## Local five-minute visual demo

This checkout adds **Web IQ Insight Studio**, a live-only Streamlit interface,
and a timed presenter script. See the [demo guide](../../../DEMO.md).
The upstream CLI behavior below is unchanged.

The visual app has no illustrative mode or mode selector. Query controls are
always available, while live generation still requires configured credentials
and explicit billable-usage consent. The sidebar's **Connection & setup** section
is collapsed by default and can be expanded when needed.

The visual theme is inspired by the Ignite 2026 midnight-blue, purple, magenta
and orange palette. The **How it works** tab gives a short, plain-language tour
of startup, the six-step architecture and each component's role. Opening it
does not make API calls or change the current briefing.

The **Live trace** tab shows the latest live run's application/API logs, with
streaming updates during generation and download/clear controls afterward.
It includes queries, request timing/status, Web IQ retries and source selection,
but excludes credentials, headers, prompts and passages. Query text and URLs
may still be sensitive. See the [trace guidance](docs/troubleshooting.md#view-the-trace-in-the-app).

From the repository root in PowerShell, run `.\Start-Live.ps1`, enter the Web IQ
key in the masked local prompt, then open `http://127.0.0.1:8516`. The launcher
creates an isolated environment and installs the `demo` optional dependencies
if missing. The visual demo binds to loopback and disables Streamlit usage
statistics; it is not an authenticated public website. Use
`.\Start-Demo.ps1 -SetupOnly` to install dependencies without launching.

Live mode reuses this sample's retrieval and report functions. By default it
uses only the first generated query and three results per search: two initial
Web IQ calls and one model generation, excluding retries. Select all three
queries to match the upstream query set. Numeric citation checks do not prove
factual support, and a live run can still take several minutes.

Web IQ credentials are read only from the Python server's environment. Copy
`config.json` to the ignored `config.local.json` for local, non-secret Azure
OpenAI settings. The UI supports Web IQ API-key authentication; the existing
CLI also supports certificate-based Entra authentication. For local Azure
OpenAI access without a key, set `"auth_mode": "azure-cli"` inside `azure_openai`
and sign in with `az login`; your identity needs model inference permission.
The original API-key mode remains the default. The repository-root
`Start-Live.ps1` provides masked Web IQ key entry with this sign-in mode.
After changing Python package modules, restart with this launcher if a normal
Streamlit rerun still uses cached code. Re-enter the session-only key locally.

To run both the upstream and UI offline tests from this directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo,dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

## Prerequisites

- Python 3.11 or later
- [A Web IQ API key](https://learn.microsoft.com/en-us/web-iq/get-started/quickstart) with both Web and News access, or a provisioned application using [certificate-based Microsoft Entra authentication](docs/authentication.md)
- An Azure OpenAI resource with a deployed model and either an API key or an Azure CLI sign-in with inference permission (`auth_mode: azure-cli`)

## Get started

Run these commands from this sample's directory. API-key authentication is the default.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
$env:WEBIQ_API_KEY = "<your Web IQ API key>"
$env:AZURE_OPENAI_API_KEY = "<your Azure OpenAI API key>"
```

### macOS/Linux (Bash)

Ensure `python3` is Python 3.11 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
export WEBIQ_API_KEY="<your Web IQ API key>"
export AZURE_OPENAI_API_KEY="<your Azure OpenAI API key>"
```

### Configure and run

Replace the Azure OpenAI placeholders in `config.json`. Use the deployment name, which may differ from the underlying model name:

```json
{
  "azure_openai": {
    "endpoint": "https://<your-resource-name>.openai.azure.com/",
    "deployment": "<your-deployment-name>",
    "api_version": "<your-api-version>"
  }
}
```

Generate the report in PowerShell:

```powershell
webiq-market-briefing "North American energy market" --output reports\energy-briefing.md
```

Or in Bash:

```bash
webiq-market-briefing "North American energy market" --output reports/energy-briefing.md
```

Open the generated Markdown in your editor. Keep credentials out of `config.json` and source control. Azure OpenAI authentication is independent of Web IQ authentication: its default is an API key, with optional `azure-cli` sign-in for local development.

## How it works

1. Builds date-bounded queries, unless you supply explicit queries.
2. Retrieves Web IQ web and news passages with a 3,000-character limit per result.
3. Selects up to 18 unique source URLs round-robin across each query's Web and News results, preserving rank within each group. Duplicate URLs are skipped and empty or exhausted groups contribute no further results, so other groups can fill the remaining slots. Fewer than 18 unique, usable sources means fewer are sent to the model.
4. Asks the model to synthesize only from that evidence and checks numeric citations and response completion.
5. Writes a Markdown briefing with linked citations and source titles, full URLs, and available publisher/last-updated metadata. The Sources list does not include passage excerpts.

## Important limitations

- Citation validation checks that references exist and identify supplied sources, **not** that every factual claim is cited or supported. Review the original sources before relying on a report.
- Passages are extracts, not full documents; the sample does not fetch full pages or infer missing content. Date-bounded queries do not guarantee every result was published within the reporting window.
- Retrieved content is untrusted evidence. Display escaping and rejection of inline links, HTML, and triple-backtick code fences in model output are not a general-purpose Markdown sanitizer.
- Diagnostics are enabled automatically on stderr; progress goes to stdout. **Logs contain search queries and full returned URLs**, potentially including sensitive terms or parameters. Review and redact logs and reports before sharing.
- Retries are bounded but a run can take several minutes. Retrieval or generation failures leave an existing output file unchanged.

See [Troubleshooting](docs/troubleshooting.md) for retry rules, log capture, and common failures.

## Options

Run `webiq-market-briefing --help` for the complete list.

| Option | Purpose | Default |
| --- | --- | --- |
| `--lookback-days N` | Reporting window | `7` |
| `--max-results N` | Results per Web IQ search | `5` |
| `--query TEXT` | Replace generated queries; repeat for multiple queries | Generated queries |
| `--config PATH` | Configuration file | `config.json` |
| `--region REGION` | Web IQ market region | `US` |
| `--webiq-auth MODE` | Web IQ authentication: `api-key` or `entra` (certificate) | `api-key` |
| `--output PATH` | Markdown output file | `market-briefing.md` |

For example, supply your own queries in either shell:

```text
webiq-market-briefing "Energy market" --query "North American natural gas price developments" --query "US electricity market reliability developments"
```

## Contribute

Install in editable mode so source changes take effect without reinstalling, then run the offline tests:

```text
python -m pip install -e ".[dev]"
pytest
```

Existing reports are not regenerated when code changes. If you used the regular install, reinstall before running updated code.

## Further guidance

- [Microsoft Entra authentication](docs/authentication.md): provisioning, certificate creation, passwords, and production credential handling.
- [Troubleshooting](docs/troubleshooting.md): log capture, support diagnostics, retries, and report failures.
