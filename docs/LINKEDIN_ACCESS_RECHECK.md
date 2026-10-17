# LinkedIn access and public crawler review

12 October 2026. This follow-up preserves the original goal: live LinkedIn/X profile-email extraction and measured target-market coverage. It does not substitute ordinary company-site contacts for verified native LinkedIn profile access.

## Primary-source review

The current [joeyism/linkedin_scraper README](https://github.com/joeyism/linkedin_scraper) documents an async Playwright implementation and authenticated-session loading in its profile/company examples. Its documented quick-start requires creating a session. This supplies extraction/session machinery, not demonstrated anonymous recovery from the observed HTTP 999 response. It was reviewed without installing it, supplying account credentials or importing desktop cookies.

[Crawlee](https://github.com/apify/crawlee) documents persistent queues, resource scaling, HTTP/browser support, session/proxy management and multiple browser engines. Our existing crawler already implements bounded persistent work, normal browser rendering and source evidence, but that overlap is not a measured feature/performance equivalence claim. The repository does not by itself establish access to this denied profile or unpublished contact fields.

[Scrapling](https://github.com/D4Vinci/Scrapling) documents adaptive parsing, ordinary browser fetching and advanced stealth/challenge options. These options were not installed or enabled as a claimed LinkedIn solution. A project demonstrating other websites is not live LinkedIn profile-email acceptance evidence. No privileged bot identity, copied login state, proxy rotation or CAPTCHA/challenge handling was used.

LinkedIn distinguishes public-profile visibility from contact-field visibility in its [public profile guide](https://www.linkedin.com/help/linkedin/answer/a518980/) and [profile visibility guide](https://www.linkedin.com/help/linkedin/answer/a545600/what-people-can-see-on-your-profile). A public About section may contain an explicitly published address; the application's scoped reader can collect those visible strings. A generic contact-field extractor cannot supply a field that is unavailable to the current viewer. Protected contact panels remain excluded.

## Ordinary Firefox control

The previous comparison covered ordinary and managed Chromium. A separate ordinary headless Firefox guest session now checked exactly the previously observed `https://www.linkedin.com/in/kara-webs-403722422` URL once. Firefox also returned **HTTP 999**. The response was not parsed as profile/contact evidence. No fallback was promoted to production on that failure.

The first Firefox launch failed before any platform request with Windows error **14001**. The Windows SideBySide event identified a missing `mozglue` private assembly manifest, even though the DLL was present. A task-owned copy of the officially downloaded Playwright Firefox runtime received an adjacent private-assembly manifest for the existing DLL. `firefox.exe --version` then succeeded and the ordinary browser ran. Original shared browser binaries and Windows system settings were not modified. This local runtime repair is separate from platform access; it did not remove LinkedIn's denial.

The initial launch failure is not counted as a LinkedIn response. The successful subsequent test and runtime version check are referenced by `data/linkedin-firefox-check-latest.json` and `data/firefox-runtime-check.json`. The executable/runtime copies reside under ignored `data/tools` and are excluded from source releases. Firefox remains a diagnostic engine, not an enabled production dependency or a verified Linux/VPS implementation.

The operational database fingerprint remained unchanged; zero contacts were imported, zero recipient probes ran, zero messages were sent and no native source holds were cleared. The existing enabled FxEmbed source and paused/sending-disabled state remain in effect. Ruff/Python compilation passed for the diagnostic. Production implementation did not change after the prior 893-test suite; no full-suite rerun was needed for this diagnostic-only addition.

## Remaining gate

On this host, both ordinary browser engines tested the same native profile and were denied. The repository review did not establish a working free public LinkedIn source. Current state therefore still does not prove native LinkedIn email extraction, personal buyer-email yield or vendor-equivalent representative recall. A working public/appropriately authorized source or an external access/network-state change is required before those specific acceptance gates can pass. The X community-source and current official-site results remain separately scoped in [the enabled automatic research audit](FXEMBED_AUTOMATIC_RESEARCH.md).
