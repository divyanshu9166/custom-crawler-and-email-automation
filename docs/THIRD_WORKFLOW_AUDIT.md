# Third workflow: node-by-node verification

**Email-writing correction (2026-10-11):** this earlier audit used controlled/template copy. It does not validate live AI writing or model quality. Operational writing now requires research-based AI with no template fallback; legacy drafts cannot be approved. See [the correction and current tests](AI_EMAIL_WRITING.md).

All **23 boxes** in the supplied third diagram have implementation and executed passing behavioral evidence. **393 tests passed** in 114.87 seconds; **37 new cases** target this audit. Ruff, JavaScript syntax, the full isolated Chromium smoke and dedicated approval/revision desktop/mobile checks passed.

**This is local implementation acceptance, not a claim that every real provider/client action is live or fully automatic.** Real state remains six unqualified candidates, three unverified contacts and zero messages; all real records/private configuration were preserved. No real recipient was probed or emailed. VPS/domain/mailbox setup remains deferred to the user.

## Each node

| # | Diagram node | Mode | Verified behavior | Live/manual boundary |
|---|---|---|---|---|
| 1 | Selected offer + evidence | review + automatic guards | **Passed local checks.** One current, quoted and country-reviewed A/B offer; stale evidence cannot approve. | Real companies still need identity and service-fit review. |
| 2 | Identify relevant buyer | operator review | **Passed local checks.** Stored contact name/role and an explicit relevance note are reviewed at approval and frozen. | Public roles are clues; actual buying authority is confirmed by the operator/client. |
| 3 | Choose contact route | automatic email checks / manual social | **Passed local checks.** Different-domain/profile inboxes require ownership review; manual LinkedIn history blocks overlapping cold outreach. | No automated LinkedIn/X DM or guarantee of email availability. Reacher/provider accuracy needs later live acceptance. |
| 4 | Check contact eligibility | operator review + automatic guards | **Passed local checks.** Approval requires recorded eligibility/relevance, current qualification, fresh safe verification, sender identity and no shared stop/history conflict. | The application records the operator eligibility review; it does not determine legal permission from an email address. |
| 5 | Draft personalized pitch | automatic draft + human wording review | **Passed local checks.** Source-backed observation, optional sourced trigger, one offer and a question; no fabricated completed asset or sales lift. | Human review decides accuracy, tone and relevance before any send. |
| 6 | Initial pilot review / revise / approve | operator gate | **Passed local checks.** All four drafts are reviewed; copy, recipient, identity and evidence snapshot freeze atomically. Unsent approval can return to draft review with history preserved. | Sent/sending/uncertain/failed or stopped conversations cannot reset through this control. |
| 7 | Send + log contact history | automatic after approval/readiness | **Passed local checks.** Trusted loopback TLS SMTP exercises actual protocol acceptance, durable Message-ID, local windows, quota/interval and inbox readiness. | This proves local protocol behavior, not your real mailbox, inbox placement, DNS or VPS deployment. |
| 8 | Response / delivery status | automatic monitoring + operator intent review | **Passed local checks.** Positive 2.x notices stay separate from temporary/unknown delay and permanent bounce; IMAP reads bounded messages independently. | A reported delivery notice is a provider report, not independently verified inbox visibility. Reply interest is reviewed by a human. |
| 9 | Suggested follow-ups Day 4 / 9 / 15 | automatic schedule of reviewed copy | **Passed local checks.** Three follow-ups use 3/5/6-day gaps after actual previous acceptance, preserving minimum spacing when delayed. | Day 1/4/9/15 are nominal inclusive days. Local business windows, weekends and actual delays can shift sends. |
| 10 | Any reply or stop signal? | automatic stop | **Passed local checks.** Any human reply cancels pending touches; automatic replies hold. Repeated IMAP records cannot duplicate fulfillment tasks. | An email already submitted cannot be recalled; SMTP uncertainty stays held for reconciliation. |
| 11 | Interested: stop + promised audit/demo/ideas | automatic stop/task + operator fulfillment | **Passed local checks.** A human reply creates a due review/fulfillment task; sourced artifacts can be prepared, inspected, approved and recorded as actually delivered. | Interest classification, asset selection and external delivery are operator actions; the task does not itself answer the prospect. |
| 12 | Question: stop + answer in context | automatic stop/task + operator conversation | **Passed local checks.** Questions stop the cold sequence and enter the shared conversation ledger/task queue. | The operator reads and answers the actual question; no automatic interested label or invented answer. |
| 13 | Later / out of office: pause + next date | automatic hold / operator next date | **Passed local checks.** OOO holds/cancels queued steps. Reviewed resume requires a future date, fresh verification and unchanged approved sources/copy. Nurture requires a future date. | Human later replies remain stopped; record nurture and continue the existing conversation. No automatic date inference or cold restart. |
| 14 | No / opt-out / hard bounce: stop + suppression/status | automatic + operator closure | **Passed local checks.** Explicit opt-out/permanent recipient failure suppresses globally; known non-acceptance cannot requeue a concurrent stopped message. | A plain negative human reply also stops the sequence; operator records lost/closure context. Conservative text recognition still needs response review. |
| 15 | None after final touch: close sequence | automatic | **Passed local checks.** Touch four closes the active cold sequence and no fifth message is queued. | Closure is after fourth SMTP acceptance, not a timed proof of no later reply; later replies are still processed. |
| 16 | Qualify need / timing / buyer / budget | operator-confirmed records | **Passed local checks.** Actual conversation plus confirmed problem, goal, metric, decision maker, timeline and budget context guard qualified stages; optimistic versions reject stale saves. | Unknowns are recorded explicitly. No automatic budget/need invention or buyer-authority guarantee. |
| 17 | Discovery call: problem / baseline / metric | operator-confirmed record | **Passed local checks.** Call-booked needs an agreed call time and explicit baseline notes; unknown baseline requires a measurement plan. Baseline and agreed metric appear in proposals. | The app records calls and dates; it does not book the external calendar or measure business analytics automatically. |
| 18 | Scoped proposal | automatic document + operator review/delivery | **Passed local checks.** Versioned draft includes deliverables, milestones, exclusions, acceptance, commercial terms and exact USD/GBP fee. Changed client qualification invalidates draft review. | External proposal delivery is separately recorded with an actual-delivery confirmation/reference. Existing delivered versions remain history. |
| 19 | Agreement + initial payment | operator-confirmed records | **Passed local checks.** Won/delivery needs a delivered reviewed proposal and actual agreement/payment references. Confirmed cash/cost entries use exact separate currencies. | No signature verification, payment gateway or independently verified bank receipt. Contract fee is not counted as cash received. |
| 20 | Deliver project / measure outcome | operator work + automatic record gates | **Passed local checks.** Existing delivery tasks must close with outcomes; completion requires client acceptance and measured or inconclusive outcome notes. | These controls manage delivery records; they do not themselves build/deploy the sold client website/bot or establish causal conversion uplift. |
| 21 | Expand: maintenance / improvements / case study | operator plan + automatic guards | **Passed local checks.** Completed accepted clients can have dated maintenance/expansion plans; reviewed case studies require explicit permission and preserve measured/inconclusive context. | Client agreement, actual follow-on work and publication remain operator actions. |
| 22 | Campaign review | automatic descriptive report + human interpretation | **Passed local checks.** Saved approval cohorts, accepted business records, human email replies and sales milestones are deduplicated. Automatic replies/DSNs do not inflate human replies. | No opens, guaranteed inbox placement, causal attribution or automatic experiment winner. |
| 23 | Improve targeting / research / offer; replies / calls / wins / cost | automatic reports + operator changes | **Passed local checks.** Learning provides next-review guidance, confirmed qualification/wins, recorded calls and currency-specific cost/receipt calculations with immutable correction history. | Targeting/copy changes require operator judgment. Missing costs/sample sizes stay unknown; client references are not audited revenue. |

