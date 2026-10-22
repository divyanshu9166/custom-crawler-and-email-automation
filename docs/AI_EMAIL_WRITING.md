**22 October pain-led initial email (prompt v17):** live drafts read like audit reports
("mobile loading observation and proposed website work", render-blocking jargon, no reason to
care, a second add-on offer and self-defeating hedges). The writer now receives a deterministic
`pitch_brief` for the strongest measured finding (`outreach/stakes.py`): a plain-English hook
naming the business and page, a verified reason it matters (Google's 2.5 s / 4 s main-content
thresholds and 90+ PageSpeed band, WCAG contrast minimums, or the direct consequence such as a
404 link being a dead end), the plain fix and its effort. The prompt orders the email as hook,
why it matters, fix, one small yes/no question, in 55-95 words with a 2-6 word subject and one
offer. New hard checks reject report-title subjects, sender-first openers, technical jargon,
defensive hedges and percentages absent from sources. All earlier truth validators are unchanged:
no claimed lost customers, sales or visitor behaviour. Greetings drop legal suffixes and SEO
taglines. A body written literally from each brief passes every validator (tests cover six finding
types). Live model output is not yet reviewed: regenerate a few drafts after deploying.

**19 October audit-input correction:** assessment and email writing now receive scoped
PageSpeed and render diagnostics separately from HTML source quotes. Failed/partial reports
cannot establish business pain. Valid measured observations need a report reference and test
qualification; audit changes/expiry invalidate approval. Existing edited drafts are preserved.
See [the live evidence audit](PAIN_POINT_AUDIT.md).

# Research-based email writing — correction, 11 October 2026

**18 October update:** current website prospects can now prepare source-validated
qualification and one initial AI email automatically, with bulk queueing and final message review.
The manual qualification editor is optional for routine supported cases. Unsupported evidence,
ownership and profile-only cases stay explicit exceptions. NVIDIA URL normalization, a preset
and synthetic connection check help diagnose HTTP 404. See [automatic preparation and VPS
update steps](AUTO_PREPARATION.md). Earlier manual-first descriptions below are the original
writer baseline; no template fallback or automatic outreach approval has been introduced.

The earlier operational writer interpolated reviewed observations into fixed email wording. That did not meet the requested individually researched email-writing behaviour. Historical copy previews and workflow tests did not establish live AI writing or natural model quality.

## Operational behaviour now

`campaigns.create_drafts` calls `email_writer.generate_sequence`. After current business/source qualification and recipient publication checks, a configured chat-completions model receives the reviewed business, selected single offer, observation, useful suggestion, optional sourced trigger/follow-up, geography and D2C source evidence. Website/profile status and research notes retain coverage uncertainty. Source pages are data, never instructions. Additional page context does not establish pain points or customer behaviour.

The model individually composes one initial email. Automatic follow-ups are disabled by default. Recipient email is not an input field; matching email addresses and the known recipient name are removed from the serialized research packet. The verified greeting is added locally; sender identity and opt-out footer remain deterministic. This limited redaction is not a guarantee that every page contains no other personal information; use an endpoint permitted to process the intended research data.

Every touch must carry source-support metadata with an exact quote from a supplied current source. The local validator requires exactly one message at step 0 and checks source IDs and quotes, basic copy/header limits, duplicate bodies, placeholders, incomplete/refused output and several obvious unsupported promises/completed-work claims. These structural checks cannot prove every claim's meaning or tone. **The operator must read the email and its sources before approval.**

Missing configuration, an unavailable/rate-limited provider, invalid output or a changed source/contact/qualification/draft/configuration causes an error and preserves existing drafts. There is **no template fallback**. Source and copy comparisons are repeated before dispatch and inside the final write transaction. Messages and their AI provenance are saved together: model, prompt version, input digest, source IDs, supporting quotes and saved message IDs. Draft creation neither schedules nor sends mail.

