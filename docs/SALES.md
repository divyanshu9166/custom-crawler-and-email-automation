# Shared history and post-reply workflow

Latest complete-workflow check: **411 tests passed**. The agreed-call stage requires both call time and dated next action, plus baseline or an explicit unknown-baseline measurement plan. Unsent approved proposals/artifacts show review needed after their client/source context changes. Completion rejects open delivery tasks. Unsent pilots can revoke approval and return to review with history preserved. Actual Chromium forms and normal read-only desktop/mobile checks passed. See [the current per-node audit](COMPLETE_WORKFLOW_AUDIT.md) and [proof](complete-workflow-check.json). Calls, payments, agreement, client delivery and publication remain operator-recorded; [the 393-test third-workflow check](THIRD_WORKFLOW_AUDIT.md) is historical.

The earlier sales diagrams now have explicit application support. All external activity and commercial references are operator-recorded facts; the system does not infer buyer interest from every reply, make a booking, sign an agreement, collect payment or claim a client result.

| Step | Application support | Required evidence/action |
|---|---|---|
| Previous/manual outreach | Per-company channel ledger, source/date/contact references, shared hold | Record an actual LinkedIn/email/X/call event; don't record a planned message as already sent |
| Reply / opt-out | IMAP stop rules, manual ledger, review/fulfillment tasks for manual and inbox replies | Inspect the actual response; opt-outs remain suppressed |
| Provide initial value | Source-backed audit/concept/FAQ/WhatsApp-flow HTML | Exact saved quotes, reviewed observations, optional genuine company screenshot/callouts; inspect and approve export |
| Qualify client | Confirmed problem, goal, metric, decision-maker, timeline and budget context | A recorded real conversation and explicit qualification notes |
| Discovery call / nurture | Agreed call and next-action dates, baseline and metric, due tasks/outcomes | Operator records actual agreement; unknown baseline needs a measurement plan; nurture has a future date |
| Proposal | Versioned Markdown draft, commercial sections, review and actual-delivery reference | Confirmed need, scope/fee/exclusions/acceptance/support/ownership/change terms |
| Agreement and initial payment | Won/delivery stages and references | Record actual agreement/payment references; no payment processing is implied |
| Delivery and acceptance | Tasks, acceptance reference and measured outcome notes | Record real client acceptance and outcome, including zero/inconclusive results |
| Campaign learning | Sidebar Learning shows approval-frozen campaign/service/country/industry groups, accepted-record → human-reply/qualification/recorded-win rates and review guidance; sales reports retain currency-separated contract values | Duplicate messages/replies excluded; zero denominators/legacy context unknown. Values are recorded contracts, not audited revenue. See [LEARNING.md](LEARNING.md). External cost/outcome benchmarks remain separate. |

Shared holds are checked at sequence approval, held-contact resume and immediately before a queued send is claimed. A manual reply or opt-out cannot be cleared back into cold outreach. Only unanswered manual outreach in a new/contacted record can be released after explicit review; contact-level holds then require their own reviewed resume. A send already submitted over SMTP cannot be recalled.

Post-reply record updates carry a version: stale saves are rejected. Proposal/artifact review and delivery transitions run within a transaction; delivery cannot be recorded from an unreviewed draft. Creating another proposal/artifact preserves the old version. HTML artifacts escape prospect content, contain no scripts or remote assets, and FAQ prototype interaction uses native disclosure controls. The annotated audit embeds its saved company PNG with numbered HTML callouts; it does not alter the source bitmap or automatically validate a visual claim.

Example audit and FAQ exports in `docs/examples` are fictional UI fixtures. They demonstrate output structure and interaction, not a real prospect audit, client conversation or shipped AI chatbot.

## Research and draft acceptance benchmark

Prepare a CSV of genuine company websites with `company,website,campaign,country_hint` columns, balanced across US/UK and Campaign A/B. Then run from the project folder:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark.py --input data/benchmark-companies.csv --limit 50 --pages 30
```

The script keeps each company's pages/report in a unique private run folder, reports rendering/email-source counts and timings, and writes `review.csv`. It never imports prospects into the app, probes email recipients or sends messages. Independently check company/country/buyer match, observation/offer accuracy, verification results from the actual Reacher deployment and draft quality. Missing checks stay unknown, not zero or automatically passing. Record actual costs and reviewer/date. Inspect an initial 20 drafts before a sending pilot. Measure full deployment memory/CPU externally; the script does not label parent-process RSS as whole-stack memory.
