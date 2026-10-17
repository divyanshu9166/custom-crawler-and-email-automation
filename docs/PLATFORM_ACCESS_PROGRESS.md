# Free public-source research: progress and blocked goal

12 October 2026. The active request seeks Apollo/Apify parity, removal of LinkedIn/X restrictions and improved access to unpublished contact data. The user selected **free public sources**. This goal is **not complete**. Public-source improvements below do not make protected/unpublished information accessible or establish vendor parity.

## Blocking audit after repeated access checks

The same unresolved access/data condition persisted across the free profile-resolution work, the browser-reference work and the automatic public-post adapter work. Those turns made concrete progress on published business sources, but none supplied unrestricted unattended profile access or an authorized source of unpublished prospect emails. A new live audit on 12 October confirmed:

- LinkedIn Fonte and X Sonria direct profile requests still returned `robots_denied`.
- The official publisher still captured the known public Sonria post; it contained zero published email candidates and did not expose profile/private contact data.
- The preview was available, sending was disabled/paused and there were no pending/running operational jobs. Main operational records stayed unchanged; zero probes/messages were performed.
- The current [LinkedIn access documentation](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access) limits its open email permission to the authenticated member. The [X user-lookup documentation](https://docs.x.com/x-api/users/lookup/introduction) requires an approved developer account and app tokens; the public-post publisher is not that profile lookup service.

`data/platform-goal-access-audit.json` stores the fresh runtime result. The original goal is blocked on external access/data availability under the selected free-public-source constraint, **not completed**. Additional public parsing/UI changes cannot establish access to unpublished data that the selected sources do not expose. Resuming the full objective requires a suitable authorized data source/access change; API credentials alone do not imply permission or ability to obtain arbitrary private emails. A public-source-only completion criterion would be a user-requested scope change, not the original goal's completion.

Existing website research, published-source candidates, assisted browser references and single-public-post capture remain usable within their documented limits. Their successful tests and live captures do not establish vendor parity. VPS/domain/mailbox configuration is not the blocker in this audit.

Following the renewed request, a [local browser connector](BROWSER_CONNECTOR.md) was prepared to collect visible business website fields on an explicitly enabled tab, with local export and reviewed Workbench import. This reduces manual copying but does not remove the original access/data blocker. The extension has not been installed in the normal browser and is not an unattended server crawler.

A subsequent [VPS persistent browser mode](PLATFORM_BROWSER.md) now connects normal browser searches/profile capture directly to the server discovery/research queue, eliminating extension/file handoff for this mode. It needs an operator-owned VPS session and deployment acceptance; neither is configured here. Challenge/denial holds and unpublished-data limits remain. The blocked audit above describes the existing verified access state; the new mode is not evidence that restrictions or vendor parity are solved.

## Current requirement audit

| Requirement | Authoritative evidence | Result |
| --- | --- | --- |
| LinkedIn/X access without restrictions | Direct profile crawler snapshots returned `robots_denied`. Normal browser access was observed on one LinkedIn About page and one public X profile. Three known public X posts were captured automatically through X's official publishing endpoint | Unrestricted profile access not achieved; single-public-post access now supported |
| Unpublished prospect emails | The diagnostic saved only candidates published on separate public business pages; no protected/private email source was available | Not achieved; no hidden-address inference or mailbox probing |
| Free sources | Local SearXNG was restored on loopback 8888; current source lookup uses SearXNG, with no paid source API | Supported for the tested public-source path |
| Useful research from platform signals despite denied profile snapshots | Three known, previously indexed business profiles resolved to currently captured website candidates | Narrow live acceptance; not proof of fresh discovery consistency or direct platform scraping |
| Apollo/Apify parity | No identical-workload comparison or equivalent contact dataset | Unverified |

LinkedIn's [API access documentation](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access) describes application permissions; its email sign-in permission concerns the authenticated member. [Organization lookup](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/organization-lookup-api) has OAuth/access requirements. It is not unrestricted access to arbitrary prospects' private contact data. The [X API](https://docs.x.com/x-api/users/lookup/introduction) requires developer credentials; its [current pricing](https://docs.x.com/x-api/getting-started/pricing) is usage-based. No such API was used for these diagnostics.

## Changes actually implemented

- Explicit website URLs in an indexed business snippet can be checked against current public content. Contact/about paths survive as research seeds. An email domain is never converted into a guessed company website.
- Named-company, profile-URL backlink and contact/about search fallbacks are bounded. Search failure/partial engines cannot establish website absence.
- Website-side Organization `sameAs` and identity metadata supplement public profile links. A directory's listed business is not treated as the directory website's owner; homepage identity and site-own organization URL constraints distinguish those cases.
- Accented brand names are normalized consistently, and candidate parent-brand subdomains can be considered. These remain unqualified candidates with explicit identity/ownership review requirements.
- Thin allowed company pages can render normally through the existing mediated Chromium session. Denied/login/challenge platform profiles do not receive an alternate-client bypass.
- Matched public company pages reach the website crawler as seed URLs. The homepage may remain denied while a separately allowed contact page is captured. Every path still receives robots, same-domain, DNS and network checks; policy-denied paths keep coverage partial.
- Lookalike domains ending in the text `linkedin.com` no longer match genuine LinkedIn locale aliases.
- The local free search service was stopped at the first live check. It was restarted from the existing pinned SearXNG runtime. Search-engine rate limits/challenges remain reported; they were not cleared or bypassed.

## Current live results

`scripts/verify_free_profile_resolution_live.py` reuses three real platform search signals already recorded in the normal database. It does **not** fabricate fresh snippets or pretend old index results are current profile captures. Website resolution/search and official-page capture were checked live in an isolated database. Workers, mailbox activity, technical email verification and email writing were not started.

| Recorded platform signal | Current direct profile state | Current website candidate | Saved pages | Other-domain email candidates |
| --- | --- | --- | ---: | ---: |
| X: Sonria Dental Clinic | Robots denied | `www.sonriadentalclinic.co.uk` | 5 | 1 |
| LinkedIn: Fonte Coffee Roaster | Robots denied | `www.fontecoffee.com` | 6 | 1 |
| LinkedIn: MZ SKIN | Robots denied | `try.mzskin.com` | 1 | 0 |

**12 pages and two other-domain candidates** were saved. All three website captures are partial. No company-domain contact was imported in this sample; both published candidates require business/inbox ownership review. Their mailbox existence and buyer relevance are unknown. No email probe or message was sent, and main operational records were unchanged.

The MZ result is a currently readable branded subdomain candidate; it does not prove that every primary-site route is available or independently establish legal ownership. The initial diagnostic with search stopped resolved none. A later intermediate pass held directory/reseller ambiguity; the final matcher distinguishes site identity from a directory listing.

Runtime reports are referenced by `data/free-profile-resolution-live-latest.json`; extracted/runtime data is excluded from source packages. The final diagnostic preceded the script's explicit blank paid-provider/AI fields; the exercised runtime used SearXNG and no configured research AI. The script now explicitly forces those constraints for future runs.

## Verification and limits

### Automatic public X post capture

X's [official embedding guide](https://help.x.com/en/using-x/how-to-embed-a-post) directs publishers to `publish.x.com`. A live, unauthenticated GET to its `/oembed` endpoint returned HTTP 200 and matching first-party post/author metadata. The old developer oEmbed documentation URL currently redirects to the general developer overview; current behavior was checked directly rather than inferred from that historical URL.

`outreach/public_posts.py` now retrieves a specific, known public X post through that fixed first-party publishing endpoint. No profile HTML, authenticated session, hidden token, paid service, third-party mirror or widget script is used. Responses are bounded by time/body limits and must match the requested post ID, author and provider. Redirects, denials, protected/deleted/unavailable posts and rate limits remain unavailable; no retry or alternate route is attempted for those responses.

Automatic discovery now accepts genuine X/Twitter status URLs in search results instead of discarding every result that is not a profile root. Post author metadata replaces a potentially misleading indexed post title for company-name research. Published business links still require current company-page identity/backlink corroboration; they are not automatically accepted as official company identity. Source records identify `official_public_oembed`, `single_public_post`, `profile_snapshot=false`, the observation time, the posted date label and response/content hashes. Public email strings are saved only as review candidates in the signal; no contact, mailbox probe or outreach is created by the publication adapter. Profile-only review/source gates remain intact.

The company details UI distinguishes a **Public X post** capture from indexed platform research and explicitly states that the author's profile and mailbox were not verified.

`scripts/verify_public_posts_live.py` captured three actually observed Sonria business posts, dated 23 March, 14 April and 22 April 2026. **Three requests, three captures, zero published email candidates, zero direct profile requests, zero verification probes and zero messages.** Main operational records were unchanged. This is a narrow compatibility result for known public posts, not current activity evidence or a cross-segment discovery benchmark. Reports are referenced by `data/public-posts-live-latest.json` and excluded from source packages.

A current local SearXNG query for Sonria public posts returned zero results with reported Brave rate limiting, DuckDuckGo failure, Google denial and a Qwant CAPTCHA. Those issues were not bypassed, and fresh discovery was not counted as verified. The public publishing endpoint does not enumerate timelines, identify every relevant prospect, reveal an unpublished email or remove LinkedIn/profile restrictions.

The updated release passed **705 tests**. Twenty-five new cases cover permitted post routes, author/post/provider mismatches, bounded responses, unavailable/rate-limited posts, absence of authenticated headers, no script execution, source-preserving discovery and current official-page corroboration. Chromium UI checks passed with clearly fictional isolated post-capture data and zero JavaScript errors. The normal preview was restarted; sending remains disabled/paused. These checks establish the stated adapter behavior, not Apollo/Apify parity.

### Normal-browser evidence and reference intake

The normal in-app browser showed the [Fonte company About page](https://www.linkedin.com/company/fonte-coffee-roaster/about/), including its website and Seattle headquarters. It used the user's existing signed-in LinkedIn session. The [Sonria public X profile](https://x.com/SonriaUK) displayed business information, website/booking links and a login/signup prompt. Neither observed page showed an email address. No login, CAPTCHA, private-member navigation, messaging or cookie/token transfer was performed. This evidence does not establish that the server crawler can fetch those profiles.

The dashboard's **Find prospects → Research a website linked from a business profile** form and authenticated `POST /api/browser-references` save an operator-observed reference, source URL, observation time and market hint. A new company receives a normal website-research job with its linked public page as a seed. Duplicate submissions reuse pending research. Existing captures, company reviews, contacts and messages are preserved; existing companies require an explicit research action to recrawl.

These records are explicitly `operator_browser_reference`, with `server_profile_fetched=false`, `identity_verified=false` and `contact_publication_proof=false`. They appear separately in company details and do not become saved crawl evidence or qualify a contact. Current company-page capture, publication/ownership review, buyer/offer review and technical verification remain required. The intake rejects personal LinkedIn routes, X posts, source query parameters, private-IP URLs, account paths and stale/future observation times. It does not import browser sessions or automatically drive a platform browser.

Two actual browser-observed links were replayed through `scripts/verify_browser_reference_live.py` in isolated databases:

| Browser reference | Current website-research result | Contact result |
| --- | --- | --- |
| Fonte LinkedIn About → `http://www.fontecoffee.com` | Six captured pages; coverage remains partial | One other-domain published email candidate; no company-domain contact; ownership and mailbox existence unverified |
| Sonria X visible booking post → `https://sonriadental.co.uk` | DNS resolution failed; no captured pages | No contact; a visible historical profile link is not proof of a currently reachable site |

Both checks sent zero messages and ran zero verification probes; main operational records were unchanged. Runtime reports live under `data/browser-reference-live/` and are excluded from source packages. The latest pointer selects the Fonte run; the Sonria run is retained separately. The older Sonria `.co.uk` website candidate in the preceding diagnostic and the different X booking link are separate candidates, not a confirmed domain migration.

The updated release passed **680 tests**, including authenticated intake, rejection with no partial rows, provenance separation, duplicate-job behavior and preservation of existing qualification/messages. The Chromium smoke check exercises the new form and reference display with clearly fictional isolated data. This assisted reference path improves access to useful business links; automatic restricted-platform access and vendor parity remain outstanding.

The preceding release passed **666 tests**, including fourteen new public-source resolution cases beyond the previous 652-test release. The checks cover no email-domain guessing, LinkedIn suffix spoofing, own-organization metadata, a directory leaf's unrelated ownership, profile-backlink search, engine failure, public contact seeds, permitted official-page rendering and source/review gates. Existing workflow/UI checks passed; sending remains disabled/paused.

These tests prove the stated public-source behavior, not that LinkedIn/X restrictions have been removed. Fresh discovery across segments, real website-less contact acceptance, unreviewed ownership, unpublished data, unattended restricted-profile coverage and vendor parity remain outstanding. This report preserves those requirements as incomplete rather than redefining them as public-website/public-post success.
