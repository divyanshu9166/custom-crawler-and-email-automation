import json
import sqlite3
import time
from contextlib import contextmanager


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS leads (
 id INTEGER PRIMARY KEY, domain TEXT NOT NULL UNIQUE, website TEXT NOT NULL,
 company TEXT NOT NULL, campaign TEXT NOT NULL CHECK(campaign IN ('A','B')),
 country TEXT NOT NULL DEFAULT '', country_source TEXT NOT NULL DEFAULT '',
 timezone TEXT NOT NULL DEFAULT '', business_type TEXT NOT NULL DEFAULT '',
 source_url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
 service TEXT NOT NULL DEFAULT '', fit_notes TEXT NOT NULL DEFAULT '',
 findings TEXT NOT NULL DEFAULT '[]', research_notes TEXT NOT NULL DEFAULT '',
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id), url TEXT NOT NULL,
 title TEXT NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL, fetched_at REAL NOT NULL,
 UNIQUE(lead_id,url)
);
CREATE TABLE IF NOT EXISTS contacts (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id), email TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL,
 verification TEXT NOT NULL DEFAULT 'unverified', verification_raw TEXT NOT NULL DEFAULT '{}',
 verified_at REAL, status TEXT NOT NULL DEFAULT 'new', eligibility_basis TEXT NOT NULL DEFAULT '',
 reviewed_at REAL, unsubscribe_token TEXT NOT NULL UNIQUE, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id), step INTEGER NOT NULL,
 subject TEXT NOT NULL, body TEXT NOT NULL, evidence_ids TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'draft', due_at REAL, sent_at REAL,
 message_id TEXT NOT NULL UNIQUE, error TEXT NOT NULL DEFAULT '', UNIQUE(contact_id,step)
);
CREATE TABLE IF NOT EXISTS suppression (
 email TEXT PRIMARY KEY, reason TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, due_at REAL NOT NULL, started_at REAL,
 error TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, external_id TEXT UNIQUE, kind TEXT NOT NULL,
 contact_id INTEGER REFERENCES contacts(id), detail TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules (
 id INTEGER PRIMARY KEY, query TEXT NOT NULL, campaign TEXT NOT NULL, country_hint TEXT NOT NULL,
 result_limit INTEGER NOT NULL DEFAULT 10, interval_hours INTEGER NOT NULL DEFAULT 24,
 next_run REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS crawls (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 report TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
 lead_id INTEGER PRIMARY KEY REFERENCES leads(id), stage TEXT NOT NULL DEFAULT 'new',
 details TEXT NOT NULL DEFAULT '{}', cold_email_hold INTEGER NOT NULL DEFAULT 0,
 version INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS activities (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 contact_id INTEGER REFERENCES contacts(id), channel TEXT NOT NULL, kind TEXT NOT NULL,
 note TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '', happened_at REAL NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 kind TEXT NOT NULL, title TEXT NOT NULL, due_at REAL NOT NULL,
 state TEXT NOT NULL DEFAULT 'open', outcome TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 details TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft',
 delivery_reference TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deliverables (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id), kind TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, evidence_ids TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'draft', delivery_reference TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_due ON jobs(state,due_at);
CREATE INDEX IF NOT EXISTS messages_due ON messages(state,due_at);
CREATE INDEX IF NOT EXISTS activities_company ON activities(lead_id,happened_at);
CREATE INDEX IF NOT EXISTS tasks_due ON tasks(state,due_at);
CREATE TABLE IF NOT EXISTS financial_entries (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 kind TEXT NOT NULL CHECK(kind IN ('acquisition_cost','delivery_cost','maintenance_cost','payment','refund')),
 currency TEXT NOT NULL CHECK(currency IN ('USD','GBP')), amount_minor INTEGER NOT NULL CHECK(amount_minor>0),
 reference TEXT NOT NULL, note TEXT NOT NULL, happened_at REAL NOT NULL, created_at REAL NOT NULL,
 void_reason TEXT NOT NULL DEFAULT '', voided_at REAL, UNIQUE(lead_id,reference)
);
CREATE TABLE IF NOT EXISTS client_plans (
 id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
 kind TEXT NOT NULL CHECK(kind IN ('maintenance','expansion','case_study')),
 title TEXT NOT NULL, scope TEXT NOT NULL, due_at REAL NOT NULL,
 state TEXT NOT NULL DEFAULT 'planned', version INTEGER NOT NULL DEFAULT 0,
 agreement_reference TEXT NOT NULL DEFAULT '', permission_reference TEXT NOT NULL DEFAULT '',
 outcome_reference TEXT NOT NULL DEFAULT '', outcome_notes TEXT NOT NULL DEFAULT '',
 client_snapshot TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS finance_company ON financial_entries(lead_id,happened_at);
CREATE INDEX IF NOT EXISTS plans_due ON client_plans(state,due_at);
CREATE INDEX IF NOT EXISTS evidence_current ON evidence(lead_id,fetched_at);
CREATE INDEX IF NOT EXISTS events_kind_recent ON events(kind,id);
CREATE INDEX IF NOT EXISTS crawls_company ON crawls(lead_id,id);
CREATE INDEX IF NOT EXISTS contacts_company ON contacts(lead_id);
CREATE INDEX IF NOT EXISTS events_contact_kind ON events(contact_id,kind,created_at);
CREATE TABLE IF NOT EXISTS send_attempts (
 id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL REFERENCES messages(id),
 mailbox TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL,
 outcome TEXT NOT NULL DEFAULT 'sending', smtp_code INTEGER, error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS attempts_mailbox ON send_attempts(mailbox,started_at);
CREATE INDEX IF NOT EXISTS attempts_message ON send_attempts(message_id,id);
CREATE TABLE IF NOT EXISTS inbound_receipts (
 fingerprint TEXT PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id), created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_groups (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
 goal TEXT NOT NULL CHECK(goal IN ('A','B')), state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','paused')),
 is_default INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS campaign_default ON campaign_groups(goal) WHERE is_default=1;
"""


class DB:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version > 8:
                raise RuntimeError("Database belongs to a newer application version")
            con.executescript(SCHEMA)
            columns = {r[1] for r in con.execute("PRAGMA table_info(leads)")}
            for name, definition in {
                "lead_kind": "TEXT NOT NULL DEFAULT 'website'",
                "profile_url": "TEXT NOT NULL DEFAULT ''",
                "website_status": "TEXT NOT NULL DEFAULT 'present'",
                "profile_review": "TEXT NOT NULL DEFAULT '{}'",
                "discovery_country": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in columns:
                    con.execute(f"ALTER TABLE leads ADD COLUMN {name} {definition}")
            columns = {r[1] for r in con.execute('PRAGMA table_info(contacts)')}
            if 'delivery_state' not in columns:
                con.execute("ALTER TABLE contacts ADD COLUMN delivery_state TEXT NOT NULL DEFAULT '' CHECK(delivery_state IN ('','SENT','BOUNCED','REPLIED','UNSUBSCRIBED'))")
            if version < 5:
                con.execute("""UPDATE contacts SET delivery_state=CASE
                    WHEN EXISTS(SELECT 1 FROM suppression s WHERE s.email=contacts.email AND (lower(s.reason) LIKE '%bounce%' OR s.reason='SMTP permanent recipient rejection')) THEN 'BOUNCED'
                    WHEN status='suppressed' OR EXISTS(SELECT 1 FROM suppression s WHERE s.email=contacts.email) THEN 'UNSUBSCRIBED'
                    WHEN status='replied' THEN 'REPLIED'
                    WHEN EXISTS(SELECT 1 FROM messages m WHERE m.contact_id=contacts.id AND m.sent_at IS NOT NULL) THEN 'SENT'
                    ELSE '' END""")
            for goal, name in [('A', 'Campaign A - Enquiries and bookings'), ('B', 'Campaign B - Ecommerce growth')]:
                con.execute('INSERT OR IGNORE INTO campaign_groups(name,goal,is_default,created_at,updated_at) VALUES(?,?,1,?,?)', (name, goal, time.time(), time.time()))
            columns = {r[1] for r in con.execute('PRAGMA table_info(leads)')}
            for name, definition in {'campaign_id': 'INTEGER REFERENCES campaign_groups(id)',
                                     'deleted_at': 'REAL', 'delete_reason': "TEXT NOT NULL DEFAULT ''"}.items():
                if name not in columns:
                    con.execute(f'ALTER TABLE leads ADD COLUMN {name} {definition}')
            con.execute('UPDATE leads SET campaign_id=(SELECT id FROM campaign_groups WHERE goal=leads.campaign AND is_default=1) WHERE campaign_id IS NULL')
            if 'campaign_id' not in {r[1] for r in con.execute('PRAGMA table_info(schedules)')}:
                con.execute('ALTER TABLE schedules ADD COLUMN campaign_id INTEGER REFERENCES campaign_groups(id)')
            if 'profile_first' not in {r[1] for r in con.execute('PRAGMA table_info(schedules)')}:
                con.execute('ALTER TABLE schedules ADD COLUMN profile_first INTEGER NOT NULL DEFAULT 0 CHECK(profile_first IN (0,1))')
            if 'discovery_source' not in {r[1] for r in con.execute('PRAGMA table_info(schedules)')}:
                con.execute("ALTER TABLE schedules ADD COLUMN discovery_source TEXT NOT NULL DEFAULT 'mixed' CHECK(discovery_source IN ('mixed','google_maps'))")
            con.executescript('''
                CREATE INDEX IF NOT EXISTS leads_campaign_group ON leads(campaign_id,deleted_at,id);
                CREATE TRIGGER IF NOT EXISTS leads_default_campaign AFTER INSERT ON leads WHEN NEW.campaign_id IS NULL
                BEGIN UPDATE leads SET campaign_id=(SELECT id FROM campaign_groups WHERE goal=NEW.campaign AND is_default=1) WHERE id=NEW.id; END;
                CREATE TRIGGER IF NOT EXISTS leads_matching_campaign BEFORE UPDATE OF campaign_id,campaign ON leads
                WHEN NEW.campaign_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM campaign_groups WHERE id=NEW.campaign_id AND goal=NEW.campaign)
                BEGIN SELECT RAISE(ABORT,'Campaign business goal does not match prospect'); END;
                CREATE TRIGGER IF NOT EXISTS leads_matching_campaign_insert BEFORE INSERT ON leads
                WHEN NEW.campaign_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM campaign_groups WHERE id=NEW.campaign_id AND goal=NEW.campaign)
                BEGIN SELECT RAISE(ABORT,'Campaign business goal does not match prospect'); END;
            ''')
            # Actual From address and Message-ID header per send (aliases and multiple domains).
            columns = {r[1] for r in con.execute('PRAGMA table_info(send_attempts)')}
            for name in ('sender', 'header_message_id'):
                if name not in columns:
                    con.execute(f"ALTER TABLE send_attempts ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
            con.execute("CREATE INDEX IF NOT EXISTS attempts_header ON send_attempts(header_message_id) WHERE header_message_id<>''")
            con.execute("PRAGMA user_version=8")
            con.execute("""CREATE INDEX IF NOT EXISTS events_job_activity ON events
                ((CASE WHEN json_valid(detail) THEN json_extract(detail,'$.job_id') END),id)
                WHERE kind IN ('discovery_started','discovery_progress','discovery')""")
            con.execute("""CREATE INDEX IF NOT EXISTS jobs_lead_activity ON jobs
                ((CASE WHEN json_valid(payload) THEN json_extract(payload,'$.lead_id') END),kind,id)""")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def all(self, sql, params=()):
        with self.connect() as con:
            return [dict(row) for row in con.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.connect() as con:
            return con.execute(sql, params).lastrowid

    def event(self, kind, detail, contact_id=None, external_id=None):
        self.execute("INSERT OR IGNORE INTO events(kind,detail,contact_id,external_id,created_at) VALUES(?,?,?,?,?)",
                     (kind, json.dumps(detail), contact_id, external_id, time.time()))

    def get(self, key, default=""):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set(self, key, value):
        self.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, str(value)))

    def enqueue(self, kind, payload):
        encoded = json.dumps(payload, sort_keys=True)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            deleted = con.execute('SELECT 1 FROM leads WHERE deleted_at IS NOT NULL AND (id=? OR id=(SELECT lead_id FROM contacts WHERE id=?))', (payload.get('lead_id'), payload.get('contact_id'))).fetchone()
            if deleted:
                raise ValueError('Deleted prospects cannot queue new work')
            row = con.execute("SELECT id FROM jobs WHERE kind=? AND payload=? AND state IN ('pending','running')",
                              (kind, encoded)).fetchone()
            if row:
                return row[0]
            return con.execute("INSERT INTO jobs(kind,payload,due_at,created_at) VALUES(?,?,?,?)",
                               (kind, encoded, time.time(), time.time())).lastrowid

    def claim(self, kinds=None):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("""UPDATE jobs SET state='cancelled',error='Prospect deleted; pending work cancelled'
                WHERE state='pending' AND EXISTS(SELECT 1 FROM leads l WHERE l.deleted_at IS NOT NULL
                AND (l.id=json_extract(jobs.payload,'$.lead_id') OR l.id=(SELECT lead_id FROM contacts WHERE id=json_extract(jobs.payload,'$.contact_id'))))""")
            rows = con.execute("SELECT * FROM jobs WHERE state='pending' AND due_at<=? ORDER BY CASE kind WHEN 'verify' THEN 0 WHEN 'screenshot' THEN 1 ELSE 2 END,due_at,id",
                               (time.time(),)).fetchall()
            # Research and screenshots of one lead must not execute simultaneously across lanes.
            busy = {json.loads(r[0]).get("lead_id") for r in con.execute(
                "SELECT payload FROM jobs WHERE state='running' AND kind IN ('research','screenshot','performance','contact_research','professional_research','social_research','prepare')")}
            row = next((r for r in rows if (not kinds or r["kind"] in kinds)
                        and (r["kind"] not in {"research", "screenshot", "performance", 'contact_research','professional_research','social_research','prepare'}
                             or json.loads(r["payload"]).get("lead_id") not in busy)), None)
            if not row:
                return None
            con.execute("UPDATE jobs SET state='running',attempts=attempts+1,started_at=? WHERE id=?",
                        (time.time(), row["id"]))
            return dict(row)

    def recover(self):
        # Only call at single-worker startup. Outbound acceptance may have happened before a crash.
        with self.connect() as con:
            con.execute("""UPDATE crawls SET report=json_set(report,'$.status','interrupted',
                        '$.recovery_note','Worker restarted; preserved captures are partial, not a completed crawl')
                        WHERE json_extract(report,'$.status') IN ('running','researching')""")
            con.execute("UPDATE jobs SET state='pending' WHERE state='running'")
            con.execute("UPDATE contacts SET status='hold' WHERE status='active' AND id IN (SELECT contact_id FROM messages WHERE state='sending')")
            con.execute("UPDATE messages SET state='uncertain',error='Process restarted during send; reconcile manually' WHERE state='sending'")
            con.execute("UPDATE send_attempts SET outcome='uncertain',finished_at=?,error='Process restarted during send; reconcile manually' WHERE outcome='sending'", (time.time(),))

    def suppress(self, email, reason, con=None, *, state=None):
        if con is None:
            with self.connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                self.suppress(email, reason, connection, state=state)
            return
        email = email.strip().lower()
        state = state or ('BOUNCED' if reason in {'bounce', 'SMTP permanent recipient rejection'} else 'UNSUBSCRIBED')
        if state not in {'BOUNCED', 'UNSUBSCRIBED'}:
            raise ValueError('Invalid suppression state')
        con.execute("INSERT INTO suppression VALUES(?,?,?) ON CONFLICT(email) DO UPDATE SET reason=excluded.reason",
                    (email, reason, time.time()))
        # A later bounce must never erase an explicit opt-out.
        con.execute("UPDATE contacts SET status='suppressed',delivery_state=CASE WHEN delivery_state='UNSUBSCRIBED' THEN delivery_state ELSE ? END WHERE email=? COLLATE NOCASE", (state, email))
        con.execute("UPDATE messages SET state='cancelled' WHERE contact_id IN (SELECT id FROM contacts WHERE email=?) AND state IN ('draft','queued')", (email,))
