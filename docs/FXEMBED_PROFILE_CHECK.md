# Free community X profile check

12 October 2026. The user explicitly authorized a live test of the free FxEmbed community endpoint on three profiles. No official X developer key, account sign-in or paid subscription was used. This is a third-party source, not direct first-party X access.

## Actual results

The test requested the documented `https://api.fxtwitter.com/2/profile/{handle}` endpoint once for each of three previously observed profiles with the application's declared `OutreachResearchBot` user agent. Each returned HTTP 200, provider code 200, a matching profile handle/URL, an explicitly public profile and a non-empty bio.

| Profile | Bio returned | Email strings in returned bio | Scope |
|---|---|---|---|
| `ssbmGooms` / Gooms | 158 characters | 1 | Personal-profile transport control; not a qualified target buyer |
| `SonriaUK` / Sonria Dental Clinic | 159 characters | 0 | Previously observed UK business |
| `musicplaza_la` / Music Plaza | 128 characters | 1 | Previously observed US business |

These are **two real email candidates from three community profile responses**, including one personal-profile bio. They were extracted from actual published bio strings rather than generated names/domain patterns. Successful retrieval does not verify mailbox existence, current company, buying role, outreach eligibility or current first-party publication. The response `Date` is retrieval metadata, not proof of the upstream profile's last update; no trustworthy upstream freshness assertion was observed.

The public HTML-only mirror check had weaker results: one profile returned only handle metadata, while Sonria's public HTML said the user did not exist despite the subsequent API returning its profile. This discrepancy confirms that HTTP 200 and mirror HTML alone cannot qualify profile identity or absence. The API route and the HTML route are different access paths and may have different cache/upstream behavior.

The operational database fingerprint stayed unchanged. **Zero contacts were imported, zero recipient probes ran and zero messages were sent.** The private dated report and bio excerpts/candidates are referenced by `data/fxembed-profile-check-latest.json`; runtime data is excluded from the source archive. The test made exactly the three authorized profile requests, with no native LinkedIn/X retries.

## Optional integration

`outreach/fxembed.py` supplies a bounded, fixed-host, no-credential adapter. `FXEMBED_PROFILES_ENABLED=false` is the default and remains unchanged in the normal preview. Enabling it makes company-associated professional research collect a separate community hint after a native X profile cannot be captured. LinkedIn routes are rejected by this adapter.

The adapter validates the provider code, profile type, exact handle and official X/Twitter profile URL, explicit `protected=false`, and bounded bio/name fields. Missing/private/unknown-visibility, malformed and wrong-identity responses cannot produce email evidence. Only the description contributes email candidates; avatar, location, unrelated fields and error messages cannot supply contacts. Requests are paced/coalesced and cached with their original retrieval timestamp. Missing profiles do not hold unrelated profiles; native HTTP and provider-level denials stop further calls for a cooldown. No redirects, cookies, tokens or account credentials are used.

Native `professional_capture` records retain their denial and empty publication evidence. Mirror hints are stored in the professional research report's `community_profile_hints` and displayed separately in the dashboard, with provenance and cache state. They cannot pass the native source-review/import route or enter first-party geography/offer evidence, Reacher jobs or sending. Current official company evidence can be researched independently through the existing crawler; mirror data does not replace that source proof.

## Remaining scope

This establishes a working third-party X bio-email research path for this small mixed-relevance sample. It does not fix LinkedIn HTTP 999, make native X HTTP 403 disappear, establish representative client coverage, or prove Apollo/Apify-equivalent recall. Actual unattended VPS acceptance and deployment source choice remain separate from this local test. No production fallback was enabled by the test authorization.

Primary sources: [FxEmbed project](https://github.com/FxEmbed/FxEmbed), [documented profile endpoint](https://docs.fxembed.com/api/twitter/operations/2profilehandle/), [project FAQ and shared mirror domains](https://docs.fxembed.com/guide/faq/). Self-hosting this entire external project was not performed and is not equivalent to removing its upstream access dependency.

## Verification

**885 tests passed in 185.31 seconds**, with one existing Starlette/httpx deprecation warning. Eighteen new checks cover public/private visibility, exact identity, provider errors under HTTP 200, disabled-mode zero requests, fixed-source/no-credential transport, coalesced/cache-preserving reads, 429 and provider-code cooldowns, missing-profile independence, response size bounds, and company-pipeline isolation from contacts/evidence/jobs/messages. The focused new-adapter/professional set passed 55 tests.

The Chromium UI smoke test exercised separately labelled mirror bio/email/source/cache display and escaped script-like bio content with zero JavaScript errors, alongside existing desktop/mobile flows. The normal preview restarted with the fallback explicitly disabled; its read-only desktop/mobile verification preserved operational rows/settings and made zero provider calls/messages. Ruff, Python compilation and JavaScript syntax checks passed. Runtime reports and bio/email data are not copied into public source documents or the release archive.

## Current official-source and inbox-purpose follow-up

The saved bios explicitly describe the two candidates as **customer support** (Gooms) and **order inquiries** (Music Plaza). A personal-profile bio containing an email is not proof that the address is a personal owner/marketing-buyer inbox. The adapter now retains exact label context and classifies the observed inbox purpose without assigning buying authority. Unknown/ambiguous labels remain unknown or multiple-purpose; all buyer-contact verification flags remain false. The dashboard exposes this distinction next to each mirror candidate.

`scripts/verify_profile_email_corroboration_live.py` made no further FxEmbed profile requests. The current official Music Plaza help page captured by the normal crawler independently contained the same email, in customer-order support context: `https://www.musicplaza.com/apps/help-center`. This verifies current publication of the company support address, not mailbox existence or decision-maker suitability. The Music Plaza source hash and exact context are in the private report referenced by `data/profile-email-corroboration-latest.json`.

Gooms' store URL came directly from the saved bio. Its HTTP page was unavailable; a separate same-host HTTPS check also returned `ConnectError`. Current publication on that store therefore remains uncorroborated. The failed fetch does not prove website absence or an inactive business. A search result for Down Back Club's older organizer page is a further identity/research hint, not proof that this separate controller-support address is a current business-buyer inbox.

A further public HTML-only X mirror check stopped at **HTTP 403 on its robots resource**, before any profile-page capture. No HTML-only adapter was enabled based on that failed check. The existing API sample remains the actual working third-party path.

The updated adapter/professional tests passed **61 checks**, including six new explicit-purpose/unknown/ambiguous-label cases. Chromium smoke passed the inbox-purpose and unverified-buyer display with zero JavaScript errors. Ruff and JavaScript syntax passed. These are the focused follow-up checks; the preceding full-suite count of 885 remains the baseline before the additive purpose labels. The saved-data analysis in `data/profile-email-routing-check.json` preserves the original source retrieval times. Zero new profile API calls, contacts, recipient probes or messages occurred.
