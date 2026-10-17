# Research-based email writing — correction, 11 October 2026

The earlier operational writer interpolated reviewed observations into fixed email wording. That did not meet the requested individually researched email-writing behaviour. Historical copy previews and workflow tests did not establish live AI writing or natural model quality.

## Operational behaviour now

`campaigns.create_drafts` calls `email_writer.generate_sequence`. After current business/source qualification and recipient publication checks, a configured chat-completions model receives the reviewed business, selected single offer, observation, useful suggestion, optional sourced trigger/follow-up, geography and D2C source evidence. Website/profile status and research notes retain coverage uncertainty. Source pages are data, never instructions. Additional page context does not establish pain points or customer behaviour.

The model individually composes the initial email and three distinct follow-ups. Recipient email is not an input field; matching email addresses and the known recipient name are removed from the serialized research packet. The verified greeting is added locally; sender identity and opt-out footer remain deterministic. This limited redaction is not a guarantee that every page contains no other personal information; use an endpoint permitted to process the intended research data.

Every touch must carry source-support metadata with an exact quote from a supplied current source. The local validator checks all four unique steps, source IDs and quotes, basic copy/header limits, duplicate bodies, placeholders, incomplete/refused output and several obvious unsupported promises/completed-work claims. These structural checks cannot prove every claim's meaning or tone. **The operator must read all four emails and their sources before approval.**

Missing configuration, an unavailable/rate-limited provider, invalid output or a changed source/contact/qualification/draft/configuration causes an error and preserves existing drafts. There is **no template fallback**. Source and copy comparisons are repeated before dispatch and inside the final write transaction. Messages and their AI provenance are saved together: model, prompt version, input digest, source IDs, supporting quotes and saved message IDs. Draft creation neither schedules nor sends mail.

Old template sequences are labelled in Pipeline and blocked in the workflow map, approval route and frozen approval-context guard. Existing operational copy is not silently rewritten with test fixtures. Human edits remain available; final reviewed content is frozen by the existing approval snapshot.

## Configuration

Settings → **AI email writer** provides API base URL, model ID, password-style API-key field and timeout. The authenticated settings API preserves a saved key when left blank, supports explicit removal, excludes the key from responses/events, and persists configuration privately across restarts. Saving pauses sending and makes no provider call. HTTPS is required, except for a local inference endpoint.

Environment alternative: `DRAFT_API_URL`, `DRAFT_API_KEY`, `DRAFT_MODEL`, `DRAFT_TIMEOUT_SECONDS`. The default base URL is `https://integrate.api.nvidia.com/v1`; no model or key is enabled automatically. The implementation appends `/chat/completions`. Existing `OPENAI_*` settings remain solely for optional research suggestions; they do not write operational emails.

Use terms that permit the intended production use. NVIDIA's [API trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) distinguish evaluation from production; free-endpoint availability alone is not production permission. No real prospect data was sent to any AI endpoint in this correction.

## Verification and remaining acceptance

- Full regression: **617 passed**, no failures, one existing Starlette/httpx deprecation warning, 138.86 seconds. JUnit: `data/research-email-writing-tests.xml`.
- Thirty-six new writer tests use controlled HTTP-provider output through the actual writer, including research/recipient redaction, atomic provenance, missing configuration, provider errors, bad source quotes, invalid message structures, concurrent context changes, legacy approval blocking and private settings persistence. The remaining workflow tests use controlled fictional copy; they validate workflow guards and state transitions, not live model quality.
- Read-only Chromium checks on the normal preview: legacy hold, missing configuration, AI settings fields, simulated valid writer/review display, desktop/mobile and zero JavaScript errors. Operational tables and private configuration unchanged; zero provider calls and zero external messages. Report: `data/research-email-writing-ui-check.json`.
- Existing execution-visibility browser checks passed again for 17/11/35-node maps and selected-data/issue navigation.
- An isolated fictional provider fixture exercised the actual writer before the approval/revision/edit browser checks; it establishes UI transitions only. The offline demo remains explicitly template content and cannot be approved.

**Live model quality remains unverified.** Once an eligible provider/model/key is configured, review a varied US/UK Campaign A/B sample for factual grounding, useful suggestions, natural English and distinct follow-ups before accepting the writer for campaigns. No live endpoint availability, model quality, inbox delivery or client outcome is claimed by the controlled tests.

`draft_sequence`, `scripts/draft_review.py` and historical offer previews remain offline/demo tools. They are not called by the operational draft route and do not establish current AI-writing acceptance. Sending remains disabled and paused in the normal preview.
