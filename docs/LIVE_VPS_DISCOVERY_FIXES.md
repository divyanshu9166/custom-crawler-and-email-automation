# Discovery fixes from VPS Operations output — 18 October 2026

The reported VPS run retained three prospect records, captured rendered LinkedIn company
pages and saved a published business email from official website pages. Its discovery job
nevertheless reached the configured 30-minute timeout while later research jobs kept running.
Separate jobs reported DNS/connectivity errors and an unavailable verifier. These are distinct
conditions; retained records do not establish qualification, verification or complete research.

## Requested discovery quota

The application previously stopped importing at the requested count but the discovery engine
continued resolving more profiles and running more queries. Its own count included website
domains, whereas the UI's requested count also included profile-only business records.

The import/signal callbacks now report when the retained-record quota is reached. Discovery
stops after saving the last record's source event and returns `stop_reason: requested_limit`.
Plain read-only/observer callers retain a default unique-website quota; an explicit false
callback result allows a consumer to continue until its own acceptance quota is met. Requested
limits remain prospect counts, not a guarantee that those businesses are relevant or qualified.
The report distinguishes planned `queries` from `executed_queries` and keeps engine failures
that occurred before the quota was reached. There is no new request after quota completion.

Cancellation/failed-engine tests now request more than the retained count, so they continue
to exercise partial-result preservation before the quota is met. The same errors are not
deliberately triggered after discovery has already fulfilled its requested count.

## LinkedIn company website links

The rendered company reader previously removed the query from LinkedIn's `/safety/go/`
link before extracting its `url` destination. It could therefore retain only the internal
redirect URL even when the visible Website field named an external business website.

The reader now takes the destination explicitly present in that visible scoped link, or
a complete visible HTTP(S) URL label when the redirect is opaque. It excludes truncated
labels, hidden links, credentials and non-HTTP(S) schemes, and drops unresolved internal
redirects. Website candidates still pass the existing company/domain checks and source
review; no hidden response data or authenticated private page is retrieved by this change.

## Current deployment boundaries

- Pending/running research and automatic continuation jobs should finish before manually
  queuing duplicate work. A discovery timeout does not erase records already saved.
- `gaierror` indicates a name-resolution failure; `ConnectError` alone does not identify
  whether DNS, routing, TLS or another connection stage failed. Inspect the affected service.
- An unavailable Reacher endpoint requires container/URL/path inspection. A configured
  secret is not proof that the backend is running. Do not keep retrying valid recipients
  against an unavailable service. Read-only `docker compose --profile verify ps -a` is the
  first deployment check; do not assume the cause from the generic readiness error.
- A broad search can yield weak business matches. Review the actual industry, geography,
  business activity and buying role before qualifying a prospect.
- Operations' `AI suggestions` flag describes optional research suggestions. It is separate
  from Settings → AI email writer and its NVIDIA model/key configuration.

These source fixes do not repair VPS-wide networking, start the verifier, enable sending,
reclassify live prospects or prove personal-profile email yield. Preserve the existing data
volume and use the registry override in [build recovery](REGISTRY_BUILD_RECOVERY.md) when
deploying while the Docker Hub path is unavailable. Verification is recorded in VALIDATION.md.
