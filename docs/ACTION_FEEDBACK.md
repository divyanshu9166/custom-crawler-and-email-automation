# Action feedback and background activity

The dashboard uses one feedback layer across API-driven actions: research, preparation,
audits, mailbox/provider checks, qualification, drafts, settings, campaigns, imports and
other saved changes. Notifications stay in the viewport when the page is scrolled.
Successful notices dismiss automatically; failures remain visible until dismissed or
replaced. Existing inline results are retained for detail.

Buttons show a spinner and `aria-busy` during their requests. Common multi-step actions
also guard repeat clicks/submits while their follow-up refresh finishes, without
overriding the original approval/sending controls' disabled state. Local controls such
as navigation, filters and expanded sections keep their visible selection/open state
rather than generating a popup for every click. Export feedback says requested, not
downloaded: the browser handles the actual file or preview.

## Research is accepted before it starts

Click **Start research** for an immediate queued notification and **View progress** action.
The **Activity** button in the header opens a panel with the latest 20 jobs started from
this tab. The tab's tracked IDs survive page refresh through session storage; API keys,
passwords, form inputs and job payloads are not stored there. Operations remains the
place to inspect all jobs, including recurring searches and work started elsewhere.

| Status | Meaning |
| --- | --- |
| Queued | The server accepted the job; an available worker has not started it. |
| Queued · research OFF | Work is saved, but automation must be enabled in Settings. |
| Running | The server reports this exact job running. Source-check stages/candidate counts appear when recorded. |
| Completed | This individual job finished. Search completion does not establish completed research, qualified prospects or approved messages. |
| Failed / Cancelled | The server's recorded outcome and reason are shown. |
| Status unavailable | Connection/status retrieval failed. Last-known work may still run; nothing is resubmitted automatically. |

There is no invented percentage or completion estimate. Job completion refreshes dashboard
counts without replacing an open email editor. When Activity is open, job updates appear
inside it rather than displaying duplicate job notifications over the panel. An unavailable
status changes the header badge to `!`; a missing job is reported and stops polling.

Updates pause in hidden tabs and resume when the tab is visible. Polling is bounded and
backs off on failures. Dismissing a notification or closing Activity does not cancel work.
Connection errors after a mutation explicitly say that acceptance is unknown, so the
operator checks the result before repeating it. Validation notifications omit the API's
raw `input` values, which can contain credentials. Mixed import results show accepted
and attention-needed row counts instead of an unconditional success message.

## Status inside each prospect

The prospect list and workspace read actual research/audit jobs even when they were
started by another tab or before this session. An old `review` record cannot hide a
queued/running source job. Idle research with saved sources is labelled **Research saved**;
this means stored results, not complete coverage, qualification or a confirmed client pain.

A **Data collection** card shows the active task, worker OFF or retry waiting information,
saved page-content/contact counts, screenshot status and links to existing desktop/mobile
files. Saved source pages are text/metadata, not screenshot images. Pending captures,
partial rendering, older reports, missing files and failures have separate labels. Profile-only
prospects do not imply an applicable website screenshot. Existing captures do not prove
that a later screenshot attempt succeeded.

Status updates in place every five seconds while the workspace is visible, backing off
after network failure. When source jobs finish, a clean workspace reloads its saved results.
An open advanced section, email composer or edited form is preserved with **View updated
research** instead. Pending work disables duplicate research/audit actions and premature
email preparation. Automatic preparation OFF is explicitly called **Data collection mode**;
creating an email stays optional. No automation preference is changed by viewing status.

## Implementation and checks

`GET /api/jobs/{id}` is authenticated, read-only and returns a bounded status projection,
not the job payload. Discovery events carry their actual worker job ID, so identical
queries and concurrent campaigns cannot borrow each other's progress. A compatible
event index supports these lookups; schema version 8 and existing records are preserved.
`GET /api/leads/{id}/activity` provides the same read-only projection for a selected
prospect. Batched source-job lookup uses a compatible per-lead index, without changing
schema version 8 or rewriting job history.

Real Chromium tests cover desktop/mobile queue acknowledgement, repeat-click prevention,
running/completed transitions, refreshed-tab tracking, paused workers, unknown request
outcomes, offline polling, recorded failure, source-text escaping, settings validation
and secret-value exclusion. Fixtures run no real provider jobs or email sends.
