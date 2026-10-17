# Real no-send acquisition pilot

Live search and normal-dashboard worker run: **4 website candidates, 112 current official pages, 5 published email candidates after purpose exclusions**. One collected marketplace record is retained as rejected history. **Zero emails sent, zero sequences approved.**

These are research candidates. Published patient-support, press or partnerships inboxes still need buyer/contact-route review; their extraction is not approval for sales outreach.

| Prospect | Campaign | Current pages | Published email candidates after exclusions | Result |
|---|---|---:|---:|---|
| [Dentists in Leeds &#124; mydentist](https://www.mydentist.co.uk/) | A | 30 | 1 | review; crawl partial |
| [Roofing Contractors Services, Roofing Contractors in India](https://m.indiamart.com/) | A | 11 | 0 | Rejected marketplace/source |
| [Roofing Contractors in Raleigh, North Carolina &#124; SmartRoof](https://smartroof.com/) | A | 30 | 0 | review; crawl partial |
| [Skindays &#124; Curated Indie Skincare, Haircare & Wellness UK](https://www.skindays.com/) | B | 24 | 4 | review; crawl partial |
| [Order Coffee Online &#124; Portland Coffee Roasters](https://www.portlandcoffeeroasters.com/) | B | 28 | 0 | review; crawl partial |

## Actual discovery runs

| Query | Campaign / country hint | Queries issued | Public signals | Snapshot states |
|---|---|---:|---:|---|
| dental practice Leeds UK book appointment | A / UK | 9 | 22 | {'robots_denied': 15, 'captured': 1, 'unavailable': 6} |
| roofing contractor Raleigh North Carolina contact | A / US | 9 | 10 | {'robots_denied': 9, 'unavailable': 1} |
| independent skincare brand UK shop | B / UK | 9 | 10 | {'robots_denied': 8, 'unavailable': 2} |
| coffee roaster Portland Oregon shop | B / US | 9 | 10 | {'robots_denied': 8, 'unavailable': 2} |

Search engine CAPTCHA, access-denial and rate-limit reports are saved. Indexed profile results can help resolve a company website; they do not establish readable profile content or an accessible profile email.

## Findings and fixes

- Privacy/security/automated inbox filtering and historical-contact probe guard.
- Marketplace exclusion in discovery, CSV/imports, research, ownership and qualification.
- Worker recovery marks interrupted captures honestly while retaining their evidence.

The first UK dental candidate published a data-protection inbox. That record remains auditable and is excluded/suppressed specifically for nonbuyer purpose; it is not recorded as a recipient opt-out. Its patient-support address is still only a sourced contact, with buyer relevance unconfirmed. A noisy US roofing search initially selected IndiaMART; the corrected filters reject it and the real search selects SmartRoof instead. Updates were loaded through server restarts; queued work recovered and partial capture history is retained. Crawl limits stayed at 30 pages with real Chromium rendering. The initial UK search used the default 40-signal ceiling; subsequent runs cap deeper platform resolutions at 10 signals while still issuing all configured platform queries.

## Where the real workflow stops

- Crawl completion remains partial when page/depth/render/robots limits apply.
- A published inbox is not a verified mailbox or a confirmed relevant buyer.
- The local Reacher syntax endpoint returned HTTP 404; no safe mailbox verdict established.
- LinkedIn/X and other public platforms can return inaccessible/stale/ambiguous signals.
- No qualified country/buyer/offer review, sequence approval or sending is fabricated.

Source-backed finding previews and screenshots are research material. They are not confirmed pain points, improved conversions, buyer consent or client results. No phone/contact form was submitted and no LinkedIn/X/WhatsApp message was sent. VPS/domain/mailbox setup remains deferred by the user.

[Full saved results and current source hashes](no-send-pilot-check.json). Detailed URLs, captures, reports and held contacts are visible in the normal dashboard at http://localhost:8000/. Raw run files stay under private data/no-send-pilot/.
