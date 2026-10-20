# Delivery, suppression and unsubscribe

The application is the only sending-queue owner. SQLite under `/data/outreach.db`
stores the queue, suppression list, inbox receipts and SMTP-attempt ledger locally
on the VPS. Schema version 5 adds fields/tables without deleting drafts or history.

## Contact delivery states

| State | Meaning | Pending messages |
| --- | --- | --- |
| `SENT` | SMTP accepted the message; inbox delivery is not established | Reviewed follow-ups may remain if explicitly enabled |
| `BOUNCED` | Permanent DSN failure or permanent SMTP recipient rejection | Cancelled; address suppressed globally |
| `REPLIED` | Human reply detected | Cancelled; sales review task created |
| `UNSUBSCRIBED` | Opt-out link, opt-out reply or manual do-not-contact | Cancelled; address suppressed globally |

An empty delivery state means no delivery outcome has been recorded. Research,
approval and queue status remain separate. The four states are mutually exclusive
current contact outcomes; individual messages and events retain their history.
Opt-out takes precedence over subsequent acceptance, replies or bounces. A normal
reply stops the sequence without labelling the person globally opted out. Vacation
responses and temporary delivery delays hold the conversation and cancel pending
messages; they are not permanent bounces. Restart recovery never resends an
ambiguous submission.

Inbox monitoring uses the existing TLS IMAP client every 30 seconds while the
worker is ON, including when sending is OFF. It uses read-only selection, bounded
UID reads, UIDVALIDITY tracking, atomic event handling and per-contact message
fingerprints. A DSN with several recipients applies each recipient's own status.
English opt-out phrases are supported; an unrecognized reply still stops the
sequence for review. Choose a mailbox/folder that receives replies **and** DSNs;
messages filtered into unmonitored folders will not be detected. Gmail can use
IMAP with an appropriately configured account/app password. Gmail OAuth/API
`messages.list` or `watch` + `history.list` is not added or required by this change.
Google's API alternative needs its own OAuth authorization, reliable cursor
storage, watch renewal and full-sync recovery on an expired history cursor.

## Durable sending queue

- Each contact has one row per sequence step and one unique outbound Message-ID.
- Claiming, mailbox quotas and attempt reservation happen under a SQLite write
  lock. A second sender cannot claim the same message. A recorded acceptance or
  uncertain attempt cannot be resent by accidentally resetting the queue state.
- Limits use the normalized SMTP-login email (or sender email for generic relay
  logins) and rolling windows: default **20 per
  24 hours**, **10 per hour**, minimum **180 seconds** between attempts. Settings
  exposes all three limits. Changing an SMTP host/password does not reset the
  mailbox's budget. Aliases using one email login share its budget. This
  deployment configures one mailbox at a time; it is not
  a multi-mailbox rotation system. Legacy sends lacking a mailbox ledger count
  conservatively against any sender until their window expires.
- Sending/uncertain reservations count toward quotas. Explicit non-acceptance
  does not count as accepted mail. All attempts still respect the minimum gap.
- Explicit temporary SMTP 4xx refusals retry after one hour, then two hours,
  with at most **3 total attempts**. Every retry passes the same freshness,
  approval, sending-window, inbox and suppression checks. Exhaustion holds the
  contact and marks the message failed. Manual resumption does not reset the
  attempt budget.
- SMTP login/TLS/configuration failures pause sending for correction. Permanent
  sender/DATA policy rejections hold for review rather than falsely suppressing
  a valid recipient. Timeouts/disconnects with an unknown DATA outcome become
  `uncertain`, never automatic retries.
- Contact stop and pause controls are checked again after SMTP login, before
  submission. A message already being accepted by SMTP cannot be recalled; any
  later follow-ups are cancelled.
  A global pause before submission leaves the unsent item queued for Resume;
  a reply, opt-out or conversation hold cancels it instead.
- Permanent SMTP recipient rejection records failure and global suppression in
  one transaction. A database error rolls back both operations rather than
  leaving a recorded hard bounce without its suppression entry.

**Operations → Email delivery** shows state counts and mailbox usage. Queue,
attempt logs and the suppression list are collapsed below. A do-not-contact
address can be added before importing it. Re-import, reapproval and restart do
not clear suppression. There is deliberately no automatic unsuppress action.

Authenticated APIs: `GET /api/delivery?limit=50&offset=0` returns paginated queue,
suppression and attempt data plus total counts; `POST /api/suppression` accepts
`email` and `reason`. Tokens, passwords and message bodies are absent from the
delivery response. Existing per-contact suppression remains available.

## Unsubscribe

Outgoing messages include a visible plain-text opt-out URL, reply instructions,
`List-Unsubscribe: <https://.../unsubscribe/TOKEN>` and
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`.

The tokenized POST works without login, cookies, redirects or another confirmation.
Repeated POSTs are idempotent. GET only renders a confirmation form, so link
scanners do not unsubscribe recipients. Suppression and pending-message
cancellation commit together before success is returned.

Use a **lasting HTTPS domain** that keeps old tokens reachable. A temporary
`trycloudflare.com` URL remains usable for dashboard/research, but fails sending
readiness because links expire when that quick tunnel is replaced. A named
Cloudflare Tunnel on a stable domain can serve the application. Keep the database
and tokens across deployments. Cloudflare Access or other upstream authentication
must allow the public unsubscribe route, including POST; verify this externally.

The SMTP provider must DKIM-sign the two unsubscribe headers as required by
[RFC 8058](https://www.rfc-editor.org/rfc/rfc8058). Header generation alone does
not verify that provider signing, domain authentication or inbox placement works.
[Google's sender guidelines](https://support.google.com/mail/answer/81126?hl=en)
require one-click unsubscribe and a visible body link for bulk marketing/subscribed
mail. The app processes received opt-outs immediately, rather than waiting for
Google's recommended 48-hour maximum. This change does not raise the application's
sending limits or enable sending/follow-ups.

## Deployment and checks

Back up the database before upgrading. Version 5 is additive, but older app
versions intentionally refuse to open it; rollback requires the matching backup.
Automated tests cover local TLS SMTP/IMAP fixtures, cancellation, multi-recipient
DSNs, duplicate inbox processing, concurrent claims, retry exhaustion, rolling
quotas, migration and unauthenticated one-click POST. No external email is needed.
Live mailbox/provider acceptance, DKIM coverage and externally reachable permanent
unsubscribe links require deployment checks before sending is enabled.

Official Gmail API references (alternative transport):
[list messages](https://developers.google.com/workspace/gmail/api/guides/list-messages),
[synchronization and history recovery](https://developers.google.com/workspace/gmail/api/guides/sync).
