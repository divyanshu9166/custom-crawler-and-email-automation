# Campaign learning from saved acquisition records

Current local recheck: **575 tests passed**. Eleven Learning tests include four source-freshness regressions. Current qualification uses the workflow’s fresh reviewed-offer guard; historical sends, approvals and cohort attribution remain distinct. Countries outside US/UK are also excluded from current qualification by that shared guard. Earlier feature and browser snapshots below are historical.

Earlier feature release: **288 tests passed**, zero failures, one existing warning, 93.47 seconds. Explainable prospect priorities, exact separate-currency cost/receipt reporting with correction history, and permission-reviewed post-delivery maintenance/expansion/case-study plans are implemented. Full Chromium checks actual forms and desktop/mobile navigation with zero JavaScript errors; normal-server read-only checks preserve all existing operational records and credentials. Calls, payments, agreement, client delivery and publication remain operator-recorded. See [feature details](PRIORITY_FINANCE_AFTERCARE.md) and [current proof](growth-feature-check.json). Older validation sections below are historical.

Open **Learning** in the sidebar. The page shows lifetime SMTP-accepted business records, human email replies, recorded qualified conversations and recorded won clients, grouped by campaign, service, country and industry. Refresh learning reads the current database; it does not send mail or modify a campaign.

## Counts and rates

- `qualified_for_outreach` uses the same current reviewed-offer gate as the workflow map. Expired/future-dated sources, a changed quote or a newer research attempt without refreshed reviewed evidence remove current qualification. Historical approval, SMTP acceptance and frozen cohort attribution remain preserved; business qualification does not establish recipient validity or authorize sending.

- A business record with two accepted messages counts as one accepted record, not two prospects. Multiple human replies from the same record count once.
- A human email reply must be recorded after that record's first SMTP acceptance. Automatic replies, delivery-status notices and manual phone/social replies are excluded from the email-reply numerator.
- Client conversations on other channels can still lead to recorded sales qualification. Qualification and recorded-won rates use accepted records; won/qualified uses qualified sales records. Qualification/reply is not calculated because the channels can differ.
- Missing denominator is `null` in the API and a dash in the table. No sent sample is not a measured zero-success campaign.
- Sales-stage history preserves recorded qualification, won and completion milestones even if a later stage becomes lost/nurture. Imported current sales state can supply legacy milestone evidence; it is explicitly operator-recorded.
- Counts use lead/business records, not independently verified legal entities. A retained business profile and its matched website may describe the same actual business.

## Preserve context

Sequence approval atomically saves campaign, country, service, industry and prospect kind alongside the approval event. Learning uses the first saved approval context, so later labels cannot move earlier results into a different offer. Previously approved/sent records without that snapshot stay in a legacy unknown group; the system does not invent historical attribution. Unapproved groups use current fields and are labelled accordingly.

## Use the results

The page suggests a review based on the observed funnel: finish infrastructure/review if there is no accepted sample, inspect individual responses for small samples, review contact fit/provider placement/copy when replies are absent, inspect intent and qualification when responses do not advance, or inspect proposal/next-action context for qualified conversations without recorded wins.

The small-sample cue below twenty accepted records is an operational reminder, **not a statistical significance threshold**. All cohorts remain descriptive. Different sending dates, incomplete follow-ups, offer selection and business mix affect comparisons. No automatic winner, causal lift, ROI or email opens are inferred.

SMTP acceptance is not inbox placement. A recorded win requires the existing lifecycle's proposal/agreement/payment gates, but those references are operator assertions, not audited receipts or revenue. Client conversion/booking/purchase outcomes still require actual measurements and outcome notes; this funnel is not a private-analytics integration.

## Verification

The 238-test full suite passed on 10 October 2026 in 87.22 seconds. Seven new learning tests check empty rates, message/reply deduplication, automatic-response exclusion, frozen approval context, unknown legacy attribution, channel/timing boundaries, recorded sales history, auth/redaction and read-only reporting. Chromium checked empty/nonzero fictional metrics, escaped malicious-looking labels, demo labelling and desktop/mobile layouts. Fictional counts are not real campaign results. Real local data still has zero accepted messages, zero verified-safe contacts and zero approvals.

The authenticated `GET /api/sales/report` includes the report under `learning`. It returns aggregate context labels and counts, not recipient email addresses, mailbox secrets or message bodies. Its definitions explain attribution and metric limits.
