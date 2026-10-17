# Contact-source recovery without a working search index

Latest publication-gate recheck refreshed the same two official pages per candidate: Skindays returned four previously known inboxes, all with current publication proof; SmartRoof returned none. Both remained partial. See [contact-source integrity](CONTACT_PUBLICATION.md).

Contact recovery now combines search results with current saved official contact/about/team URLs and contact routes retained in the crawl checkpoint. Uncaptured routes take precedence over refreshing already captured routes within the same priority. Every selected route records its origin. Company-domain checks, robots controls and fresh published-email evidence still apply; catalog/editorial URLs containing words such as "about" or "team" are not mistaken for saved contact routes.

If these sources provide no routes, the crawler starts at the official homepage and follows observed links within the existing six-page recovery limit. It does not guess contact URLs or emails. This navigation pass skips sitemap expansion; the main crawler's 30-page budget and sitemap research are unchanged. Partial captures remain partial, and unavailable pages are held with diagnostics rather than labeled successful.

## Real official-page check

The reproducible check deliberately supplied empty search results while retaining real HTTP/Chromium requests to two existing candidate websites. It copied saved evidence into an isolated database; it did not run discovery, verification, sending or a worker against that database.

| Existing candidate | Refreshed official pages | Published email candidates recovered | Status |
| --- | ---: | ---: | --- |
| Skindays | 2 | 4 | Partial |
| SmartRoof | 2 | 0 | Partial |

Skindays' four inboxes were already published in earlier research. They are not four new leads or confirmed decision-makers. The earlier diagnostic selected two unnecessary Skindays blog pages; tightened route selection retained the same four inboxes with two page captures rather than four. This small check is not a general throughput benchmark or proof of reliable acquisition from every platform.

SmartRoof remains a real negative contact result; no address was guessed. Country, business-model fit, buyer relevance and mailbox existence were not newly qualified by this run. LinkedIn/X/PeoplePerHour private-email access remains unproven, and the actual Reacher backend remains unavailable. DNS alone never establishes a safe mailbox.

Normal candidate/contact/evidence/job counters were unchanged. Sending remains disabled and globally paused. No email, social message or contact form was submitted.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/contact-fallback-tests.xml
.\.venv\Scripts\python.exe scripts/verify_contact_fallback_live.py
.\.venv\Scripts\python.exe scripts/verify_complete_workflow.py
```

The live script expects the existing pilot candidates and uses a fresh isolated directory under `data/contact-fallback-live`. [Machine-readable results](contact-fallback-live-check.json) include current source hashes, page-source hashes, route origins and access/render diagnostics. Empty index results are explicitly controlled; the HTTP/Chromium captures are real. Future public-site runs may return different results.
