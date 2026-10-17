# Current review-priority correction

The current complete suite has 491 passing tests, including ten additional readiness regressions. Priority shares the workflow’s selected-offer guard; source/country freshness, single compatible service and D2C commerce evidence must all remain valid. Current local 500-record timing and acceptance limits are in [PRIORITY_READINESS.md](PRIORITY_READINESS.md). Earlier feature counts below describe their original release.

# Prospect priorities, recorded economics and client growth

These features extend the existing acquisition system. They do not approve outreach, negotiate with clients, validate receipts or publish client work. The eleven-stage overview and the thirty-five-node map still describe the same pipeline. Client growth and financial reporting are available from node Z / Learning and each company's detail.

## Review queue

Pipeline defaults to **Evidence and readiness priority**. The order selector also supports newest first and company name. The score's breakdown is available in each company under **Review priority**.

| Signal | Points | Required evidence |
|---|---:|---|
| Recent research | 20 | A source captured within 30 days, not beyond allowed clock skew, and refreshed in the latest research attempt |
| Reviewed business fit | 25 | Current reviewed US/UK offer matching the campaign, one exact observation/country quote and valid D2C commerce proof when applicable |
| Reviewed target country | 10 | US/UK country recorded in the above valid review; discovery hints do not count |
| Selected service | 15 | One service selected in the above valid review |
| Usable published contact | 15 | New/active, unsuppressed contact passing the existing current ownership guard |
| Fresh safe verification | 15 | Such a contact has an unexpired safe verdict; future/stale verdicts do not count |

The score is a readiness rubric, not sales probability. The UI always requires final review and the existing sending gates. Research/review deficiencies remain explicit. Ready outreach reviews come first, followed by research reviews. Already active sequences and existing sales conversations have separate later lanes, regardless of score; they are not offered as new outreach work. The queue retains the existing newest-500-record API boundary; it is not a global ranking of unlimited records.

Calculation uses one SQLite read transaction, indexed evidence/contact/crawl lookups and selected contact fields. The SQL recent-source check excludes future timestamps; business readiness reuses the workflow selected-offer guard and its current saved source pages. SMTP payloads are not loaded. No job, draft or approval is created by reading or sorting. A synthetic 500-business local ranking measurement is recorded in the feature proof; it is not a crawler or whole-VPS benchmark.

## Costs and cash receipts

Open a company → **Costs and client growth → Record actual costs, payments and refunds**. Record acquisition, delivery or maintenance costs, actual payments and refunds with a unique reference, context and past transaction date. Entries require explicit confirmation of an actual transaction. A proposal's fee is never imported as cash income.

Money is stored as integer cents/pence with a maximum of two decimal places. USD and GBP are aggregated independently, with no implicit exchange rate. Amounts must be positive and finite. A duplicate matching reference is idempotent; conflicting values are rejected. To correct an entry, void it with a reason and create a new reference. Voiding retains the original record and an audit event; there is no delete or silent monetary edit.

Learning shows the global totals; company details show only that company's entries and totals:

- Net receipts = recorded payments minus refunds.
- Recorded contribution = net receipts minus acquisition/delivery/maintenance costs.
- Return on recorded cost = contribution divided by those costs. With no recorded costs this is unknown, not infinity or a fictional zero.
- Acquisition cost per recorded win = all acquisition costs in that currency divided by recorded-won business records that have acquisition costs in that currency. No such wins means unknown. Current and historical reached sales milestones are considered; a later lost label does not erase them.

These are operator records. Missing allocations, costs or refunds can materially alter the figures. They are not audited revenue, accounting profit, verified payments or causal marketing ROI. One business can incur costs in both currencies; currency-specific denominators must not be summed as distinct clients. Financial recording does not advance a sales stage, verify payment references or restart cold outreach.

## Maintenance, expansion and case studies

After completed client delivery with acceptance and measured **or inconclusive** outcome notes, open **Maintenance, expansion and case studies**. Create a future dated maintenance, expansion or case-study plan with an explicit scope. Existing plans are retained if the client record later changes; further progression requires the client still meets completion/acceptance gates, or the plan can be declined with a reason.

Plans progress **planned → reviewed → agreed → completed**, with a decline option before completion. Saves carry a version; stale concurrent changes are rejected. Repeating the same company/kind/title/date/scope creation returns the existing plan rather than duplicating it. A conflicting scope for that dated plan is rejected. Agreement requires its actual reference. Completion requires actual delivery/publication reference and outcome notes; it does not itself deliver or publish anything.

A case study additionally requires explicit client permission and its reference at every progression. Its internal draft freezes the client problem, metric, acceptance and outcome notes at creation; later edits cannot rewrite that snapshot. HTML exports escape all client content, preserve inconclusive outcomes and label planned/declined drafts accordingly. A permission-reviewed export is still subject to human inspection. The system neither invents results nor publishes automatically.

Learning lists open/overdue plans, counts completed plans by type in the API and provides company navigation. It also counts recorded agreed calls separately; an agreed date does not prove attendance. Node Z shows financial-record and open-plan counts and needs review when client plans remain open.

## API and persistence

Authenticated, same-origin or bearer-protected mutations:

- `POST /api/leads/{lead_id}/finance`
- `POST /api/finance/{entry_id}/void`
- `POST /api/leads/{lead_id}/client-plans`
- `PUT /api/client-plans/{plan_id}`
- Authenticated internal case-study export: `GET /api/client-plans/{plan_id}/download`

Company details include priority, financial entries/report and client plans. `GET /api/sales/report` adds `finance` and `aftercare` reports without changing the existing learning metrics. Database v4 adds two tables and supporting indexes while retaining existing leads, contacts, mail, history and credentials. Use the current release after upgrading; older application versions correctly reject a newer database.

## Verification and remaining acceptance

24 new executed regression cases cover money precision/invalid amounts, unknown denominators, refunds and currency separation, duplicate references/void history, actual transaction/date guards, stale/cross-business source and contact ranking, completed-client gates, ordered plan states/permission/version guards, frozen escaped case-study exports, authenticated scoped reads, additive migration and proposal-fee versus cash separation.

Earlier feature-release complete suite: **288 passed**, zero failures, one existing Starlette/httpx warning, 93.47 seconds. Full isolated Chromium smoke exercises the actual forms, totals, void, permission rejection, case-study progression, plan creation, sort and Learning navigation on desktop/mobile with zero JavaScript errors. Its transactions and client references are fictional. A separate read-only check of the normal server verifies its existing operational records and private configuration remain unchanged, v4 integrity is healthy, and no real financial entry, client plan or external message was added.

Domain, VPS and mailbox setup remain user-owned. Representative live research/verification/delivery acceptance and genuine client outcomes are separate from these local feature checks. Source and proof details: `growth-feature-check.json`.
