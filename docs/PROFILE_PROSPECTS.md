# Profile-first bulk research and email preparation

Use **Find prospects → Automatic prospect research**, enter an industry/location, select
**Business profiles first**, choose a market, count (up to 30) and named campaign, and
select **Start research**. There is no requirement to enter each business name/profile URL.
The repeat-search option retains the same focus and campaign. The advanced single-business
form remains optional for a business you already know.

## Automatic path

1. Search the configured business-profile sources, instead of filling the batch with
   ordinary website results first. Deduplicate profile identities and retain campaign ownership.
2. Capture accessible current business fields and check published links plus a bounded
   named-business website search. A matched website enters normal website research.
3. When no site matches, retain the profile URL, current text/hash, activity, published
   contact candidates and website-search report. The website field stays empty; internal
   profile keys are not displayed/exported as websites.
4. With **Settings → Automatically prepare one email after research** enabled, the worker
   schedules eligible profile records after research finishes. Otherwise collect research
   first, then select prospects in **Campaigns → Prospects → Prepare** or use Pipeline's
   batch preparation control. These paths use the same automatic qualification logic.
5. Require a matching name in a current first-party capture, actual business activity,
   a completed unambiguous website lookup without engine errors, an exact current
   US/UK country quote, campaign/offer fit and a currently published business inbox.
   An indexed snippet, community mirror or selected market does not qualify the source.
6. Assess one offer using the existing AI writer and source packet. Campaign A can propose
   a website launch or an independently sourced customer-question/calling task. Campaign B
   needs owned-product and starting-ecommerce evidence for a store launch. A profile-only
   prospect cannot receive an invented PageSpeed result or a website-improvement diagnosis.
7. Import only an explicitly labelled published business email from that same current
   source/hash. Check suppression, unique-inbox ownership and outreach history. Machine
   checks are recorded as `research_ai_profile` / `source_automation`, never operator approval.
8. Prepare one initial unscheduled email by default. Retain the website-search uncertainty:
   no matched website is not proof that no website exists. Explain the sourced business
   process and a useful proposed launch/change. Final recipient/message review remains.

Existing drafts, human edits, contact holds and sending history are preserved. Preparation
never enables sending, approves a recipient, calls a real mailbox verifier or creates
follow-ups unless the separate existing follow-up setting was explicitly enabled.

## LinkedIn personal profiles

A specific `/in/...` URL can be researched as a candidate. Automatic business qualification
requires explicit current self-selling evidence, such as an independent consultant,
self-employed provider or a person describing their own services. An employee/founder
keyword alone does not establish a personally owned business. Ordinary employee profiles
continue through the existing employer/official-company resolution path. Personal-profile
search in this mode also respects the existing LinkedIn people-search setting.

## Held cases and limits

Blocked/login-only sources, mismatched identity, stale captures, ambiguous/failed website
searches, unsupported country, missing business activity, unlabelled/personal contact details,
shared or suppressed inboxes and weak offers stay held with a reason. No address is guessed.
Changed research/configuration/contact state discards stale AI output. Published contact
ownership does not establish buying authority or mailbox deliverability.

This automates repetitive source checks and preparation; platform accessibility and the
strength of each business's public evidence still determine coverage. Website screenshots
and PageSpeed are unavailable until an actual website is matched. No CAPTCHA or login
restriction is bypassed.

## Validation

Controlled tests exercise both launch campaigns, automatic and bulk scheduling, profile-first
search/deduplication/campaign attribution, recurring execution, source/contact races,
source hashes, suppression/shared inboxes, employee exclusion and the real writer validator.
Desktop/mobile Chromium exercises the actual search form and recurring-search payloads.
These fictional-source tests do not establish live LinkedIn/X coverage or deliverability.
Database schema 7 adds only the saved search-focus flag; migration preserves existing
campaigns, drafts, suppression and delivery history. Back up before deployment because
older application images reject newer schemas.
