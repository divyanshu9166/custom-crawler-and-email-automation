# Campaign dashboard

The home page now opens **Campaigns**. Pipeline remains the individual prospect
review/editor. An existing `?prospect=ID` or `?view=pipeline` link opens that view;
`/#campaigns` opens the overview. No email is approved or sent by opening it.

## Using the reporting workspace

The dashboard has three views instead of one long page:

- **Overview**: six lifetime counters, a 14-day activity chart, actionable work
  queues and a compact campaign comparison table.
- **Prospects**: search, outcome shortcuts, market/Deleted filters, paginated
  records and CSV export. Select rows to reveal bulk preparation, move,
  delete and restore controls. Open a company to review its single initial email.
- **Delivery activity**: the six latest recorded sending and inbox events for
  the selected campaign or all campaigns. Open an event's company for details.

**Reporting scope** updates the counters, chart, work queue and activity together,
and constrains the prospect list. Prospect search/outcome/market/Deleted filters
affect that list only. Campaign comparison always shows all campaigns so you can
switch context without clearing filters. Counter cards and message queue rows
open the matching prospect view; automation job rows open Operations. Job counts
include all associated job kinds, not only website research. Failed job history
counts stored failed records; a newer run may already have succeeded. Operations
shows the underlying runs for inspection.

The chart groups persisted acceptance timestamps and reply events by **UTC day**,
including today and the previous 13 days. Reply events are historical events,
distinct from the lifetime counters' *current contact outcomes*. A later opt-out
can therefore change a contact's outcome while leaving its earlier reply in the
chart/history. The activity feed never exposes raw event payloads, email bodies,
credentials or unsubscribe tokens. Empty charts show real zeroes; no sample data
is inserted. Deleted prospects remain in historical reporting.

Campaign directory “Active prospects” excludes deleted records; the top
“Prospects” counter includes them and labels the active count separately. SMTP
acceptance is not evidence of inbox delivery. No open rates, click rates or
conversion rates are estimated from these counts.

## Named campaigns and attribution

Create names such as **UK Cleaning – October**, choosing business goal A
(enquiries/bookings) or B (D2C ecommerce). These are separate from the two offer
decision trees. Existing records migrate into default A/B campaigns without
changing message bodies, approval snapshots or delivery history. Schema version
6 adds campaign groups, lead association, a reversible deletion flag and optional
scheduled-search association.

Discovery, recurring searches, manual website entry, profile entry and CSV's
optional `campaign_id` can target a named campaign. Legacy inputs still choose the
default group for their goal. New Search/Add forms expose **Save prospects in**.
Existing inbox/domain deduplication still applies. A rediscovered company is not
silently transferred to another campaign. Profile-to-website resolution carries
its campaign forward when possible; conflicts remain held for explicit review.

Unapproved prospects can be moved in bulk between campaigns of the **same**
business goal. Any approval, submission, delivery outcome or contact conversation
freezes the association. This deliberately prevents moving an old successful
conversation into a new campaign to inflate its results. This is one campaign
association per company, not repeated enrolment of the same contact into many
simultaneous sending sequences.

## What the numbers mean

| Number | Unit and interpretation |
| --- | --- |
| Prospects | Unique company/profile records, including Deleted in overview totals |
| Contacts | Unique stored contacts belonging to those prospects |
| Sent | SMTP-accepted messages across the campaign's history; not inbox placement |
| Bounced / Replied / Unsubscribed | Contacts with that **current** delivery outcome; DNC is included with Unsubscribed |
| Queued | Stored queued message rows; paused/global-disabled queues still count |
| Deleted | Soft-deleted prospects; separate from delivery state and inbox deletion |
| Failed / Uncertain | Current message failures / ambiguous submissions needing review |
| Research jobs | Current pending/running/failed jobs, including discovery jobs without prospects yet |

Counts aggregate contacts and messages separately before joining companies, so
multiple contacts or follow-ups cannot multiply totals. Deleted prospects remain
in historical counters. A reply followed by an opt-out shows the latest contact
outcome as Unsubscribed; the underlying reply and accepted message history remain
saved. These counters are not open/click tracking, cumulative unique reply rates
or verified delivery rates.

## Bulk work

Campaign comparison rows show per-campaign results and pause/resume controls. Campaign pause
blocks SMTP claiming and rechecks after login, before submission. Inbox monitoring
continues. Campaign resume does not enable global sending, remove suppression,
approve drafts, override limits or automatically start follow-ups. Already
submitted messages cannot be recalled.

The prospect table supports campaign, outcome, confirmed market, search and
active/Deleted filters, with 50 rows per page. It does not use Pipeline's 500-row
review list. Select a page and choose:

- **Prepare initial emails:** queue the existing evidence-based preparation flow.
  Unsupported, held or already-drafted prospects report why they were skipped.
  Final review and approval remain separate; no template fallback or bulk auto-approval.
- **Move to campaign:** assign unapproved prospects with the same A/B goal.
- **Delete prospects:** require a reason and UI confirmation. Cancel pending
  emails and research/verification jobs; prevent fresh queueing and silent
  re-import. Data, accepted messages, audit events and suppression stay on disk.
  In-progress research may finish; deleted records remain blocked from outreach.
- **Restore deleted prospects:** return them to the active list, holding any
  formerly runnable contact for review. Cancelled emails/jobs do not restart.
  Opt-outs and hard-bounce suppression remain in force.

Selections reset on filtering/paging and are restricted to visible rows after
refresh. Requests are capped at 200 prospects, with per-record success/error
results. No hidden "select every matching record" or unbounded send operation is
performed. CSV exports **all** matching records, not only the displayed page,
using a snapshot and bounded cursor chunks. Formula-leading values are escaped.

## APIs and deployment

All campaign/report/export/mutation routes require the application's existing
authentication and mutation-origin checks:

- `GET/POST /api/campaigns`; `PATCH /api/campaigns/{id}` (`active` / `paused`).
- `GET /api/campaign-prospects` with `campaign_id`, `state`, `market`, `search`,
  `deleted`, `limit` (max 100), `offset`.
- `POST /api/campaign-prospects/bulk` with `lead_ids` (max 200), `action`, optional
  `campaign_id`, and deletion `reason`.
- `GET /api/campaign-export` with the same filters, without page limits.

Campaign responses do not expose unsubscribe tokens or mailbox credentials.
Back up the database before deploying schema 6. Older images refuse newer schemas;
rollback requires a matching backup. Existing SMTP/IMAP, stable HTTPS unsubscribe
URL, DKIM checks, mailbox limits, sending-OFF state and disabled follow-ups remain
independent of the dashboard. Do not infer production inbox delivery from the
dashboard counters or synthetic tests.
