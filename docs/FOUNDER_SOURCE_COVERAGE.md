# Fresh founder-source coverage follow-up

13 October 2026. The previous goal turn made concrete progress: negative search
operators and company-URL-free resolution were fixed and two known controls passed.
This follow-up targets fresh public-index prospects rather than treating those
known controls as a coverage benchmark.

## Current changes

- Preserve explicitly declared employer phrases from indexed titles/snippets as
  **unverified search hints**. Prefer a person+employer query when one exists.
- Read names and roles published in separate spans inside one staff-page heading.
  Multiple names in a heading do not select an individual owner.
- Preserve same-name official-page observations even when the requested LinkedIn
  link is missing. Those observations do not approve a person or recipient.
- Independently resolve a declared company using a bounded additional query and
  up to three current homepage checks. Its own title/Organization name must match;
  mentioning a company in customer/editorial text is insufficient.
- A unique business match creates a **company-only candidate** in discovery while
  personal identity remains held. Native-source state, exact person-link review,
  country/buyer qualification and contact ownership checks remain separate.
- Known contact brokers, people directories, publisher and platform roots cannot
  consume the independent-employer request budget.
- Dashboard details distinguish a company source from unresolved person identity.
  Fixture browser checks exercise these as separate states, including escaping.

## Actual measured evidence

A fresh free-index sample used UK coffee-founder and US skincare-founder queries.
It returned six results per query; two valid names per market were processed:
Pellegrino Venturino, Tom Sobey, Anisha Khanna and Maree Glading. Market labels are
query hints, not approved business locations. No profile was replaced to inflate
success. The initial person-only passes produced no exact staff/profile matches.

The company-only follow-up independently found two current company sources:

| Indexed founder hint | Current company candidate | Contact evidence |
| --- | --- | --- |
| Pellegrino Venturino / Renoir Coffee | https://horeca.renoircoffee.co.uk/ | `renoircoffee83@gmail.com`, published on the rendered barista-training page |
| Anisha Khanna / Sonage Skincare | https://sonage.com/ | `sonage@sonage.com`, published on the current help-center page |

These are **two business-email candidates**, not verified founder inboxes. They
remain unqualified for buyer fit, ownership, country eligibility and mailbox
existence. The Gmail candidate needs other-domain ownership review. Native LinkedIn
publication and personal identity were not asserted.

The HTTP-only Renoir diagnostic captured an 83-character JavaScript shell with no
email. Repeating that site using the normal configured Chromium renderer produced
4,996 homepage characters and found the published Gmail candidate on an observed
page. Thus the HTTP-only result was not representative of normal renderer coverage.
The three-page rendered run remained partial; rejected analytics POST requests
were recorded and no forms or messages were submitted. Sonage's three-page crawl
also remained partial while saving the email's current publication source.

A previous fresh UK architecture control now reaches BDP's current Nick Jackson
staff page and saves its explicit director/location quote. It contains neither
an exact LinkedIn link nor an email, so identity/contact acceptance remains held.

Private evidence pointers:

- `data/linkedin-founder-segment-check-latest.json`
- `data/linkedin-employer-hint-check-latest.json`
- `data/linkedin-company-fallback-check-latest.json`
- `data/linkedin-company-contact-check-latest.json`
- `data/linkedin-rendered-contact-check-latest.json`

All runs preserved the operational database and sending-disabled/paused state.
Zero recipients were imported, zero recipient SMTP probes and zero messages sent.

## Original goal still incomplete

Neither the two known-profile controls nor these two company contacts proves
native LinkedIn personal-profile email extraction or Apollo/Apify-equivalent recall.
Exact personal-profile acceptance in the fresh founder sample remains zero.
The approved X community adapter's earlier observed bio email candidates remain
separate evidence; they do not restore native X access or prove buyer authority.

A public-post URL search for one observed published business address produced no
accepted URLs, with index restrictions recorded. No embed URN was guessed or
profile retried. A single anonymous
[Jina Reader](https://jina.ai/reader/) check explicitly enforced the normal crawler's
robots rules and returned HTTP 409 `ResourcePolicyDenyError` for LinkedIn. No cookies,
proxy/identity override, challenge handling, further attempt or adapter was enabled.
See `data/linkedin-public-post-route-check.json` and
`data/linkedin-reader-availability-check.json`. This is a current access result,
not proof that every possible public source is unavailable.

The full objective remains active and completion unproven. Further acceptance
must demonstrate live personal-profile sources and representative US/UK coverage,
without treating company support/training inboxes as confirmed decision makers.

## Verification

**943 tests passed in 221.90 seconds**, with one existing Starlette/httpx warning.
Focused person/employer and discovery/professional checks passed. Chromium smoke
verified separate company-only and matched-person displays, absent recipient
approval controls for unresolved identity, and script-text escaping with zero
JavaScript errors. Ruff and JavaScript syntax passed.

The final normal preview was restarted and its authenticated status/health/assets checks preserved operational data: sending disabled, paused, FxEmbed enabled and native managed platform browser disabled. Python compilation and source ZIP integrity passed; the release excludes runtime data and credentials.
