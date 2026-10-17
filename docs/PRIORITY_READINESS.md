# Review priority matches current workflow evidence

The review queue now uses the same current selected-offer guard as workflow nodes G, AA and BB, and Learning. A stored `qualified` status and matching observation quote are insufficient when the service, campaign, country or D2C commerce evidence no longer supports that review.

Ten reproduced defects failed before the correction and pass afterward:

| Condition | Previous score | Corrected score |
| --- | ---: | ---: |
| All research pages are future-dated | 70 | 0 |
| Observation requires review, service differs, campaign is incompatible, or multiple offers are stored | 100 | 50 |
| Country changed outside US/UK | 90 | 50 |
| Separate D2C commerce source is missing, changed or future-dated | 100 | 50 |
| Current country-source URLs differ only in canonical root slash | 50 | 100 |

The 50-point cases retain current research and published, technically safe contact fixtures. They receive no business/country/offer review credit and stay in the research-review lane. The safe verdicts in these tests are controlled fixtures; they are not real verified recipients. In real data, contact publication, suppression, freshness and contact state remain additional independent checks.

The shared selected-offer guard now rejects countries outside US/UK, so the workflow map and Learning also stop counting those records as currently qualified. Existing conversations and active sequences retain their lanes and history. Priority remains a work-queue rubric; it does not authorize sending or predict a sale.

## Executed checks

The full suite passed **491 tests in 136.08 seconds**, with one existing Starlette/httpx dependency warning. The focused priority, finance, Campaign A/B offer and Learning suite passed 79 cases. Full isolated Chromium smoke and the third-workflow form check passed. The normal dashboard was reloaded with sending disabled and inspected read-only; the [current complete audit](COMPLETE_WORKFLOW_AUDIT.md) records node coverage.

Two isolated local benchmark scenarios each used 500 fictional businesses. The empty-research queue took 0.0273 seconds. The reviewed D2C queue, with 1,500 source pages and 500 published contact fixtures, took 0.1319 seconds. Reading either queue preserved all jobs, messages and events. No network, verifier, worker or sender ran, and the normal database was not used. These timings describe local queue latency, not crawler throughput, a VPS memory guarantee or production acceptance.

See [machine-readable evidence](priority-readiness-check.json), [the README/workflow comparison](README_WORKFLOW_CHECK.md) and [priority, finance and aftercare](PRIORITY_FINANCE_AFTERCARE.md). Real qualified lead yield, running Reacher, external inbox placement and actual client outcomes remain unaccepted. Sending stays disabled.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/priority-readiness-tests.xml
.\.venv\Scripts\python.exe scripts/verify_complete_workflow.py
.\.venv\Scripts\python.exe scripts/benchmark_priority_readiness.py
.\.venv\Scripts\python.exe scripts/verify_complete_workflow_ui.py
```

The normal dashboard inspection requires the existing localhost development server and reads saved configuration for authentication without displaying credentials.
