# Fresh architecture sample and homonym recovery

13 October 2026. Previous goal work made concrete implementation/live-regression
progress through independent HTTP/rendered source retention. This continuation
checked a different fixed sector rather than recounting the known contacts.

## Discovery and current source limits

Two free SearXNG queries were fixed before contact resolution:

- `site:linkedin.com/in/ architecture director UK`
- `site:linkedin.com/in/ architect director United States`

Each returned seven indexed rows. The first two distinct eligible person roots
per query were frozen: Mark McIntosh, Adam McLatchie, David Gutierrez and Brian
Roberts. No operator name/company URL was supplied and no failed person was
replaced. Locale/query terms do not approve country, business fit or buyer role;
one input explicitly described a federal executive rather than a confirmed
private-business prospect.

All four remained personally unconfirmed, with zero accepted personal emails and
zero qualified buyers. FRONT's independent company results were ambiguous, not
an approved employer. The index supplied no accepted current exact staff/profile
association. Native access was not restored and the sample proves no vendor parity.

Two separate legacy Twitter root queries for UK skincare/US ecommerce founders
returned zero accepted index rows. No legacy-domain fallback was enabled merely
because it might increase coverage. Earlier constrained cohorts had nonzero raw
results rejected by explicit site/quoted-term checks; those rejected rows were
not silently relabelled as leads.

Read-only `/config` confirmed six enabled general engines in this local backend;
configured `mojeek` was absent. A configured fallback name is not proof of a
working engine. VPS setup must inspect actual engine availability. The local
search signing key was rotated without printing its replacement and the verified
original SearXNG launcher was restarted; production secrets were not changed.

## Actual recovery problem corrected

Common-name searches can return an unrelated current employee. The earlier
David Gutierrez pass followed a university staff frontier until all four leaf
requests were used, before the second identity query. Mark McIntosh also entered
an unrelated employer's team. Neither same-name source was accepted as the buyer.

Recovery now inspects at most two new leaf pages per search query before trying
the next identity query. It retains the total four-leaf-page ceiling. Pending
observed routes can still use remaining budget after the queries, including when
the second index request fails. Explicit supplied source hints keep their original
bounded navigation behavior. Exact profile/name/role and company checks are unchanged.

The employer parser now preserves a bounded terminal headline employer such as
`Director, Architecture UK&I, AECOM`. This is an explicitly unverified query hint,
with its original publication quote, not evidence of current employment. Ordinary
`at/of/within/for` hints take precedence; geography/generic terminal labels are
rejected. No person, company URL or mailbox is guessed.

## Same-row replay after the correction

The four original selected rows were replayed explicitly, not rediscovered or
replaced:

| Input | Earlier leaf pages / identity queries | Replay leaf pages / identity queries | Personal emails |
| --- | --- | --- | ---: |
| Mark McIntosh | 4 / 2 | 0 / 2, with AECOM hint retained | 0 |
| Adam McLatchie | 0 / 2 | 0 / 2 | 0 |
| David Gutierrez | 4 / 1 | 4 / 2 | 0 |
| Brian Roberts | 1 / 2 | 1 / 2 | 0 |

The David replay verifies that the second query can run before frontier exhaustion.
Mark's changed request count is not a controlled speed/recall benchmark: engine
rows and availability can change between captures. There is still no accepted
person or new company in this replay. Source failure/ambiguity remains visible.

Private evidence:

- `data/architecture-buyer-discovery-20261013.json`
- `data/architecture-buyer-contact-latest.json`
- `data/architecture-buyer-replay-latest.json`
- `data/twitter-alias-probe-20261013.json`

Reproduce new fixed discovery with
`python scripts/verify_architecture_buyer_coverage_live.py`; replay with
`--replay-report /path/to/original/report.json`. The replay pointer preserves the
original report path and does not count reused rows as new leads.

## Verification scope

129 focused person/recovery/index/profile-resolution checks passed in 47.13
seconds. Tests exercise a wrong-person coworker frontier, an independent exact
staff/profile result in the second query, index failure with remaining navigation
budget, the four-leaf cap, bounded employer headlines and unchanged rejection of
wrong names/profiles/emails. Ruff and Python compilation passed.

The final complete suite passed **1008 tests in 266.01 seconds**, with the existing
Starlette/httpx warning. Live runs preserved operational tables and sending
disabled/paused, with zero contact imports, real-recipient probes and external
messages. Latest preview/release verification is in VALIDATION.md.

The full goal remains incomplete. The correction improves query opportunity and
identity discipline; it is not successful native-profile extraction or proven
consistent new US/UK buyer-email coverage. Account-specific VPS acceptance remains
on [the deployment checklist](VPS_DEPLOYMENT_CHECKLIST.md).
