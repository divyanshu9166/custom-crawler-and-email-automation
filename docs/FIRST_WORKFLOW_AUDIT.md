# First workflow: live discovery and research audit

Checked 11 October 2026 (India time). This is the first business workflow supplied by the user, not an assertion that sending or sales acceptance is complete.

## What actually ran

Own local SearXNG searches (including LinkedIn-company and X queries), candidate imports, domain deduplication, robots-aware HTTP/Chromium website research, saved source evidence and public-contact extraction. No Apify/Apollo, fixture search results, external mail or email probes were used.

Four balanced input segments: Campaign A UK dental, A US roofing, B UK skincare shops and B US coffee roasters. The market label scopes the query; it does not verify a business location or D2C model.

| Search candidate | Input segment | Saved current pages | Coverage | Stored contacts |
|---|---|---:|---|---:|
| [MYSKIN Shop UK • Buy Skincare • Make-up • Beauty Products •](https://www.myskinshop.co.uk/) | B · next market must be reviewed | 0 | failed · 1 issues | 0 |
| [Tanuki Coffee Roasters](https://tanukicoffeeroasters.com/) | B · next market must be reviewed | 19 | interrupted · 19 issues | 0 |
| [Austin Roofing Company  /  Roof Repair & Replacement  /  WDR](https://austinroofingandwaterdamage.com/) | A · next market must be reviewed | 0 | interrupted · 1 issues | 0 |
| [Contact Us - Dental Clinic London](https://www.dentalclinic.london/) | A · next market must be reviewed | 16 | interrupted · 10 issues | 1 |

**Fresh diagnostic totals: 4 website candidates, 35 current source pages, 1 published address extracted, 3 current source-backed proposal previews, zero qualified prospects.**

Each discovery segment used a 120-second diagnostic deadline; each crawl used 180 seconds. The application retains its 30-page crawl budget and normal 1800-second job timeout. These diagnostic deadlines do not reduce production crawler quality or capacity. Two crawls preserved useful pages before interruption; the roofing crawl yielded no page before its deadline, and the skincare site returned HTTP 403. Neither failure is marked as a completed crawl.

Proposal previews are computed read-only from exact quotes on fresh saved pages when interrupted research has no finalized findings. They propose review, without persisting an offer selection, inventing a pain point, interpreting missing features as absence or claiming sales uplift.

Four research-only candidate records and the one unverified address were copied into the normal dashboard for inspection. Zero automatic jobs, messages, approvals or verification probes were queued by that import. Existing records and credentials were preserved. The dashboard now has six company records (five websites, one profile) and three stored contacts, including prior records. Historical failed jobs stay visible; the new live diagnostic outputs are shown separately under Recent search runs.

## Verification against the supplied diagram

| Diagram step | Actual result / boundary |
|---|---|
| US/UK and Campaign A/B | All four input combinations ran. Location and business model remain source-review gates. |
| Discover via Google/official sites/LinkedIn/X | Own metasearch returned actual candidates and platform-query results. Several upstream engines were blocked or rate-limited; this is not direct Google/Maps or authenticated social-account access. |
| Verify identity, activity and relevant buyer | Remains review required. The public address found is a general business inbox; no named decision-maker was established. |
| Genuine/relevant source gate | Fixed a reproduced directory import. Known editorial/marketplace/listicle results and generic/personal platform pages are excluded before resolution. Unknown businesses still require review; the finite exclusion rules are not universal source classification. |
| One company and domain/contact deduplication | Repeated dental discovery reused the same company domain/ID. Normal import respects company-domain and global contact uniqueness. |
| Research website/product/journey/posts | Two current crawls captured pages; two failed/interrupted with no current capture. Announcement/post coverage is not guaranteed. |
| Save URL/date/screenshot or excerpt | 35 real text captures with URLs, timestamps and content hashes. This diagnostic did not execute prospect screenshot jobs; text excerpts satisfy the evidence branch. |
| Observations / opportunity / unknown | Readout separates exact source quotes, proposed service changes and missing country/buyer/model evidence. |
| Enough evidence for useful pitch? | Zero prospects passed qualification. Missing facts stay in review; no pitch eligibility is inferred from a completed search. |
| Match and prioritize one service | Three quoted service previews are available for review. Final selection and qualification remain operator gates. |

## UI and regressions

Default Find & research view: 17 relevant nodes from the 35-node graph, seven readable guided steps, scoped prospect/coverage results, source-backed previews and latest run limitations. Overview retains 11 stages and the full graph retains 35 nodes. Selected routes are highlighted; focus, fit, zoom, keyboard movement and layout dragging stay read-only. Desktop/mobile inspection confirms no overflow or inspector overlap.

Automated suite: 305 passed; the final readiness/freshness adjustment was followed by 17 focused first-workflow tests. Complete fictional-data Chromium smoke passed; normal live dashboard inspection also passed with zero JavaScript errors. No normal credentials were changed.

## Reproduce

`python scripts/verify_first_workflow_live.py` creates an isolated live diagnostic database/report. It performs real public requests and may preserve partial data or report failures. It never starts a worker, sender or email verifier.

Raw search probe: `data/first-workflow-search-probe.json`. The first diagnostic reproduced a YellowPages false positive; the second diagnostic after filtering is recorded by `data/first-workflow-live-latest.json`. Raw reports are retained unchanged, so their snapshot does not include proposal previews added subsequently to the read-only readout. Import proof: `data/first-workflow-import.json`; UI proof: `data/first-workflow-ui-check.json`; full suite: `data/first-workflow-tests.xml`. Private runtime reports and email addresses are excluded from the source release.
