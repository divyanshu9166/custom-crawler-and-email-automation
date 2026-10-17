# Personal professional X bio-email acceptance

13 October 2026. The preceding goal turn made progress in company-contact
coverage, but company support/training inboxes did not prove personal-profile
email extraction. This audit tests that requirement directly.

## Fresh unattended public-index sample

`scripts/verify_fxembed_personal_discovery_live.py` used the configured free index
and the enabled community profile adapter, with no manually supplied handles:

| Query cohort | Indexed profile selected | Bio email candidate |
| --- | --- | --- |
| UK business enquiries | RhiannonKagoe | kagoe@hotmail.co.uk |
| UK business enquiries | jessyttv | jessyontwitch@gmail.com |
| USA business inquiries | AlexGaKill46 | alexddelrio2@hotmail.com |
| USA business inquiries | kamicakes_1 | kamicakes_business@outlook.com |

**4/4 selected personal professional profiles returned public bios and four
literal email candidates.** The bios explicitly labelled them business enquiries/
inquiries. Mirror locations described Wales/England and Virginia/Texas. These are
self-declared hints, not verified business jurisdictions, qualified buyers or
proof of a need for our services. Subjects are professional creators/illustrators,
not a representative coffee/skincare/D2C business-founder sample. No replacement
profiles inflated the result. The private report is located by
`data/fxembed-personal-discovery-latest.json`.

## Independent personal-profile controls

Six profiles newly located in public X search results were also checked: Marisa
Meltzer, TiffanyMayCry, CasanovaCasts, esc_gabe, TomP1Bellingham and DJVadim.
Five returned public bios; TiffanyMayCry returned not found and was retained as
that failure. The five bios contained **seven unique addresses** after the parser
fix below. DJVadim supplied three booking-agent addresses; those are not three
personal owner inboxes. Tom Bellingham's published contact was a shared podcast
address. No buying authority was inferred. The private measured report is located
by `data/fxembed-personal-professional-check-latest.json`.

## Actual extraction bug fixed

Gabe's real returned bio published `gabe(at)escgabe(dot)com`, but the plain-address
reader missed it. The community-bio parser now decodes only explicit `(at)`, `[at]`,
`(dot)` and `[dot]` notation. It preserves exact offsets, original publication
quotes, extraction method and nearby purpose context. Natural role language such
as “Founder at Bright Demo dot com” does not synthesize an email. The saved actual
bios were reparsed without another provider call; original retrieval timestamps
and bio hashes were retained.

The [documented profile API](https://docs.fxembed.com/api/twitter/operations/2profilehandle/)
also publishes a separate website URL. That explicit field is now retained as an
unverified reference and participates in independent company-site research. It
never approves website ownership. Non-HTTP, private-IP and credentialed URLs are
rejected. The dashboard labels the reference and ownership-review requirement.

## Current-publication check and limits

A subsequent Marisa control returned the explicit linked contact page
`http://www.marisameltzer.com/hello`; its normal crawler capture returned 404.
This does not prove website absence, email invalidity or private-account status,
and no substitute URL/address was guessed. Current official-site publication was
not corroborated. See `data/personal-profile-contact-corroboration-latest.json`.

These observations prove working extraction of email strings from personal
professional bios returned by the approved community source. They do **not**
prove current first-party X publication, mailbox existence, inbox ownership,
buyer/offer fit, native X access, LinkedIn recovery, unattended VPS deployment or
Apollo/Apify-equivalent recall. Community hints remain separate from first-party
captures and cannot automatically import recipients or trigger verification/send.

The original full goal remains incomplete and active. LinkedIn personal-profile
source acceptance and representative target-market coverage are still required;
these results must not be relabelled as qualified business-founder leads.

All live checks preserved the operational database and paused/sending-disabled
state. Zero recipient imports, recipient SMTP probes and messages occurred.

## Current verification

The current combined community-profile, LinkedIn recovery, discovery and failover
set passed **87 tests in 35.86 seconds**, with the existing Starlette/httpx warning.
Chromium smoke passed with zero JavaScript errors. Ruff and JavaScript syntax
checks passed. The earlier full-suite baseline is 943 passing tests; a subsequent
full run's final output was not retained and is not claimed as a measured result.
The preview was restarted on current code, still paused with sending disabled.
