# Campaign 3 — Google Business Profiles

Find prospects → **Campaign 3 · Google Business Profiles** searches local businesses
in the UK or US for a possible website launch. Enter an industry and town, select
the market and requested count, then click **Research Google businesses**.
The optional repeat interval saves this same source and campaign for later runs.

Results are saved in the named group **Campaign 3 - Google Business Profiles**,
using the existing Campaign A website/inquiry service goal. This keeps the shortlist
separate from other A/B campaigns without creating a second sending engine.
The group appears on first use; deployment also creates it for this workspace.

## What the automatic research does

1. Open a bounded public Google Maps search. An independent configured search
   provider can contribute Maps listing references when the visible search is short.
2. Capture each accessible current business listing's name, category, address,
   public phone and observed Website link. Ignore reviews, hidden content and scripts.
3. Resolve any listed official website, then run the existing bounded independent
   website lookup when needed. Search snippets are discovery hints, not proof.
4. Exclude businesses with a matched official website from Campaign 3 intake.
   A later research pass that finds a website marks the existing candidate accordingly
   and holds website-launch preparation; it does not create another website lead here.
5. Save captured candidates whose website is still unmatched. Incomplete or ambiguous
   lookups stay held with their recorded reason. Missing results or a Website button
   never establish that no website exists.
6. Retain the public phone and source evidence on the prospect workspace. Email
   preparation still needs a current explicitly published business inbox, current
   identity/activity/country evidence and a completed unambiguous website lookup.
   A phone-only listing is useful research data, but cannot produce a guessed email.

The requested number is a cap on saved prospects, not a promise that enough eligible
businesses exist in a single bounded search. Repeated listing aliases share one identity.
Previously saved candidates do not create duplicate prospects. Public access holds,
consent, CAPTCHA, robots restrictions and rate limits stop the run; none are bypassed.

## Collect first, draft later

Keep **Automatically prepare one email after research** OFF in Settings while collecting.
Research remains ON. Sending and follow-ups remain OFF. When ready, use the existing
bulk preparation controls; sufficiently supported candidates can prepare one unscheduled
website-launch draft. Final recipient/message approval remains separate.

Phone availability is not consent to call, and this feature makes no calls. No email
is sent by discovery, research, saving contact details or preparing a draft. Current
public Google Maps pages are used; this integration does not enable a billed Places API.
Google Business Profiles often expose a phone rather than an email, so email-ready yield
can be low. Source availability and website-match confidence are reported, not guaranteed.

## API and deployment

`POST /api/discover` and `POST /api/schedules` accept
`discovery_source: "google_maps"`, `campaign: "A"`, `country_hint: "UK" | "US"`,
`query` and `limit`. Campaign 3 is selected automatically; an unrelated `campaign_id`
is rejected. Other searches default to `discovery_source: "mixed"` and retain their
existing behavior. The browser form limits a run to 30 requested prospects.

Schema 8 adds `schedules.discovery_source` with the legacy default `mixed`. Back up
before deployment: older images reject newer schemas. Existing drafts, suppression,
contacts and sending history are preserved. Research records remain on the VPS data
volume. No external CRM or additional storage service is enabled.

## Verification scope

Controlled checks cover primary visible fields, review/hidden-email exclusion, known-site
filtering, held lookups, phone-only cases, positive published-email preparation, duplicate
listing identities, source denial, recurring execution and schema 7→8 preservation.
Real Chromium exercises desktop/mobile forms and the phone/address workspace against
the application API. Native VPS checks captured public Maps searches and current listings with public phones
and linked websites. Another current listing had no observed Website field and a public
phone, but its independent website lookup was incomplete. Controlled checks verify that
this state stays held for qualification. No published email was found in those native samples. These checks
prove those access/extraction paths, not universal access, website absence or email yield.
