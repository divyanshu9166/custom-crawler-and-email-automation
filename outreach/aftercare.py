"""Post-delivery plans and permission-reviewed case studies. No external publication."""
import html
import json
import math
import time

KINDS = {'maintenance', 'expansion', 'case_study'}
TRANSITIONS = {'planned': {'reviewed', 'declined'}, 'reviewed': {'agreed', 'declined'},
               'agreed': {'completed', 'declined'}, 'completed': set(), 'declined': set()}


def accepted_client(con, lead_id):
    row = con.execute('SELECT l.company,s.stage,s.details FROM leads l JOIN sales s ON s.lead_id=l.id WHERE l.id=?', (lead_id,)).fetchone()
    if not row or row['stage'] != 'completed':
        raise ValueError('Aftercare requires a completed client delivery with recorded acceptance')
    details = json.loads(row['details'])
    if len(details.get('acceptance_reference', '').strip()) < 12 or len(details.get('outcome_notes', '').strip()) < 12:
        raise ValueError('Record client acceptance and measured or inconclusive outcomes first')
    return {'company': row['company'], 'acceptance_reference': details['acceptance_reference'],
            'outcome_notes': details['outcome_notes'], 'success_metric': details.get('success_metric', ''),
            'confirmed_problem': details.get('confirmed_problem', ''), 'baseline_notes': details.get('baseline_notes', '')}


def create(db, lead_id, value):
    kind, title, scope, due = value['kind'], value['title'].strip(), value['scope'].strip(), value['due_at']
    if kind not in KINDS or len(title) < 8 or len(scope) < 20 or not math.isfinite(due) or due <= time.time():
        raise ValueError('Provide a plan kind, title, useful scope and future review date')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        snapshot = accepted_client(con, lead_id)
        previous = con.execute('SELECT id,scope FROM client_plans WHERE lead_id=? AND kind=? AND title=? AND due_at=?',
                               (lead_id, kind, title, due)).fetchone()
        if previous:
            if previous['scope'] != scope:
                raise ValueError('This dated plan already exists with a different scope')
            return previous['id']
        pid = con.execute('INSERT INTO client_plans(lead_id,kind,title,scope,due_at,client_snapshot,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                          (lead_id, kind, title, scope, due, json.dumps(snapshot), time.time(), time.time())).lastrowid
        con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                    ('client_plan', json.dumps({'lead_id': lead_id, 'plan_id': pid, 'state': 'planned'}), time.time()))
        return pid


def update(db, plan_id, value):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM client_plans WHERE id=?', (plan_id,)).fetchone()
        if not row:
            raise ValueError('Client plan not found')
        if row['version'] != value['version']:
            raise ValueError('Plan changed; reload before saving')
        state = value['state']
        if state not in TRANSITIONS[row['state']]:
            raise ValueError('Review the plan, then record agreement and completion in order')
        # Permission remains explicit even for a draft; agreement and publication references are not receipt validation.
        permission = value.get('permission_reference', '').strip() or row['permission_reference']
        agreement = value.get('agreement_reference', '').strip() or row['agreement_reference']
        outcome = value.get('outcome_reference', '').strip()
        notes = value.get('outcome_notes', '').strip()
        if state != 'declined':
            accepted_client(con, row['lead_id'])
            if row['kind'] == 'case_study' and (len(permission) < 12 or value.get('client_permission_confirmed') is not True):
                raise ValueError('Case-study review requires explicit client permission and its reference')
        if state == 'agreed' and len(agreement) < 12:
            raise ValueError('Record the actual scope agreement before work proceeds')
        if state in {'completed', 'declined'} and len(notes) < 12:
            raise ValueError('Record what actually happened, including inconclusive results')
        if state == 'completed' and len(outcome) < 12:
            raise ValueError('Record actual delivery or publication reference; this action does not publish')
        con.execute('UPDATE client_plans SET state=?,version=version+1,permission_reference=?,agreement_reference=?,outcome_reference=?,outcome_notes=?,updated_at=? WHERE id=?',
                    (state, permission, agreement, outcome, notes, time.time(), plan_id))
        con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                    ('client_plan', json.dumps({'lead_id': row['lead_id'], 'plan_id': plan_id, 'state': state, 'operator_recorded': True}), time.time()))


def export(db, plan_id):
    row = db.one('SELECT * FROM client_plans WHERE id=?', (plan_id,))
    if not row or row['kind'] != 'case_study':
        raise ValueError('Case-study plan not found')
    snapshot = json.loads(row['client_snapshot'])
    esc = html.escape
    fields = [('Client', snapshot['company']), ('Confirmed problem', snapshot['confirmed_problem']),
              ('Measurement baseline', snapshot.get('baseline_notes', '') or 'Not recorded in this historical client snapshot'),
              ('Agreed metric', snapshot['success_metric']), ('Scope', row['scope']),
              ('Recorded delivery outcome', snapshot['outcome_notes']), ('Later outcome notes', row['outcome_notes'])]
    status = 'DRAFT - internal review only' if row['state'] == 'planned' else 'DECLINED - do not publish' if row['state'] == 'declined' else 'Permission reference recorded - inspect before sharing'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Client case study</title><style>body{font:17px system-ui;max-width:760px;margin:40px auto;padding:20px;line-height:1.6}p{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>' + esc(row['title']) + '</h1><p>' + esc(status) + '</p>' + ''.join('<h2>'+esc(k)+'</h2><p>'+esc(str(v))+'</p>' for k, v in fields) + '<p>Client outcome notes are operator-recorded. No independent measurement or causal uplift is established. This export does not publish anything.</p></html>'


def report(db):
    with db.connect() as con:
        con.execute('BEGIN')
        rows = [dict(r) for r in con.execute('SELECT p.id,p.lead_id,l.company,p.kind,p.title,p.state,p.due_at FROM client_plans p JOIN leads l ON l.id=p.lead_id ORDER BY p.due_at,p.id')]
        calls = con.execute("SELECT count(*) FROM sales WHERE json_extract(details,'$.call_at')>0 AND stage NOT IN ('new','contacted')").fetchone()[0]
    open_rows = [r for r in rows if r['state'] not in {'completed', 'declined'}]
    return {'open_plans': len(open_rows), 'overdue_plans': sum(r['due_at'] < time.time() for r in open_rows),
            'recorded_agreed_calls': calls, 'due_plans': open_rows[:30],
            'completed_by_kind': {k: sum(r['kind'] == k and r['state'] == 'completed' for r in rows) for k in sorted(KINDS)},
            'note': 'Operator-managed plans and agreed-call records; dates are not proof a call occurred. No automatic maintenance work, upsell messages or case-study publication.'}
