# LinkedIn-linked person recovery

**Follow-up:** [The company-URL-free recovery audit](LINKEDIN_UNSEEDED_RECOVERY.md) records the search-filter fix and two passing known-profile controls. The earlier zero-result test below is retained as historical evidence; it is no longer the latest result.

12 October 2026. This implements a server-side public-source path without a paid
lead API or a desktop connector. It does not restore denied LinkedIn access.

## Automatic path

1. Discovery searches company LinkedIn pages and an additional bounded `/in/`
   query for founders, owners, directors and marketing roles in the chosen market.
2. A personal result supplies an indexed name/profile hint. It cannot become a
   website-less business record on its own.
3. Check explicitly observed company-domain URLs and follow their published
   same-company team/About navigation, then use up to two free index queries. At most four current company pages and four associated homepages are
   inspected. No guessed employer, email pattern or profile handle is used.
4. Require the exact normalized LinkedIn profile link in the same named staff
   record as a matching full name and published role. Only current home/contact/
   team/About routes qualify; article/event mentions are excluded. The company's
   homepage must also be accessible. Navigation prioritizes observed name/team
   routes within a forty-URL queue; unrelated staff pages stop after a company
   match. Multiple company matches remain unresolved.
5. Preserve the native access state independently. A match becomes an unqualified
   official-site prospect with its staff page as a crawl seed. Normal research,
   company/country/buyer/source review and mailbox verification still follow.

The company-page parser now reads bounded nested staff cards including h1/h5/h6,
scoped mailto/text/Cloudflare email obfuscation, and Person JSON-LD email fields.
It does not attach a footer inbox to a staff member. Shared staff inboxes retain
their published associations but do not select an individual recipient. Private,
hidden, former-role, testimonial and article-author exclusions remain in place.
Names and published roles are source facts, not automatic employer/buyer approval.

Company-professional research and prospect details display these email candidates
with the actual company-page URL and profile link. Official-page candidates remain
distinct from emails captured inside a native LinkedIn profile.

## Measured live result

`scripts/verify_linkedin_official_recovery_live.py` runs two known-profile controls:

| Control | Current independent page | Observed result |
| --- | --- | --- |
| Adam Frickleton | https://mlaarchitects.co.uk/team/ | Matching name, director role, exact LinkedIn link and one published email |
| Rachel Rogerson | https://norr.com/team/rachel-rogerson/ | Matching name, director role, exact LinkedIn link and one decoded published email |

**2/2 known controls resolved; two published email candidates.** Both native
LinkedIn snapshots stopped at the robots gate. No native-profile email was
captured. These two UK architecture controls are not a representative US/UK lead
sample, proof of mailbox existence, qualified buyers, or fresh LinkedIn discovery.

A second variation supplied only each company homepage: both people and both
email candidates were recovered by following observed navigation, without an
exact team-page seed. Reproduce that variation with
`python scripts/verify_linkedin_official_recovery_live.py --homepage-navigation`.

The additional control removed Adam's official-site hint and searched the exact
profile/name independently. It produced **zero accepted source results** with
engine access-denied/CAPTCHA/rate-limit issues; company resolution correctly stayed
unconfirmed. Therefore unattended discovery coverage still depends on available
public indexes or already observed company URLs. This change does not prove a
universal restriction bypass or vendor-equivalent recall.

The private measured report is located by
`data/linkedin-official-recovery-latest.json`. Operational database fingerprint,
sending-disabled/paused state and all recipient/job/message records were preserved.
Zero contacts were imported, zero mailbox probes and zero messages were sent.

## Verification

The full regression run passed 907 tests after fixing two compatibility regressions: generic JSON-LD email text should retain the existing publication-proof behavior, and personal index results without a valid human-name hint must not consume the profile budget. The subsequent bounded-navigation refinement passed 67 focused discovery/person/publication checks. Chromium smoke verified staff email/source display, native-access state and script-text escaping with zero JavaScript errors. Ruff, Python compilation, JavaScript syntax, source-package integrity and the restarted preview health/assets were checked. The preview remains paused, with sending disabled.
