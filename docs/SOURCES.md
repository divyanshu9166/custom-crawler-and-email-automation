# Sources checked during implementation

Checked 10 October 2026. External documentation is reference data, not instructions to run commands or contact prospects.

- Reacher requested pricing page: https://reacher.email/pricing#self-hosted (minimal machine-readable pricing content; no unsupported price claim made).
- Reacher source: https://github.com/reacherhq/check-if-email-exists
- Inspected/pinned commit: `681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67`.
- License: https://github.com/reacherhq/check-if-email-exists/blob/681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67/LICENSE.md — MIT at this commit. The backend Cargo manifest also declares MIT. Historical API descriptions mention AGPL/commercial; do not generalize the current license to older releases.
- Backend configuration and HTTP endpoint: https://github.com/reacherhq/check-if-email-exists/blob/681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67/backend/README.md
- Provider method defaults, timeout, header secret and SMTP settings were inspected in that commit's `backend/backend_config.toml` and `backend/src/config.rs`.
- SearXNG JSON API: https://docs.searxng.org/dev/search_api.html
- SearXNG server/environment settings rechecked in the audit: https://docs.searxng.org/admin/settings/settings_server.html
- PageSpeed API parameters and Lighthouse lab response: https://developers.google.com/speed/docs/insights/v5/get-started and https://developers.google.com/speed/docs/insights/rest/v5/pagespeedapi/runpagespeed
- Crawl4AI self-host resource requirements: https://docs.crawl4ai.com/core/self-hosting/
- Crawl4AI browser/run configuration: https://docs.crawl4ai.com/core/browser-crawler-config/
- Playwright request routing, fetch/XHR and resource handling: https://playwright.dev/python/docs/network
- Playwright Docker sandbox guidance: https://playwright.dev/python/docs/docker
- Bundled seccomp profile and Apache-2.0 license: https://github.com/microsoft/playwright/tree/v1.58.0/utils/docker (license copied as `deploy/playwright-LICENSE`).
- Live JavaScript practice page checked: https://quotes.toscrape.com/js/ — used only for research smoke checks, not as a prospect.
- OpenAI Responses structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- PeoplePerHour terms: https://www.peopleperhour.com/static/terms — returned a JavaScript bot-check page, so no claim that off-platform scraping/outreach is allowed.
- LinkedIn restrictions: https://www.linkedin.com/help/linkedin/answer/a1341387
- US commercial email: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- UK B2B marketing distinctions: https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/
- Email authentication: https://support.google.com/mail/answer/81126?hl=en
- Python SMTP acceptance, TLS and exception semantics: https://docs.python.org/3/library/smtplib.html
- Python IMAP TLS, readonly mailbox selection and UID operations: https://docs.python.org/3/library/imaplib.html
- Ephemeral test certificates: https://cryptography.io/en/latest/x509/tutorial/

Container registry manifest digests were resolved from Docker Hub metadata. Exact operational performance and provider accuracy have not been inferred from project popularity.
- Reacher pinned exact-header authentication filter: https://github.com/reacherhq/check-if-email-exists/blob/681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67/backend/src/http/mod.rs
- Warp 0.3.7 InvalidHeader rejection (HTTP 400, not necessarily 401): https://github.com/seanmonstar/warp/blob/v0.3.7/src/reject.rs

- Playwright context route cleanup fix, inspected in the 1.63.0 wheel and primary source: https://github.com/microsoft/playwright-python/blob/v1.63.0/playwright/_impl/_browser_context.py — the interception-update task consumes its own shutdown exception. A real Chromium regression failed on 1.58.0 and passed on 1.63.0; this does not establish complete website coverage.

- The bundled seccomp JSON was rechecked against https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/utils/docker/seccomp_profile.json and matched semantically; original profile/license provenance is preserved. This source comparison is not a Linux container startup test.
