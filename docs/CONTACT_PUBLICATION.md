# Current publication proof for contact addresses

A matching company domain does not establish that an address was published. Manual and CSV intake may retain an address for research, but verification and outreach require current saved evidence from the official company website. The recipient's source page must contain the exact email, or have crawler extraction proof for a public mailto link or structured contact entry. Extraction proof is bound to that page's HTML hash.

Publication must belong to the current research attempt and be no older than 30 days; future captures beyond the allowed clock skew are excluded. An indexed snippet, guessed address, unrelated source, removed address or hidden script is insufficient. Dedicated privacy/security/automated inbox exclusions still apply. Other-domain and profile contacts retain their additional identity and ownership review gates.

The dashboard explains the source hold and disables verification until proof exists. Saving an unpublished contact does not queue a verifier request. A successful contact-page capture can attach a pending record to its actual publication URL; suppressed records and established outreach history retain their original source. The workflow maps distinguish stored addresses from currently published contacts.

Approval freezes the recipient publication page together with the offer and country sources. A changed page invalidates approval even if the email remains visible. Send-time checks use the same database transaction and record both source and sequence holds when publication is no longer valid. Publication is rechecked after verification spacing waits.

Seventeen regression cases cover these conditions. See the [current full audit](COMPLETE_WORKFLOW_AUDIT.md) for executed suite totals and node mappings. Tests use controlled verification responses; they do not establish real mailbox existence.

The [live contact recovery check](contact-fallback-live-check.json) refreshed two pages each on Skindays and SmartRoof in an isolated database. Skindays returned four previously known published inbox candidates, all accepted by the publication gate. SmartRoof returned none. Both captures remained partial. No verification jobs ran, normal operational data stayed unchanged, and no message was sent. Buyer relevance, permission and genuine business need remain separate reviews.

LinkedIn, X and PeoplePerHour can supply accessible public discovery signals. This change does not grant access to private emails or make restricted pages universally crawlable. The configured local Reacher endpoint still needs a running backend before actual mailbox checks can be accepted.

Reproduce:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/contact-publication-tests.xml
.\.venv\Scripts\python.exe scripts/verify_complete_workflow.py
.\.venv\Scripts\python.exe scripts/verify_contact_fallback_live.py
```

The live script requires the existing pilot candidates, uses a fresh isolated directory, and leaves verification and sending disabled.
