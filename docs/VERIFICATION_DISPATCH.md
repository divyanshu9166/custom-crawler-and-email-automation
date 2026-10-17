# Verification dispatch and response recheck

**Twelve failing timing cases reproduced; all thirteen regression cases now pass. The full suite passed 532 tests in 126.67 seconds.** One existing Starlette/httpx deprecation warning remains.

A source could be revoked, a recipient edited or an opt-out recorded while the verifier awaited API readiness or HTTP client startup. Previously the recipient request could still proceed. A change while awaiting the response could also save an old safe verdict to a changed contact.

The provider now calls a synchronous current-contact guard after both preparatory awaits, immediately before its recipient request. Research checks the unchanged recipient, current official publication and both contact/global suppression. It checks again in the same short database transaction that saves the verdict and event. No database lock is held across network access. Edited recipients cannot inherit the previous address verdict or error; suppressed records retain their suppression.

| Timing boundary | Changes exercised | Expected result |
|---|---|---|
| API readiness | Publication revoked; contact suppressed; global suppression; recipient edited | No real-recipient POST |
| HTTP client startup | Same four changes | No real-recipient POST |
| Awaiting response | Same four changes | Initial authorized POST allowed; stale safe result never committed |
| Unchanged current contact | Positive control | Normal result saved |

These checks use controlled HTTP responses and isolated databases. They establish the tested application behavior, not uninterrupted source stability after dispatch, universal mailbox accuracy or unrestricted platform access. No outreach messages were sent.

Reproduce with `python -m pytest -q tests/test_verification_dispatch.py`, or the complete suite using `python -m pytest -q --junitxml=data/verification-dispatch-tests.xml`.

[Machine-readable proof](verification-dispatch-check.json) records tested boundaries and current source hashes. [Complete workflow audit](COMPLETE_WORKFLOW_AUDIT.md) maps these cases to the publication, ownership, verification, hold and suppression nodes.
