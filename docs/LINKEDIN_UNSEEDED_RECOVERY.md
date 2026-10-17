# LinkedIn research follow-up: company-URL gap

13 October 2026. This supersedes the earlier conclusion that both known controls
failed without a company URL. Native LinkedIn access remains a separate result.

## Actual bugs and improvements

- The search-result validator interpreted `-site:linkedin.com` as a positive site
  filter. It rejected independent company pages and could retain the very host
  being excluded. Negative site operators now exclude matching hosts/paths;
  positive operators still constrain results, including subdomain boundaries.
- The old first query required an outbound LinkedIn URL to be printed in the
  indexed title/snippet. The fallback combined a name, roles and country operators.
  A minimal full-name query now runs first. Identity is checked against the exact
  LinkedIn link on the freshly captured official staff page, not inferred from
  search snippets. A successful source match stops unnecessary subsequent queries.
- Known contact brokers and people-directory copies are excluded from the current
  employer source path. Published fields on a current company page remain the
  only contact publication evidence for this fallback.
- Index name hints normalize lowercase names and explicitly recognized trailing
  professional qualifications. Current source quotes and employer/buyer approval
  remain separate. Standard official `/people/`, `/studio/` and `/practice/` routes
  are now eligible staff sources; nested news/article/catalog/client-project/testimonial paths remain excluded.

## Live result without a company URL

Inputs were just the two previously known public LinkedIn profile URLs and names;
their snippets were deliberately empty. Free public search resolved current
company pages, exact staff-profile links and **two published email candidates**:

| Known control | Independently found source | Result |
| --- | --- | --- |
| Adam Frickleton | https://mlaarchitects.co.uk/team/ | Director record, exact LinkedIn link, published staff email |
| Rachel Rogerson | https://norr.com/team/rachel-rogerson/ | Director record, exact LinkedIn link, published email decoded from the page |

**2/2 resolution controls passed without an operator-supplied company URL.**
Multiple search engines still reported restrictions, but available index results
were sufficient for these two controls. This is known-profile resolution acceptance,
not representative new-lead discovery, native LinkedIn profile capture, verified
buyer authority or mailbox existence. The private report is located through
`data/linkedin-unseeded-check-latest.json`. Reproduce with
`python scripts/verify_linkedin_unseeded_live.py` while the workspace is paused.

## Fresh discovery sample and remaining limit

A separate bounded public-index query returned seven LinkedIn profile results per
market for a UK architecture-director query and a US architecture-founder query.
Two valid name/profile hints per market were tested: Nick Jackson, Mark McIntosh
MCIAT FCIAT, Anis Souissi and Patricia Garcia Chimeno. **All four remained
unconfirmed, with zero accepted email candidates.** The markets are search hints,
not verified location; for example “US” appeared as part of a company name.

Rechecks after the name/staff-route refinements also held both UK examples. A
same-name employee at another company did not pass the exact LinkedIn link check.
No copied broker email or guessed address was substituted to inflate the result.
The private report is located through `data/linkedin-fresh-index-check-latest.json`.
Consistent new-prospect recall is therefore still unproven, despite the concrete
improvement in company-URL-free resolution.

## Research on an FxEmbed-like route

The reviewed repositories do not provide a demonstrated free, unauthenticated
community mirror equivalent to the working X source:

- [inprofile](https://github.com/boxed-dev/inprofile) uses a signed-in session;
  its examples and fixtures are explicitly fictional. No repository code was run.
- [ManavvGarg/linkedin-profile-api](https://github.com/ManavvGarg/linkedin-profile-api)
  uses session-authenticated Voyager endpoints; its credential-free mode is a
  bundled fixture. That mode is not live source access.
- [Laxmikant-Dwivedi/linkedin-profile-api](https://github.com/Laxmikant-Dwivedi/linkedin-profile-api)
  also requires a session and describes live challenge/access failures.
- LinkedIn documents [public profile badges](https://www.linkedin.com/help/linkedin/answer/a517984?query=badge)
  and [public post distribution](https://www.linkedin.com/help/linkedin/answer/a523402).
  These documents do not promise arbitrary profile-email access. Our one normal
  badge-loader check stopped at the robots gate, before fetching a badge payload;
  no badge adapter was enabled. See `data/linkedin-badge-loader-check.json`.

This research establishes no universal native-profile bypass. No login cookie,
private contact panel, privileged client identity or challenge handling was used.
The current implementation works through public index hints and independently
captured company sources, with native access state preserved.

All live diagnostics preserved operational data and sending-disabled/paused state.
Zero contacts were imported, zero mailbox probes and zero messages were sent.

## Current request: FxEmbed-like LinkedIn alternative recheck

The company-URL-free diagnostic was rerun on 13 October 2026 using only the
same two known names/profile URLs and empty snippets. Both resolved again:
Adam Frickleton through the MLA team page, Rachel Rogerson through her NORR staff
page. Each named staff record published one email and the exact LinkedIn link.
This confirms repeatability for these controls; it does not convert them into
fresh, representative discovery or establish unrestricted LinkedIn access.
The latest private pointer remains `data/linkedin-unseeded-check-latest.json`.
The operational database was unchanged; no contacts, probes or messages resulted.

Two additional public repositories were inspected directly:

- [Ramasaikiran/LinkedIn-profile-API](https://github.com/Ramasaikiran/LinkedIn-profile-API)
  is a PDL wrapper requiring `PDL_API_KEY`; its own documentation says the data
  comes from an existing dataset rather than a live LinkedIn visit. It does not
  satisfy the current no-key, free-public-source requirement.
- [BigAnomaly/linkedin-email-finder-profile](https://github.com/BigAnomaly/linkedin-email-finder-profile)
  contains an Apify-service README and per-result pricing, rather than a
  self-hostable extraction implementation. Its claimed email lookup is separate
  from direct publication in a LinkedIn profile.

Neither repository was installed or enabled. No verified free community LinkedIn
profile endpoint equivalent to the approved X adapter was established. The
concrete current route is free indexed LinkedIn hints, bounded official-site
resolution, exact named staff/profile matching and published email evidence.
It runs in the Python server and does not require the desktop connector.

## Earlier validation baseline

The final full suite passed **932 tests in 219.39 seconds**, with one existing Starlette/httpx deprecation warning. Focused index/person/discovery checks and recovery/publication checks also passed. A timing-sensitive retry test fixture was corrected to place its crawl start before its actual evidence capture; production freshness/cooldown gates were not weakened. Ruff and Python compilation passed. The normal preview was restarted with the final code, FxEmbed enabled and sending disabled/paused; read-only status/health checks preserved operational data. The verified source release excludes runtime data and credentials.
