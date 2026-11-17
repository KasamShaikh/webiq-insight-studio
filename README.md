# Web IQ Insight Studio

**Ask a question. Explore live evidence. Create a briefing you can verify.**

A live-only Python/Streamlit demo combining Microsoft Web IQ Web + News search
with Azure OpenAI. Built for a short, practical demonstration with an
Ignite-inspired visual theme.

## What you can explore

- **Briefing:** a source-cited summary with a Markdown download.
- **Evidence:** the selected source links, available dates and retrieved passages.
- **API analysis:** Web IQ request previews without credentials.
- **Live trace:** streaming query, timing, status, retry and source-selection
  diagnostics, with download and clear controls.
- **How it works:** a short architecture and component-flow explanation.
- **Try it yourself:** a reproducible starting point for your own queries.

The interface uses Live APIs only. Connection details are collapsed by default,
and generation requires explicit billable-usage consent.

## Architecture

```text
Your question
    -> Local Python / Streamlit app
    -> Web IQ Web + News search
    -> Selected, deduplicated evidence
    -> Azure OpenAI
    -> Cited briefing + source review
```

The browser and Python app run on your computer. Web IQ and Azure OpenAI are
cloud services. No database or vector index is required.

## Prerequisites

- Windows PowerShell and Python 3.11+ for the included launchers.
- Azure CLI, signed in to the tenant containing your model deployment.
- A Web IQ API key with **both Web and News access**.
- An Azure OpenAI deployment supporting Chat Completions, system messages and
  `max_completion_tokens`.
- Inference permission on the Azure OpenAI resource, such as
  **Cognitive Services OpenAI User**, for your signed-in identity.

Web IQ and model usage are billed separately. Quick mode makes two initial Web
IQ searches and one model generation; retries can add calls and latency.

## Quick start

```powershell
git clone https://github.com/KasamShaikh/webiq-insight-studio.git
Set-Location .\webiq-insight-studio
.\Start-Demo.ps1 -SetupOnly
Copy-Item .\samples\python\market-briefing\config.json `
    .\samples\python\market-briefing\config.local.json
```

Edit the new, Git-ignored configuration with your own **non-secret** model
settings. Use the actual deployment name, which may differ from the model name:

```json
{
  "azure_openai": {
    "endpoint": "https://<your-resource-name>.openai.azure.com/",
    "deployment": "<your-deployment-name>",
    "api_version": "2024-10-21",
    "auth_mode": "azure-cli"
  }
}
```

Use an API version supported by your deployment. Then:

```powershell
az login
.\Start-Live.ps1
```

Paste your Web IQ key into the **masked local prompt**, not a source file or
chat. Open **http://127.0.0.1:8516**, enter a question or topic, allow billable
requests and select **Generate live briefing**.

Azure OpenAI uses your Azure CLI sign-in; this configuration needs no model API
key. The Web IQ key is kept only in the launcher/server process environment.
Closing that window discards it, so enter it again on a future launch.

If the port is occupied, use `.\Start-Live.ps1 -Port 8517`. The optional
`-VerifyWebIQ` switch performs one Web and one News access check; those checks
are billable and do not generate a briefing.

## Five-minute presentation

See the [presenter guide](DEMO.md) for the timed script, rehearsal checklist,
credential setup and saved-report fallback.

The implementation remains under
[`samples/python/market-briefing`](samples/python/market-briefing) to preserve
the upstream package, launch paths and CLI compatibility.

## Run offline tests

After running setup, use:

```powershell
Set-Location .\samples\python\market-briefing
.\.venv\Scripts\python.exe -m pip install -e ".[demo,dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use mocked services. They do not prove live entitlements, quota, model
compatibility or end-to-end latency.

## Privacy and limitations

- Keys, local configuration, virtual environments, reports and logs are
  excluded from Git. Never commit credentials or certificates.
- Live traces are retained in server memory for the current browser session.
  Downloads are explicit; queries and source URLs may still be sensitive.
- Authentication headers, model prompts, passages and raw exception details
  are excluded from diagnostic logs. The Evidence tab intentionally shows the
  selected passages for inspection.
- Citation checks validate source numbers, not whether every claim is true.
  Date-bounded queries do not guarantee source publication dates.
- The app listens only on `127.0.0.1`. It has no public-user authentication and
  is an educational demo, not a production reference architecture.

Read the [sample documentation](samples/python/market-briefing/README.md) and
[troubleshooting guide](samples/python/market-briefing/docs/troubleshooting.md)
for details.

## Attribution and license

Derived from Microsoft's
[Web IQ market-briefing sample](https://github.com/microsoft/web-iq-samples/tree/89730ae/samples/python/market-briefing),
based on upstream commit `89730ae`. This repository adds the live-only Studio
interface, Ignite-inspired styling, in-app tracing and presentation workflow.

The original source notices and [MIT license](LICENSE.txt) are preserved.
This is an independent demo adaptation, not an official Microsoft release.
