# Research → prepare → review emails

The qualification form remains available as an advanced editor. Routine website prospects
can now use **Prepare emails**, or the default-enabled **Automatically prepare qualification
and AI drafts after research** control under Settings → Research & email preparation.
The worker waits for queued/running website/contact/professional/social research before
automatically scheduling preparation. It uses the existing configured AI writer; it does
not require a separate research-AI key. Worker must be ON; Sending can remain OFF.

## What happens

1. Check current official business evidence, published contact ownership, suppression,
   contact history and pending source jobs. No address is guessed or automatically imported
   from an unreviewed external/profile candidate.
2. Prioritize up to twelve saved official pages (home/about/contact/services/products first)
   and send bounded context to the configured model. Remove email strings from that input.
   Include the original discovery query when available so segment relevance is considered.
3. Ask the model for either a hold or one source-backed qualification/offer. Validate the
   exact country/opportunity quotes against current pages, country/timezone, source ownership,
   business type evidence, campaign goal and D2C/channel context. Reject absence/loss claims,
   helpdesk/recruitment-only sales pitches and generic chatbot pitches when captured text
   already identifies a chatbot. Partial captures never establish that a feature is missing.
4. Apply the same qualification gates as the advanced editor. Record `research_ai` as the
   qualification method; this is not a record of human review or confirmed buying authority.
5. Generate four individual, source-supported AI drafts. Every message stays `draft` with
   no due date. Preserve existing messages, human edits and active/held/replied/closed contacts.
   Source/contact/configuration changes during generation discard stale output.
6. Show **Review email drafts** with an evidence summary. Recipient relevance, current
   source/offer accuracy, all four messages and outreach eligibility still require final
   operator approval. Reacher freshness, sender/mailbox configuration and existing send gates
   remain independently enforced. Preparation never enables/resumes sending or approves copy.

AI reasoning is fallible. Matching quotes do not prove that an inference is useful, that a
buyer has authority, that a feature is absent or that conversions will increase. The final
review is necessary; this feature removes repetitive data copying rather than guaranteeing
sales relevance. Profile-only ownership/activity/search-limit review, uncertain US timezone,
missing contacts, weak business fit and insufficient context remain explicit exceptions.

## Existing prospects and bulk work

- Pipeline → **Prepare emails** handles the selected prospect.
- **Prepare pending emails** queues up to 100 review/qualified prospects per page; use
  **Prepare next batch** to advance. Existing queued jobs deduplicate and existing messages
  are skipped. Per-prospect reasons explain missing evidence/history exceptions.
- The **Preparation queue** filter shows drafts-ready, preparing and attention states.
- Completion polls without erasing unsaved form edits. If edits exist, use Refresh when
  ready. Inspect individual preparation errors under the prospect or Operations.
- Identical evidence after an exception is not automatically retried on every supplementary
  event. After resolving configuration or evidence, explicitly use Prepare emails to retry.
- Re-crawling/re-qualifying after drafts are ready is an explicit operation; preparation
  will not replace human work automatically. Existing drafts can be edited/regenerated
  through the established reviewed writing controls.

## NVIDIA HTTP 404

The documented hosted route is `POST https://integrate.api.nvidia.com/v1/chat/completions`.
See [NVIDIA's LLM API reference](https://docs.api.nvidia.com/nim/reference/llm-apis).

The writer accepts the API base URL, NVIDIA host root, or complete chat endpoint without
appending duplicate suffixes. It preserves the selected model and never silently switches
providers/models or falls back to templates. HTTP 404 can also mean the model is unavailable
to the account; path normalization alone cannot establish account/model access.

In Settings → AI email writer:

1. **Use NVIDIA Nemotron settings** fills the URL, selected
   `nvidia/nemotron-3-ultra-550b-a55b` model and 180-second timeout. It does not change the
   saved key or call/save the provider automatically.
2. Save the writer settings (leave a stored key blank to preserve it).
3. **Test AI connection** sends synthetic text only, with no prospect data or outreach.
   This may use provider quota. Success checks the selected chat route/account at that
   moment; it does not establish JSON-writing quality, future quota or email delivery.
4. If HTTP 404 persists, check the account's currently supported exact model ID/access in
   NVIDIA's API catalog. Do not infer that the prospect qualification caused that response.

## Deploy on the existing VPS

Keep Worker and Sending OFF during update. Preserve existing volumes and browser profile.

```sh
cd ~/custom-crawler-and-email-automation && git pull --ff-only
```

```sh
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml build --build-arg PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.13-slim-bookworm app && sudo docker compose -f compose.yaml -f compose.platform-browser.yaml up -d --no-build --wait --wait-timeout 120 app
```

```sh
curl -fsS --max-time 10 http://127.0.0.1:8000/health
```

Hard refresh the dashboard. Test the saved AI connection first; then enable Worker while
leaving Sending OFF. Existing prospects use Prepare emails or the batch action. Future
completed research schedules preparation automatically when the feature and writer are
configured. No new database service or Docker daemon/network change is needed.

Tests use isolated databases, fictional providers and real Chromium desktop/mobile fixtures.
See VALIDATION.md for results. The developer environment cannot establish the VPS's live
NVIDIA account access, active LinkedIn coverage, Reacher readiness or actual delivery.
