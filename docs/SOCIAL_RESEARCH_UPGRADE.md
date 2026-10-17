# LinkedIn and X research upgrade

This upgrade implements useful capabilities identified in the Agent Reach source audit on
17 October 2026 inside Outreach Workbench. It extends the existing VPS browser, queue,
review process and local SQLite storage. Agent Reach, twitter-cli, a second browser stack
and hosted Jina/Exa processing are not dependencies of this change.

## Implemented capabilities

| Capability | Integration | Boundary |
| --- | --- | --- |
| LinkedIn buyer discovery | Company and buyer-role keyword searches read rendered people cards before index fallback | Results are person/employer/buyer hints, not qualified contacts; geography still needs source review |
| Richer personal profiles | Visible About/Experience and bounded Experience detail reads reuse the same browser session | Exact profile route required; account navigation, hidden fields and unrelated dialogs excluded |
| Optional Contact Info | Dashboard switch enables the exact person's visible Contact Info dialog | Off by default; account-visible data is labeled separately and still needs independent current-employer/ownership review |
| LinkedIn company posts | Author-matched company post cards with permalinks, capture hashes and timestamps | Bounded visible sample; publication date may be unknown; no claim that every post was captured |
| X recent posts | Author/permalink matching, quote/repost exclusion, original post text | No private-account or hidden-email access; visible dates are retained without inventing event recency |
| X discovery fallback | If user-card search returns no candidates and the platform is not held, a latest-post search supplies author hints | Normal browser UI, same query identity and budgets; does not clear 403/429/login holds |
| Operational diagnostics | Saved configuration, latest result, capture counts, contact counts, operation timings and access holds | Configuration never implies a successful live source check; no automatic network probe on dashboard reads |
| Email personalization | Captured post evidence is available in the optional announcement selector | An operator must choose an exact quote and review relevance/recency; country and the primary business finding still require business-source evidence |

Settings → LinkedIn & X research exposes the controls without editing `.env`. Saving
pauses sending. It does not enable the worker or sending. Existing worker/sending controls,
mailbox quotas, approval snapshots, suppression and verification remain in force.

Pipeline includes a post-research panel and a **Research LinkedIn / X posts** action.
Automatic professional research also runs bounded post research for known profile hints.
The queue serializes this work with research of the same prospect, and the browser retains
its existing OS/session locks. No separate Chrome profile competes for the signed-in session.

## Data and provenance

Data stays in the existing `/data/outreach.db` in `outreach_app_data`. Browser state stays
in `/data/platform-browser/profile`; managed preferences stay in `/data/workspace-settings.json`.
Post snapshots record the source URL, author URL, source hint, text hash, observed time and
observed publication date when present. Captured post text is untrusted source data, never
instructions. Post email mentions do not create contacts or queue verifier jobs automatically.

Person section captures retain their own source URLs, hashes and visibility labels alongside
the combined profile capture. An optional section failure does not erase the root capture;
it is reported separately and authentication/HTTP denials preserve platform holds.

## VPS deployment

Keep Worker and Sending OFF while building and checking. Preserve the same Docker volume
and both Compose files. No new service, paid API, login export or public port is needed.

```sh
cd ~/custom-crawler-and-email-automation
git pull --ff-only
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml build app
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml up -d --no-build --wait --wait-timeout 120 app
```

Refresh the dashboard. Keep Contact Info off until you choose to enable that account-visible
source. Run a bounded known-company check first:

```sh
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml exec -T app xvfb-run -a python scripts/check_social_research.py --linkedin-company https://www.linkedin.com/company/linkedin/
```

Optional `--people-query`, `--person-profile` and `--x-profile` arguments check their respective
paths. Use a known relevant profile and one path at a time; checks print counts and statuses,
not email addresses, cookies or full profile content. A non-captured result remains incomplete.
Do not clear a platform hold without resolving its recorded cause.

After deployment checks, inspect pending jobs and enabled recurring searches, enable Worker
with Sending OFF, then run one small UK/US search. Find prospects → Source access and extraction
shows saved outcomes; Pipeline shows the data. Compare relevant businesses, reviewed contacts,
source failures, elapsed time and `docker stats` peak resource usage on the same prospect sample.
Feature coverage is not evidence of a better live email yield; deployment acceptance is separate.

## Source audit references

- Agent Reach `94f06c1969dfc1834001269d79d3ad0972d9dee6`: installer/doctor architecture, ordered tool backends and diagnostics.
- LinkedIn MCP `91329ef23a4d3d2f3d3d36cfd790f47c0cbf5edc`: section-scoped personal/company research and visible Contact Info capability.
- Twitter CLI `7c634e0d396b1e7af9f63315b414925fe4f29ae7`: profile/post research and structured output capabilities.

The implementation here uses the project's existing browser and original readers. Hosted
reader/search services are not required, and no unrestricted LinkedIn/X access or unavailable
personal email is promised. Test results and deployment limits are recorded in VALIDATION.md.
