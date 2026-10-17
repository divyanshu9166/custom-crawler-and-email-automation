# Sourced person lookup and profile parsing

12 October 2026, subsequent goal audit. The previous release's company-contact result did not prove live personal-profile email extraction. This change addresses two concrete implementation gaps: person discovery required an email before preserving a structured person's identity, and professional lookup searched company names without using people explicitly named on current company pages.

## Behavior implemented

- Capture named people on official home/About/Team/contact routes from public Person JSON-LD, small staff cards with explicit roles, and short explicit named-role/business-relationship statements. Preserve the source quote, method, URL and company HTML hash. Names without an email are useful research inputs and do not create contacts or verification jobs.
- Exclude article/review authors, testimonials, hidden fields, former roles and broad team containers. Two live false positives were fixed: an introductory greeting included in a person's name and the generic heading "Our Mission" paired with a nearby founder reference. The affected official pages were recaptured after correction; regression cases preserve both fixes.
- Reuse only hash-matched saved crawl metadata. Current navigation refresh also exposes named people. Prioritize up to three sourced names in paired LinkedIn/X searches, then company/domain variants within `PROFESSIONAL_MAX_QUERIES=10`. Results still require company relevance; a common personal name alone does not pass. Named-person sameAs/observed links remain hints until profile/employer/source review.
- X HTTP and managed DOM readers now support the scoped UserName field, corroborate its handle against the requested profile, capture bio mailto links, remove hidden descendant text and exclude timeline/account navigation. The older non-main profile-header layout remains supported by the existing bounded header scope; navigation headings cannot supply a profile name.
- An unrelated footer sign-in form no longer causes a publicly scoped HTTP profile to be discarded. Login/challenge titles and unsupported/unready fields still hold; the crawler does not submit credentials or interact with private contact panels.
- Dashboard prospect details display observed people, exact source text, declared roles or "Role not established", and the need for employer/buyer review. A sourced name is not a qualified recipient or proof of a personal email.

## Live checks

[Dated live evidence](named-people-live-check.json) contains three isolated company-professional runs, six direct profile-access controls and eleven current official-page captures across six previously known businesses. The company sample comprises Dental Clinic London, Tanuki Coffee Roasters, SmartRoof, Skindays, Portland Coffee Roasters and Bouquets For Days. The page URLs came from saved observed navigation; this is not new-company discovery acceptance.

The eleven captures produced three named-person hints: **Justin Inahara**, explicitly published as Tanuki's owner; **Mark Stell**, explicitly published as Portland's founder/managing partner; and **Ellie Jones**, published in Bouquets' About statement without an inferred founder title. The output does not approve their current employer, buyer suitability or outreach eligibility automatically.

The revised Bouquets and Tanuki professional runs still found no matching LinkedIn/X profile. The Portland company search produced four indexed professional candidates; two within the diagnostic profile budget were attempted and held by the crawler's robots gate. Index association can reflect past employment and does not approve a current buyer. Three X and three LinkedIn direct controls also stopped at the robots gate, before profile HTML extraction. These controls include non-client/competitor profiles and are access diagnostics, not six qualified leads.

All three professional runs captured **zero live personal-profile emails**. A Common Crawl HTTP 504 in the Bouquets run did not prevent official navigation/person research; Tanuki's absent index record was reported as an empty result. No contacts were imported, no recipient probes or messages were sent, and each isolated run fingerprinted the operational database as unchanged. The source report now distinguishes copied old evidence from newly fetched company navigation; the two earlier run flags are explicitly normalized from their recorded captures while preserving the original declared flag.

**The full goal is not achieved.** Real public-profile email acquisition, representative market coverage and equivalent vendor coverage remain unproven. The profile access controls stop before parsing, so passing parser tests cannot supply missing live access. The existing opt-in VPS browser session path has no live signed-in/platform acceptance in this environment. The release does not add an unrestricted access-control bypass or use the desktop browser as an unattended VPS dependency.

## Verification

**839 tests passed**, including nineteen new named-person/profile-parser cases since the 820-test release. Real Chromium exercises scoped X profile-name/mailto parsing against intercepted fictional DOM. The full dashboard smoke passed desktop/mobile with zero JavaScript errors, including sourced-person display and recipient review. Ruff, Python compilation and JavaScript syntax passed. Synthetic profile emails are explicitly fixture evidence, not a live acquisition result. The one test warning is the existing Starlette/httpx deprecation.

The preview remains sending-disabled/paused. New metadata uses existing crawl/event storage; no schema migration or external paid account is required. Source archives exclude all runtime databases and credentials.

## Follow-up: LinkedIn-linked staff email recovery

[The current recovery audit](LINKEDIN_PERSON_RECOVERY.md) records the new initial `/in/` resolution branch, bounded nested staff email scopes, and two live official-source matches. These candidates are company-page publications; the original native LinkedIn denial remains separate.
