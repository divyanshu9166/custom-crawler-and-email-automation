# Focused prospect workspace — 18 October 2026

The default screen is Pipeline. Choose a prospect on the left; read the business fit
and proposed approach, then review its initial email. The next-action card offers one
relevant action: research the business, find a published contact, create the email or
review the saved draft. A saved draft takes precedence over an older preparation error.

The normal view contains the recipient, mailbox-check status, subject and email editor.
**Save draft** never sends. The current prospect is retained in the URL as `?prospect=ID`;
`#email-sequence` opens its email section. Other contacts, original source captures,
manual qualification, audits, technical reports, sales records and history remain under
**Research details & advanced tools**. Recipient checks and sending approval have their
own collapsed section. Research controls remain in Settings; the header no longer shows
conflicting pause/resume actions next to a disabled-sending indicator.

Settings places the AI writer first. Sending-mailbox setup, detailed research preferences
and account credentials are separate expandable groups. A sending setup checklist is not
a prerequisite to writing a draft. Research and global sending switches remain available.

## One initial email

`FOLLOWUPS_ENABLED=false` is the production default. The writer requests exactly one
message at step 0 with a 1,200-token final-output budget. Validation, source support,
recipient/publication checks, approval snapshots and sending gates still apply. A supported
proposal is not proof of a client's requirement or buying intent; final copy review remains
necessary. There is no template or alternate-model fallback.

An old unapproved four-message pilot can use **Keep initial email only**. The transaction
retains the first message, including user edits, and stores the complete follow-up messages
in a `followup_drafts_archived` audit event before removing them from the working drafts.
It updates the retained AI-origin record without claiming a new model generation. It refuses
approved, scheduled, uncertain or submitted messages. Such history requires delivery review;
it is never silently reset. Existing follow-up rows are excluded from dispatch while the
feature is off. Single-email acceptance closes the cold-email sequence and schedules no
follow-up; actual replies remain visible to inbox monitoring.

The optional legacy flag exists for explicitly configured prior pilots and legacy regression
coverage. There is no follow-up toggle in the routine product flow. New workspaces and this
deployment keep it off; further outreach behavior awaits a separate user instruction.
