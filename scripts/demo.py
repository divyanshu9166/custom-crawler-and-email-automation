"""Create clearly labelled fictional data in an isolated demo database. Never creates jobs or sends."""
import argparse
import json
import time
from pathlib import Path

from outreach.config import Settings
from outreach.db import DB
from outreach.research import add_lead, add_contact
from outreach.campaigns import review_lead


def seed(folder):
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False)
    db = DB(settings.database)
    if db.one("SELECT COUNT(*) n FROM leads")["n"]:
        if db.get("demo") != "true":
            raise ValueError("Refusing to treat an existing non-demo database as fictional demo data")
        return
    lid = add_lead(db, "Example Studio · DEMO", "https://example.com", "A", "https://example.com", "UK")
    text = "FICTIONAL DEMO CONTENT: Our studio serves businesses in the United Kingdom. Contact our team to book a consultation. Illustrative contact: demo@example.com"
    eid = db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                     (lid, "https://example.com", "Illustrative website evidence — not a real audit", text, "demo", time.time()))
    review_lead(db, lid, {"company": "Example Studio · DEMO", "country": "UK", "country_source": "https://example.com",
                         "country_quote": "United Kingdom",
                         "timezone": "Europe/London", "business_type": "corporate", "service": "website_improvement",
                         "fit_notes": "Illustrative data only; this is not a real qualified company.", "evidence_id": eid,
                         "quote": "Contact our team to book a consultation.",
                         "observation": "Your page invites visitors to contact the team for a consultation.",
                         "suggestion": "Explain what the first consultation includes beside the inquiry link."})
    cid = add_contact(db, lid, "demo@example.com", "https://example.com", "Alex Demo", "Illustrative founder")
    # Demo copy is explicitly illustrative; live generation never uses this path.
    from outreach.campaigns import draft_sequence
    finding = json.loads(db.one('SELECT findings FROM leads WHERE id=?', (lid,))['findings'])[0]
    for item in draft_sequence('Example Studio · DEMO', 'website_improvement', finding, 'https://example.com', 'Alex Demo'):
        db.execute('INSERT INTO messages(contact_id,step,subject,body,evidence_ids,message_id) VALUES(?,?,?,?,?,?)',
                   (cid, item['step'], item['subject'], item['body'], json.dumps(item['evidence_ids']),
                    f'<demo-{cid}-{item["step"]}@example.com>'))
    db.event('drafts_created', {'method': 'offline_demo', 'steps': 4}, cid)
    db.execute("UPDATE contacts SET verification='unknown',verification_raw=? WHERE id=?",
               (json.dumps({"demo": True, "note": "Not verified; fictional contact. Sending is blocked."}), cid))
    add_lead(db, "Example D2C · DEMO", "https://example.org", "B", "https://example.org", "US")
    db.set("paused", "true")
    db.set("demo", "true")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/demo")
    args = parser.parse_args()
    seed(Path(args.data_dir))
    print("Created isolated fictional demo data; no provider calls, verification or sends performed.")
