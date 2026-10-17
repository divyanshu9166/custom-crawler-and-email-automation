# Offer suggestions use business-facing source context

Current saved-source replay exposed privacy-policy text and bare navigation links being treated as useful offer signals. The proposal selector now excludes legal boilerplate, rejected marketplace records and foreign company pages. Generic contact labels need an actual inquiry context. FAQ labels need question content or an explicit topic. Booking and purchase invitations take precedence over weak contact labels and shopping banners, using service-specific page routes. Quotes remain exact source excerpts and no longer begin or end inside words.

Existing automatic suggestions are retained as history. For an unqualified company, the dashboard fills the review form from current accepted suggestions; if its former suggestion is rejected and no replacement exists, the quote stays empty. Reviewed company offers are preserved. Reading the form does not qualify a company, change its saved findings, create drafts or approve outreach.

## Executed evidence

The full suite passed **506 tests in 139.41 seconds**, with one existing Starlette/httpx dependency warning. Fifteen source-quality cases cover legal sources, marketplace/foreign pages, menu labels, stronger booking/product evidence, exact quote boundaries and explicit phone contact. Ten defects were reproduced before the initial correction. Additional FAQ-footer and shopping-banner cases were added after inspecting real saved pages. The focused discovery/offer suite passed 79 cases.

Full isolated Chromium smoke passed. The second-workflow browser check exercised all 15 service-selection statuses, Campaign A/B forms and artifacts, plus legacy automatic-prefill replacement and empty-source holding without record mutation. Third-workflow forms and the normal 35-node / 46-connection dashboard also passed. Normal automatic form prefills were checked for four existing candidates; all nine contact verification buttons and eleven prospect maps were inspected. No JavaScript errors or layout overflow occurred, and private configuration and operational records were unchanged.

## Real saved-source replay

Eleven existing candidates were replayed using their current saved public pages. Eight produced reviewable suggestions and four-touch preview copy, totaling **32 unsent preview messages**. This operation made no network requests, executed no verification, saved no messages and left normal records unchanged. It did not discover new leads, confirm country/buyer/service fit, select a final primary offer or establish mailbox existence.

Examples of changed source selection:

- Dental Clinic London uses its actual booking page for the inquiry offer.
- Portland Coffee Roasters no longer receives a chatbot suggestion from privacy-policy text.
- SmartRoof no longer receives a chatbot suggestion from its FAQ footer label.
- Skindays uses product purchase evidence rather than an unrelated shopping banner on a support page.
- The rejected IndiaMART record produces no company-service suggestions.

The [saved-source results](offer-source-quality-check.json) include chosen source URLs, page hashes, capture dates, exact quotes and preview copy. [Draft previews](OFFER_DRAFT_PREVIEWS.md) are review material only; stored discovery names and all contact/buyer assumptions remain subject to review. No suggested observation establishes a conversion problem or promises sales growth.

Real search/crawl yield, restricted-platform access, a running Reacher backend, external delivery and actual paid-client outcomes remain unaccepted. Sending stays disabled and globally paused.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/offer-source-quality-tests.xml
.\.venv\Scripts\python.exe scripts/verify_complete_workflow.py
.\.venv\Scripts\python.exe scripts/verify_offer_sources_saved.py
.\.venv\Scripts\python.exe scripts/verify_second_workflow_ui.py
.\.venv\Scripts\python.exe scripts/verify_complete_workflow_ui.py
```

The saved-source replay and normal dashboard inspection require the existing local database. The second-workflow UI check uses a separate fictional database with sending and workers disabled.
