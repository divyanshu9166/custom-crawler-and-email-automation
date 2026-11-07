# Google Workspace mailbox pool

This workspace can operate up to 21 independent sender logins: the primary
mailbox plus 20 extra mailboxes. It does not treat aliases as independent
accounts; aliases share the owning account's quota, inbox monitor and minimum
send interval.

## Safe onboarding

1. In **Settings → Sending mailboxes**, open **Add Google Workspace inboxes in
   one step** and paste one existing Workspace address per line.
2. The first address becomes the primary connection if it is blank. The others
   are added as disabled independent mailboxes with `smtp.gmail.com:587`
   (STARTTLS) and `imap.gmail.com:993`.
3. For each account, edit its row and add only that account's own Google app
   password to both SMTP and IMAP password fields. Passwords stay on the VPS
   and are never returned by the API or UI. Do not put them in a CSV, source
   repository, browser notes or chat.
4. Use **Test connection** on that row. It signs in to SMTP and IMAP and opens
   the selected inbox read-only; it never sends a message.
5. Use the domain's **Check DNS** control, then check the domain-authenticated
   box on a mailbox only after SPF, DKIM and DMARC are verified. Finally,
   explicitly enable that individual mailbox. Every one of these edits pauses
   sending.

Google can restrict app passwords by Workspace policy. If an account cannot
create or use an app password, leave it disabled. This version does not pretend
that a normal account password or a copied password is OAuth; Gmail OAuth needs
separate Google Cloud consent credentials and is not silently substituted.

## Default pilot protection

The batch helper intentionally stages a 3-message rolling-24-hour limit, a
1-message rolling-hour limit, a 15-minute global gap and a 9-message per-domain
rolling-24-hour cap. It also disables catch-all recipients. These are pilot
defaults, not a claim that a provider will accept or place every message.

Only change limits after checking the connection health, provider account status,
real recipient relevance and the dashboard's delivery outcomes. Sending remains
off and paused after staging.

## Runtime safeguards

- independent inboxes rotate by least recent 24-hour use;
- a message is claimed atomically, so two worker cycles cannot submit it twice;
- a later sequence step keeps the same sender/login whenever that mailbox still
  exists;
- every mailbox has its own rolling daily/hourly budget and inbox monitor;
- each domain has a separate total cap across all its mailbox logins;
- a hard bounce, reply or opt-out cancels that contact's pending messages;
- suppression persists across campaigns and imports;
- a 14-day sender-domain circuit breaker holds a domain after more than 5% hard
  bounces with at least 10 accepted contacts, or more than 5% unsubscribes with
  at least 20 accepted contacts.

SMTP acceptance is not inbox placement. The dashboard labels it as accepted and
keeps uncertain submission attempts out of automatic retry.

## Operating model

Start with only evidence-backed, human-reviewed initial emails. Keep automatic
approval and follow-ups off during the pilot. Once a mailbox pool is stable,
approval can be done in Campaigns, but recipient verification, one-company
deduplication, suppression and the domain health guard still apply. Do not use
the extra inboxes to resend to a person who bounced, replied, opted out or was
held for review.
