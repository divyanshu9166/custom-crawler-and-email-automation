# Bulk sending: mailboxes, approval and catch-all — 23 October 2026

Operator decisions (23 October): bulk/automatic approval without a separate UK
sole-trader/partnership filter, catch-all addresses allowed under a separate cap, and no
mailbox warm-up ramp. Every other approval and send gate is unchanged: a fresh sendable
Reacher verdict, AI-written draft with current sources, suppression list, one active contact
per company, opt-out footer/link, send window, Sending ON and resumed.

## Multiple mailboxes and per-mailbox limits

Settings → **05 · Sending mailboxes** adds up to 20 extra mailboxes (sender email, SMTP, IMAP,
daily and hourly limit, on/off). The primary mailbox keeps using sections 01-04, including
its own daily/hourly limit. Passwords are saved privately in `workspace-settings.json`
and are never returned by the API; a blank password keeps the saved one. Saving pauses sending.

`outreach/mailboxes.py` presents each mailbox as a Settings copy, so the existing SMTP,
message and inbox code runs per mailbox. Sending (`mail.send_one`):

- a mailbox is ready only when its own inbox is current, its minimum gap has passed and it
  is under its rolling 24-hour and hourly limits (usage comes from `send_attempts.mailbox`);
- each email goes from the ready mailbox with the fewest sends in the last 24 hours;
- follow-ups and later steps stay on the mailbox that sent the first email;
- each mailbox's inbox is polled separately (`mail.poll_all`); one failing inbox does not
  stop the others. Replies, bounces and opt-outs are matched to contacts as before.

Per-mailbox usage, catch-all usage and inbox state are shown in the mailbox list and in
`/api/delivery`.

### Aliases, domains and Message-IDs

- **Separate logins** (e.g. `info@` and `sales@` each with their own password) are separate
  mailboxes with their own limits.
- **Aliases** (another address sent through the same SMTP login, e.g. Google Workspace
  "send mail as") must be ticked as *Alias*. They share that login's daily/hourly limit,
  minimum gap and inbox; sending rotates the From address across the aliases, and follow-ups
  keep the exact address that sent the first email. A second non-alias entry on the same login
  is rejected.
- **Domain authentication** is confirmed per sender domain (the primary's checkbox, or the
  mailbox form). A mailbox on an unconfirmed domain does not send.
- **Domain cap** (optional): a daily total across every mailbox and alias on one domain,
  set in the Domains list. 0 = no cap.
- **Message-ID** headers use the sending address's domain. The stored draft ID is unchanged
  (it is part of the approval snapshot); the header actually sent is recorded on the send
  attempt, used for follow-up threading, and matched when replies arrive.

## Catch-all addresses

`CATCH_ALL_SHARE` (Settings → Sending limits, default 20%) is the share of each mailbox's
daily limit that may go to catch-all recipients (at least 1 while enabled; 0 = safe only).
Catch-all sending pauses itself when more than 5% of catch-all recipients sent in the last
14 days bounced (minimum sample 10). Approval, verification holds and dashboard counts use
the same rule (`mailboxes.sendable`).

## Bulk and automatic approval

- Campaigns → select prospects → **Approve prepared emails** approves each prepared contact
  with a recorded automatic basis. Contacts that fail any check are reported with the reason.
- Settings → Research → **Automatically approve prepared emails** (off by default) approves a
  draft as soon as it is prepared and its mailbox check passes, so research → email → send
  runs without clicks while Sending is ON and resumed.

Both record `bulk_approved`/`auto_approved` events; skipped automatic approvals record
`auto_approve_skipped` with the reason.

## Limits

Volume is bounded by mailbox limits and your provider's own limits. Domain authentication
(SPF/DKIM/DMARC) and sending reputation remain your responsibility; no warm-up ramp is applied.