Old template sequences are labelled in Pipeline and blocked in the workflow map, approval route and frozen approval-context guard. Existing operational copy is not silently rewritten with test fixtures. Human edits remain available; final reviewed content is frozen by the existing approval snapshot.

## Configuration

Settings → **AI email writer** provides API base URL, model ID, password-style API-key field and timeout. The authenticated settings API preserves a saved key when left blank, supports explicit removal, excludes the key from responses/events, and persists configuration privately across restarts. Saving pauses sending and makes no provider call. HTTPS is required, except for a local inference endpoint.

Environment alternative: `DRAFT_API_URL`, `DRAFT_API_KEY`, `DRAFT_MODEL`, `DRAFT_TIMEOUT_SECONDS`. The default base URL is `https://integrate.api.nvidia.com/v1`; no model or key is enabled automatically. The implementation appends `/chat/completions`. Existing `OPENAI_*` settings remain solely for optional research suggestions; they do not write operational emails.

### NVIDIA Nemotron 3 Ultra configuration

For the model selected on 17 October 2026, use Settings → AI email writer:

| Field | Value |
| --- | --- |
| API base URL | `https://integrate.api.nvidia.com/v1` |
| Model ID | `nvidia/nemotron-3-ultra-550b-a55b` |
| API key | Generate it on NVIDIA Build, then paste into the dashboard password field |
| Request timeout | `180` seconds |

Save AI writer settings; no container restart is required. The key stays in the managed
settings file in the existing VPS volume and is excluded from API responses and events.
Leaving the key blank on a later save keeps it. Do not commit a key or paste it into chat.
Keep Sending OFF while generating and reviewing the first real research-based drafts.

The [official hosted inference reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b-infer)
documents `reasoning_effort: "none"`. For this exact hosted model only, the writer supplies
that field so its 1,200-token final-output budget is used for the final email JSON rather than
the provider's default high-effort reasoning. Other models/providers retain their existing
request parameters. Structured content, source quotes and unchanged research are still
validated before saving. Contract tests use a mock provider; real account availability,
quota, draft quality and latency require a live generation after configuring the key.

Use terms that permit the intended production use. NVIDIA's [API trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) distinguish evaluation from production; free-endpoint availability alone is not production permission. No real prospect data was sent to any AI endpoint in this correction.

## Verification and remaining acceptance

- Full regression: **617 passed**, no failures, one existing Starlette/httpx deprecation warning, 138.86 seconds. JUnit: `data/research-email-writing-tests.xml`.
- Thirty-six new writer tests use controlled HTTP-provider output through the actual writer, including research/recipient redaction, atomic provenance, missing configuration, provider errors, bad source quotes, invalid message structures, concurrent context changes, legacy approval blocking and private settings persistence. The remaining workflow tests use controlled fictional copy; they validate workflow guards and state transitions, not live model quality.
- Read-only Chromium checks on the normal preview: legacy hold, missing configuration, AI settings fields, simulated valid writer/review display, desktop/mobile and zero JavaScript errors. Operational tables and private configuration unchanged; zero provider calls and zero external messages. Report: `data/research-email-writing-ui-check.json`.
- Existing execution-visibility browser checks passed again for 17/11/35-node maps and selected-data/issue navigation.
- An isolated fictional provider fixture exercised the actual writer before the approval/revision/edit browser checks; it establishes UI transitions only. The offline demo remains explicitly template content and cannot be approved.

**Live model quality remains unverified.** Once an eligible provider/model/key is configured, review a varied US/UK Campaign A/B sample for factual grounding, useful suggestions, natural English and distinct follow-ups before accepting the writer for campaigns. No live endpoint availability, model quality, inbox delivery or client outcome is claimed by the controlled tests.

`draft_sequence`, `scripts/draft_review.py` and historical offer previews remain offline/demo tools. They are not called by the operational draft route and do not establish current AI-writing acceptance. Sending remains disabled and paused in the normal preview.
