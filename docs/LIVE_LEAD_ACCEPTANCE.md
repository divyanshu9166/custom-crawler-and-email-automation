# Live US/UK lead and source acceptance — 11 October 2026

**575 tests passed. Real searches/crawls ran in isolated databases; no worker, sender or recipient verifier ran. The normal operational lead/contact/message/job/event/crawl/evidence records stayed unchanged and sending remains disabled/paused.**

This check establishes a bounded research sample. It does not establish bug-free software, universal platform access or a steady supply of qualified buyers.

## Eight market/campaign/segment cells

Two actual website-discovery waves returned two indexed company candidates per cell: 16 unique company domains, with identical domains and record IDs reused. The production crawler retained its 30-page/depth-3/always-Chromium settings. Restricted platforms were tested separately; this is not a full default eight-platform expansion for every matrix cell.

| Market | Campaign | Segment | Researched official site | Current pages | Published contacts | Capture |
| --- | --- | --- | --- | ---: | ---: | --- |
| UK | A | Dental | [bespokedentalclinics.co.uk](https://bespokedentalclinics.co.uk/) | 26 | 0 | interrupted |
| UK | A | Florist | [bristolfloraldesign.co.uk](https://bristolfloraldesign.co.uk/) | 38 | 1 | interrupted |
| UK | B | Beauty retail | [blommabeauty.com](https://blommabeauty.com/) | 30 | 1 | partial |
| UK | B | Coffee | [origincoffee.co.uk](https://origincoffee.co.uk/) | 23 | 2 | interrupted |
| US | A | Dental | [atxfamilydental.com](https://atxfamilydental.com/) | 22 | 1 | partial |
| US | A | Roofing | [unitedroofingcolorado.com](https://unitedroofingcolorado.com/) | 6 | 1 | partial |
| US | B | Skincare | [unfilteredskincare.com](https://unfilteredskincare.com/) | 30 | 2 | partial |
| US | B | Coffee | [usroast.com](https://usroast.com/) | 30 | 2 | partial |

These eight representatives preserve **205 current official pages**, **9 published company-domain addresses** and one separately reviewed public Gmail. Seven of eight had a published email; the dental clinic without one has a current contact/booking route. No recipient was marked outreach-qualified by this check. Buyer relevance and mailbox existence are separate.

Blomma is a beauty retailer, not proven to manufacture its own product line. Damigrow remains an unresearched indexed candidate; the US skincare representative was Unfiltered, whose current source names Bath, Maine and its owner. Technical/order inboxes are publication findings, not confirmed purchasing contacts.

## Fixes exposed by real queries

- Generic adjectives admitted a local-time site and a dictionary article as roofing/coffee leads. Industry vocabulary now controls relevance for supported niches; explicit conflicting market signals are excluded, and an empty relevant search gets one bounded focused retry.
- “Contact us” and all-caps “CONTACT US” cannot establish or contradict United States geography.
- PeoplePerHour job/category pages and non-profile directory routes are rejected as business profiles. They cannot become false website-less companies.

## Partial captures and restricted sources

The actual Bristol florist checkpoint continued from **18 to 38 pages**, preserving every prior evidence ID/hash. Its report remains **interrupted**: the diagnostic deadline ended the pass, so remaining coverage is not accepted as complete.

All eight representative captures remain partial/interrupted. Some pass limits and render/resource issues persist. The initial pre-fix diagnostic was deliberately stopped while researching irrelevant sites; that controller stop is recorded separately from external site failures. Those sites and their contacts are excluded from the target-market results above.

| Source | Actual result |
| --- | --- |
| LinkedIn | Two company profiles: robots denied; official named-search result unconfirmed/ambiguous. |
| X | Two profiles: robots denied; official website candidates resolved. |
| Facebook | Two profiles: robots denied; one current lookup found a website candidate, one ambiguous. |
| Instagram | One profile: robots denied; website not found in the tested named search. No current identity/email proof. |
| BBB | Two business profiles unavailable; independent named lookups found website candidates. |
| PeoplePerHour | Two readable job/category pages rejected as business identities after the classification fix. |
| Additional Yell hunt | Three real listings unavailable; no published email accepted. |

SearXNG continued returning results while individual engines reported access denial, CAPTCHAs, rate limits or parsing errors. This demonstrates graceful degradation in this sample, not guaranteed future search availability. Platform resolution changed between some independent lookups; ambiguity stays reviewable.

## Website-less contact path

**Not accepted live.** The tested Instagram business signal had a completed no-match website search, but its profile was unreadable and had no current saved public contact evidence. No website-less email was imported, probed or approved. Synthetic regression tests cover the reviewed profile-to-contact route; they do not substitute for a real accessible business/email.

The Unfiltered Gmail review is genuine current official-website evidence and names its owner. It proves an other-domain publication path; this business has a website, so it is not website-less acceptance.

## Evidence and repeatable checks

Sources, exact location quotes, hashes, contacts, per-platform states and the bounded acceptance limits are in [the machine-readable report](live-lead-acceptance-check.json). Full captured page text and raw run history stay in the private `data/live-lead-acceptance` directories, excluded from the source release.

Run `python scripts/verify_live_lead_acceptance.py` for an isolated live diagnostic; `python scripts/verify_live_lead_sources.py --discovery-only` repeats the current website-search matrix. Large sites can exceed the explicitly reported audit deadlines. The full local application suite is `python -m pytest -q --junitxml=data/live-lead-final-tests.xml`.
