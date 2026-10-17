# Automatic prospect discovery

The system researches public platform signals automatically without Apify or Apollo. A private SearXNG backend expands each business query across configured sources, resolves candidates to company websites, then queues the existing deep browser research and public-email extraction.

1. Select Campaign A/B and US/UK. The market adds country context when absent and chooses its English search locale.
2. Search business websites and indexed LinkedIn company pages, X, PeoplePerHour, Clutch and Crunchbase. Configure up to eight domains with `DISCOVERY_PLATFORMS`. Results lacking meaningful query terms are recorded and excluded.
3. Read a platform page only when robots permits access. Login/password or challenge pages stay unavailable. Indexed title/snippet/hash are labelled as indexed signals; retrieval time is not publication date.
4. Resolve websites through published links, reciprocal profile links or name/domain/content correlation. Multiple plausible companies stay unresolved. Selecting a UK regional brand domain does not prove operating geography or identity.
5. Persist candidates, progress and signals as they arrive; deduplicate websites, apply the company limit and queue research. Later cancellation retains earlier findings. Signal budgets/search pacing do not reduce the website crawler's rendering scope.
6. Research official websites with robots/sitemaps/Chromium. Import sourced company-domain emails; hold official other-domain inboxes for ownership review. Indexed/platform emails stay held and are not automatically imported or probed.
7. Review current official evidence, geography, buyer/owner relevance, one offer and drafts. Reacher verification and existing approval/send/reply/opt-out gates still apply.

Company details show source cards. Operations shows engine failures, unresolved signals and progress. Searches can run once or recur. Logged-in social pages and platform messaging are not automated. No guessed/unpublished email or announcement date is introduced.

## Local development and verification

The dashboard has a sign-in form and signed session cookie; browser Basic-auth prompts are no longer required. Credentials stay in `.env`. HttpOnly/SameSite cookies, HTTPS Secure cookies, expiry, same-origin writes, throttling and API authentication are tested. Basic/Bearer clients remain supported.

Run `scripts/local_search.py --install` once, then `scripts/local_search.py` for the pinned free development backend on loopback port 8888. It uses a separate private environment and checks archive paths/size/source provenance. Windows uses a narrow POSIX diagnostic import shim with Valkey disabled. Production remains Linux/container deployment requiring separate acceptance.

Live searches returned business results here; some engines returned CAPTCHA, access denial or rate limits. Failures are reported, not bypassed. Neither free software nor an engine failure proves that an email does/does not exist.

The normal development database contains an unqualified IMAGE Skincare UK candidate from automatic discovery. Its website research captured/rendered 30 pages, desktop/mobile screenshots completed, and two sourced company-domain contacts were saved. Both verification jobs failed with `HTTPStatusError` at the configured localhost endpoint; verdicts remain unknown. No message or approved sequence exists.

A separate live LinkedIn company-signal lookup resolved to `imageskincare.co.uk` as a name/domain/content candidate. Another X brand lookup stayed ambiguous when its putative official site was unavailable; a reseller was not substituted. These are examples, not all-market/platform acceptance. The old 50-domain benchmark remains separate.

See [the dated check](platform-discovery-check.json). Actual Reacher accuracy, independent recipient approval, mailbox/domain/public HTTPS, controlled sending and VPS/container measurements remain unfinished.

Unresolved named business profiles now enter the separate [profile-first prospect branch](PROFILE_PROSPECTS.md). This does not turn indexed snippets or blocked profile pages into qualified business/contact evidence.