## Corrections made

- Campaign A now shares the current-source approval gate; expired/replaced/recrawled pages cannot qualify a send. Canonical homepage URLs avoid false stale-source rejection.
- Approval saves evidence/copy/recipient/sender context. Every send and reviewed resume rechecks it. Changed sources, copy, identity or legacy missing proof go to hold.
- Under the send-claim write lock, verification, shared stops, inbox catch-up, global pause, quota reservations and interval are checked again. A readiness change between candidate read and claim cannot submit SMTP.
- Known non-acceptance preserves a concurrent reply/opt-out as cancelled instead of requeueing its in-flight message. Uncertain sends still require reconciliation and cannot reset.
- Positive 2.x delivery notices no longer pause a sequence or count as human replies. Temporary/unknown DSNs hold; permanent failures suppress.
- Calls/proposals now require a recorded baseline or explicit unknown-baseline measurement plan. The proposal and case-study snapshot preserve this context.
- Proposal review checks the saved client qualification context; changed requirements need a new preserved draft. Delivered historical proposals stay recorded.
- Completion rejects existing open delivery tasks. Client acceptance and measured/inconclusive outcomes remain required.
- The dashboard supports returning an unsent pilot to draft review with the previous copy/history preserved. An explicit new approval is required.

Twenty-two of the first 25 negative branch cases failed before the fixes; three DSN hold/bounce cases already passed. Two additional sales regressions reproduced stale proposal review and open-task completion. These are branch scenarios, not 24 distinct root causes.

## Operational limits

The localhost TLS fixtures exercise real SMTP/IMAP clients, both TLS modes, all four touches, thread IDs and failure stages. They do not establish real mailbox delivery or Reacher accuracy. Human reply intent, useful answers, actual artifact/proposal sharing, buyer qualification, calendar booking, agreement, payment, client work and measured results require operator/client evidence. They are supported records and review gates, not completed external actions.

The final touch closes after SMTP acceptance; later replies are still processed. Nominal Day 1/4/9/15 schedules can move with local sending windows and delays. Once SMTP submission starts, a concurrent stop cannot recall that message. Missing historical approval proof cannot silently resume; an entirely unsent pilot can return to review, while a started sequence requires conversation/delivery inspection.

## Reproduce and inspect

- `python -m pytest -q --junitxml=data/third-workflow-tests.xml`
- `python scripts/verify_third_workflow_ui.py` and `python scripts/ui_smoke.py`
- `python scripts/verify_third_workflow_nodes.py`
- Pipeline → company → contact: **Return unsent pilot to review**. Sales workflow → qualification: **Baseline and measurement period**.
- [Machine-readable per-node evidence](third-workflow-check.json); fixture [revision desktop](screenshots/third-workflow-revision-desktop.png) / [mobile](screenshots/third-workflow-revision-mobile.png); real read-only [sales desktop](screenshots/third-workflow-normal-desktop.png) / [mobile](screenshots/third-workflow-normal-mobile.png).
