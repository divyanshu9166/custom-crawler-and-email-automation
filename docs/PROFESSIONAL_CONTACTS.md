# Public professional-profile contact enrichment

The missing LinkedIn `/in/` path is now separate from company/business-profile discovery. It researches a person or X profile **for an existing company**, saves scoped public evidence and published email candidates, and requires employer/role/ownership review before importing a contact. It does not turn a person into a company lead, reveal protected contact panels, generate guessed addresses or query a proprietary contact database.

## Automatic workflow

1. Website research preserves observed LinkedIn `/in/` and X profile links together with the originating company-page content hash. Only fresh, current company captures with matching hashes can seed professional research.
2. After the bounded website-research cycle, `AUTO_PROFESSIONAL_RESEARCH=true` queues `professional_research`, even when a generic company contact already exists. Existing active/replied/held/closed email conversations stop new professional research for that company.
3. Observed company links have priority. If they do not fill the configured budget, two bounded free SearXNG queries look for the named company's founder/owner/marketing/ecommerce/director profiles. Indexed results are hints, not email or employer evidence. `PROFESSIONAL_MAX_PROFILES=6` bounds captures; no paid search or developer API key is used by this step.
4. Without managed browser mode, robots-permitted profile HTML is parsed only for supported public professional fields. Managed mode uses the existing VPS-owned browser for scoped normal DOM. LinkedIn supports ASCII `/in/<slug>` roots, visible heading/headline/About/Experience and mailto links. Contact Info is off by default; dashboard opt-in reads only the exact person's visible dialog, labels its account-visible scope and retains section provenance. X profile bios/headers stay separate from author-matched post research. Account navigation, hidden elements, private messaging and connection lists are excluded. Challenges/denials remain held. See [the research upgrade](SOCIAL_RESEARCH_UPGRADE.md).
5. Each `professional_capture` records the profile URL, method, capture time, text/hash, published email candidates and unverified employer/identity status. No contact, technical verification probe or outreach is created by capture alone. Unsupported layouts stay unavailable.

## Review in the dashboard

Open a website prospect → **Public professional profiles**. Leave the profile URL blank for automatic discovery, or queue a known public professional URL. The latest research report exposes search-engine errors and held/no-result outcomes. Captures expose the exact saved text and published addresses.

To import an address, review:

- An exact quote naming the **current company** on the professional profile.
- An exact quote showing a relevant buyer role; explicit former employment is rejected.
- A current official company page and exact quote corroborating that **named person** independently.
- Notes confirming the public business inbox's ownership/relevance, plus the explicit review checkbox.

The review transaction promotes the exact profile capture into recipient-source evidence, records the employer/source review and imports a new, **unverified** contact. A verification job is queued only after review; global suppression is preserved and suppressed contacts are not queued for a probe. Source changes, a new profile capture, stale evidence, changed employer-page content or incompatible company identity invalidate ownership proof. Existing outreach or an inbox already attached to a different person/company cannot be silently reassigned.

Personal-profile source evidence is not offered as company-country or business-opportunity qualification evidence. Country, company identity, one selected offer, AI-written messages, technical verification, outreach eligibility and all-message approval remain separate gates. The email writer/approval sequence can bind a reviewed personal-profile recipient to its source; changed employer proof stops the sequence before sending.

Authenticated APIs:

- `POST /api/leads/{id}/professional-research`: optional `profile_url`; queues work only.
- `POST /api/leads/{id}/professional-review`: exact capture/employer/role/company quotes and reviewed publication; imports a sourced unverified contact.
- `GET /api/leads/{id}`: latest professional captures, currently reviewed email proofs and latest research/engine report.

The job uses the existing resource-admission and per-company serialization lane. No new database table/migration or external data-provider account is required. Runtime professional evidence stays in the private database and is excluded from source ZIPs.

## Verification and limits

The complete suite passed **795 tests**, including **32 professional-source cases**. Tests exercise real Chromium against fictional intercepted DOM, scoped HTTP parsing, public mailto extraction, private-route rejection, capture-without-contact/probe, employer/publication review, atomic rejection, stale/changed proof, suppression, authenticated API/queue behavior, per-company job serialization, current official-link reuse and approval/source invalidation. Fictional AI/SMTP data is not a live email-quality or mailbox-accuracy result.

The Chromium UI smoke test passed on desktop/mobile, with zero JavaScript errors. It exercised a fictional professional capture, review form, unverified contact import and queued-but-unexecuted verification. A duplicate generic inbox-review row discovered during that check was removed; professional sources have their own review path. Source review is reflected separately from mailbox verification.

`scripts/verify_professional_sources_live.py --lead-id 12` performed a real free-index lookup for the saved UK prospect **Bouquets For Days**, reusing 21 actual earlier company captures with their original times/hashes. Both targeted queries returned zero profiles, with Brave rate limiting, DuckDuckGo failure, Google denial and Qwant CAPTCHA recorded. Zero professional emails were captured, zero contacts created, zero probes/sends performed, and the main operational tables were unchanged. This diagnostic did not recapture the company website or use the user's logged-in browser. [The release-safe result](professional-sources-live-check.json) preserves the limitations.

**Real personal-profile email extraction remains unverified.** A successful authenticated VPS/profile capture, enough public named-person/company corroboration and representative live coverage are still required. A crawler can extract a published address from an accessible supported profile; it cannot supply an unpublished address from absent public evidence. This implementation is public-source enrichment, not Apollo database parity or unrestricted LinkedIn/X access. User-owned sign-in supplies technical session state, not automatic authorization to scrape.

## Subsequent multi-source check

The earlier two-query limitation above is preserved as dated evidence. The new engine failover, independent URL hints, current navigation refresh and six query variants were checked separately: Bouquets returned one current company email and an observed Instagram link, but still no matching LinkedIn/X professional capture. See [the implementation and live boundaries](MULTISOURCE_DISCOVERY.md). Social-profile hints are not personal-email extraction proof.

The subsequent [sourced-person and parser audit](NAMED_PEOPLE_RESEARCH.md) adds name-first queries and scoped X profile fixes. It records eleven real company pages, three sourced names and three isolated professional runs; zero live personal-profile emails were acquired. The earlier test counts/results above remain historical.
