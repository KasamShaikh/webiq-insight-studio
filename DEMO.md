# Web IQ Insight Studio: from a question to a cited briefing

**Duration:** exactly five minutes. **Audience:** mixed technical/non-technical.
**Takeaway:** Web IQ retrieves evidence; a model drafts the briefing; a person
verifies the claims. A good demo makes those three responsibilities visible.

This is a local visual adaptation of the
[official Microsoft sample](https://github.com/microsoft/web-iq-samples/tree/main/samples/python/market-briefing),
based on upstream commit `89730ae`. The upstream CLI remains available.

## Run the live-only demo

From this repository's root in PowerShell:

```powershell
.\Start-Live.ps1
```

Enter the Web IQ key in the masked prompt, then open <http://127.0.0.1:8516>.
The visual app runs Live APIs only; there is no illustrative mode or mode selector.
Query controls are always available. The left-hand **Connection & setup** section
is collapsed by default. Allow billable usage before generating a briefing.

The launcher creates a sample-local virtual environment and installs dependencies
on first use. Python 3.11+ and configured service access are required. Stop the
server with Ctrl+C. Use `.\Start-Live.ps1 -Port 8517` if the default port is occupied.
For dependency setup alone, run `.\Start-Demo.ps1 -SetupOnly`; this makes no API calls.

## What is needed for live generation

| Requirement | Where it is used |
|---|---|
| Web IQ API key, entitled to **both Web and News** | `WEBIQ_API_KEY` environment variable |
| Azure OpenAI resource endpoint | `azure_openai.endpoint` in local configuration |
| Deployed chat-model **deployment name**, not just the model family | `azure_openai.deployment` |
| API version supported by that endpoint/model | `azure_openai.api_version` |
| Azure OpenAI API key (API-key mode only) | `AZURE_OPENAI_API_KEY` environment variable; not needed with `azure-cli` |
| Network access to both services and available quota | Live retrieval and generation |

### Existing-resource setup in this checkout

Copy the [model configuration template](samples/python/market-briefing/config.json)
to the Git-ignored `samples\python\market-briefing\config.local.json` and set
`"auth_mode": "azure-cli"`. In this mode **no Azure OpenAI API key is required**.
Your `az login` identity needs Cognitive Services OpenAI User (or
equivalent inference access) on the configured resource. The existing model's
key-authentication settings are not changed. Omitting `auth_mode` preserves the
original API-key behavior.

Connect your new Web IQ resource in the
[developer portal](https://webiq.microsoft.ai/profiles), accept any required terms,
and create a key with **both Web and News access**. Then run from this repository:

```powershell
.\Start-Live.ps1 -VerifyWebIQ
```

Paste the Web IQ key into the **masked local prompt**, not chat. The launcher
keeps it only in the server process environment, optionally verifies one Web
and one News request with no retries, and starts on <http://127.0.0.1:8516>.
Expand **Connection & setup** to inspect readiness. Close the launcher/server window to discard
the key; enter it again on a future launch. Nothing stores the key on disk.
The Web IQ verification is billable and does not generate a market report.

For the CLI with this configuration, add `--config config.local.json`.
Azure CLI sign-in is a local-development option; this is not a production
authentication configuration.

### Original two-key setup (alternative)

Use the [Web IQ key setup](https://learn.microsoft.com/en-us/web-iq/get-started/authentication)
and [official sample setup](samples/python/market-briefing/README.md).
The deployed model must support Chat Completions, a system message and
`max_completion_tokens`, as used by the original sample.
Running the app itself does not create Azure resources.

1. Stop the local server.
2. Copy the placeholder configuration:

   ```powershell
   Copy-Item .\samples\python\market-briefing\config.json `
       .\samples\python\market-briefing\config.local.json
   ```

3. Edit the new, Git-ignored file and replace all three placeholders. Keep API
   keys out of both configuration files.
4. Set the two keys in this PowerShell process. To avoid recording literal keys
   in command history, use masked prompts:

   ```powershell
   $webKey = Read-Host "Web IQ key (Web + News access)" -AsSecureString
   $modelKey = Read-Host "Azure OpenAI key" -AsSecureString
   $env:WEBIQ_API_KEY = [System.Net.NetworkCredential]::new('', $webKey).Password
   $env:AZURE_OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $modelKey).Password
   Remove-Variable webKey, modelKey
   .\Start-Demo.ps1
   ```

5. Select **Live APIs**, choose a topic, allow billable calls, then generate.

The setup indicator means only "configured locally", not "connected".
Do not paste keys into chat, screenshots, browser controls or source control.
On a shared computer, close the server and shell after use.

## What to show

- **Briefing:** four short sections; citations open the underlying sources.
- **Evidence:** source links, supplied metadata and the passages sent to the model.
  Missing dates are shown as missing, not inferred.
- **API analysis:** Web + News request previews with `contentFormat: passage`,
  `maxLength: 3000`, query text and limits. Keys are never included.
  Displayed evidence is normalized, not the raw HTTP response.
- **How it works:** a short startup guide and six-step architecture diagram,
  showing what runs locally, what runs in the cloud, and who checks the claims.
- **Live trace:** inspect the latest live run's queries, timings, status, retries
  and selected sources; download the log if needed. No historical terminal
  output or API events are invented. Review queries/URLs before sharing.
- **Try it yourself:** public source link and a small CLI command attendees can adapt.

Quick live mode uses one upstream query and three results per search: two
initial Web IQ requests, at most six usable unique sources, and one model
generation. The optional full mode uses three queries and the original
18-source selection cap. Retries can increase request counts and elapsed time.
The original CLI still defaults to three queries and five results per search.

## Five-minute speaker script

| Time | Show/do | Suggested words |
|---|---|---|
| 0:00-0:25 | Start on the main screen. | "A useful demo starts with a question attendees recognize: what changed in a topic I care about, and where is the evidence? In five minutes, we'll make that journey visible." |
| 0:25-0:55 | Point to Ask / Retrieve / Verify. | "Web IQ retrieves web and news passages. Azure OpenAI organizes that evidence into a briefing. The citations help us inspect the sources; they are not a guarantee of accuracy." |
| 0:55-1:25 | Show a completed live briefing prepared before the talk. Identify it as generated earlier. | "This briefing was generated earlier from live services. Let's follow one claim back to the retrieved evidence. I don't want a demo to hide where its information came from." |
| 1:25-2:10 | Open **API analysis**. Show one Web and one News payload. | "The core request is small: a question, a region, a result count and relevant passages. Quick mode makes two search calls. We ask for passages rather than full pages to keep the model's evidence focused." |
| 2:10-3:10 | Open **Briefing**, read one short finding, then its citation. Open **Evidence** and inspect the corresponding passage. | "Don't just admire the answer. Follow one claim back to its source. Check whether the passage actually supports it, and whether the date is suitable. The sample checks citation numbers, not whether every claim is true." |
| 3:10-3:50 | Point to the question, reporting window and collapsed connection settings. | "Three demo-design choices make this easy to follow: one familiar question, visible evidence, and one change the audience can try. Connection details stay out of the way until needed." |
| 3:50-4:35 | Open **Try it yourself**. Invite attendees to pick a topic. | "Your turn: choose a different topic. Try one day versus seven days, then open a citation. The public sample includes setup instructions. Live generation needs your own Web IQ and model access, with separate usage costs." |
| 4:35-5:00 | Return to the three steps. | "The pattern is simple: ask, retrieve, verify. Make the value obvious, make the evidence inspectable, and give people a small next step they can reproduce." |

The time ranges total 300 seconds. Do not do resource provisioning, installation
or credential entry on stage.

## Rehearsal and fallback

1. Run setup before the session and confirm the page loads.
2. Generate once beforehand (billable), inspect the sources,
   and download the Markdown. Keep that real report open in an editor as a
   **saved live report**, clearly identified as generated earlier.
3. For a strict five-minute slot, present the completed, saved live report.
   A fresh live generation is optional, not part of
   the timing guarantee. Upstream retries and multiple services can take minutes.
4. If you choose a live run on stage, keep a separate prepared report/window
   ready. Switch to it rather than repeatedly restarting requests. An in-flight
   request may still complete and incur charges.
5. Never describe a saved report as a response generated live on stage.

## Attendee reproduction using the public sample

The UI additions in this local checkout are not published to the upstream
repository. Attendees can reproduce the core briefing with the public CLI:

```powershell
git clone https://github.com/microsoft/web-iq-samples.git
Set-Location .\web-iq-samples\samples\python\market-briefing
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

Follow the upstream README to configure the endpoint, deployment, API version
and environment keys, then use an explicit focused query:

```powershell
.\.venv\Scripts\webiq-market-briefing.exe "North American energy market" `
    --query "North American energy market latest developments" `
    --max-results 3 --lookback-days 7 --output reports\demo.md
```

Explicit queries are used verbatim. `--lookback-days` sets the reporting window
but does not rewrite a supplied query. Even generated date-bounded queries do
not guarantee the publication dates of results.

## Validation and handling notes

From the sample directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo,dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

Offline tests use mocked services; they cannot establish live entitlements,
quota, model compatibility or latency. Live testing is a separate, billable
step requiring configured services.

The server listens only on `127.0.0.1`; it has no public-user authentication.
Streamlit usage statistics are disabled in the sample configuration.
Live diagnostics contain query text and source URLs; reports contain source
references. Review/redact both before sharing. Retrieved content is untrusted;
the model is instructed not to treat it as instructions. No automatic fallback
pretends a failed live call succeeded. Downloaded reports are not automatically
regenerated after changes.
