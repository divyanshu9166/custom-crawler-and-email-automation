"""Shared outreach ledger and operator-confirmed sales workflow. No external messages or payments."""
import json
import math
import time
from decimal import Decimal

from .web import crawl_url


STAGES = {"new", "contacted", "interested", "qualified", "call_booked", "proposal", "won", "delivery", "completed", "nurture", "lost"}
QUALIFICATION = ("confirmed_problem", "primary_goal", "success_metric", "decision_maker", "timeline", "budget_notes")


def company(con, lead_id):
    lead = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        raise ValueError("Company not found")
    return dict(lead)


def ensure_sales(con, lead_id):
    company(con, lead_id)
    con.execute("INSERT OR IGNORE INTO sales(lead_id,updated_at) VALUES(?,?)", (lead_id, time.time()))
    return dict(con.execute("SELECT * FROM sales WHERE lead_id=?", (lead_id,)).fetchone())


def stop_company(con, lead_id, status="hold"):
    con.execute("UPDATE contacts SET status=? WHERE lead_id=? AND status IN ('active','hold')", (status, lead_id))
    con.execute("UPDATE messages SET state='cancelled' WHERE contact_id IN (SELECT id FROM contacts WHERE lead_id=?) AND state='queued'", (lead_id,))
    con.execute("UPDATE sales SET cold_email_hold=1,version=version+1,updated_at=? WHERE lead_id=?", (time.time(), lead_id))


def assert_outreach_open(con, lead_id):
    scope = con.execute('SELECT l.deleted_at,g.state FROM leads l LEFT JOIN campaign_groups g ON g.id=l.campaign_id WHERE l.id=?', (lead_id,)).fetchone()
    if scope and scope['deleted_at']:
        raise ValueError('Prospect is deleted; restore and review before outreach')
    row = con.execute("SELECT cold_email_hold FROM sales WHERE lead_id=?", (lead_id,)).fetchone()
    if row and row[0]:
        raise ValueError("Company has a shared outreach/sales hold; review its activity before cold email")


def record_activity(db, lead_id, value):
    channel, kind = value["channel"], value["kind"]
    if channel not in {"email", "linkedin", "x", "phone", "meeting", "other"} or kind not in {"note", "outreach", "reply", "opt_out"}:
        raise ValueError("Unsupported activity channel or kind")
    note = value["note"].strip()
    if len(note) < 12:
        raise ValueError("Describe the real activity and its source")
    source = crawl_url(value["source_url"]) if value.get("source_url") else ""
    happened = value.get("happened_at") or time.time()
    if not math.isfinite(happened) or happened <= 0 or happened > time.time() + 300:
        raise ValueError("Activity date must describe an actual past/current event")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        record = ensure_sales(con, lead_id)
        cid = value.get("contact_id")
        if cid and not con.execute("SELECT id FROM contacts WHERE id=? AND lead_id=?", (cid, lead_id)).fetchone():
            raise ValueError("Contact belongs to a different company or does not exist")
        activity_id = con.execute("INSERT INTO activities(lead_id,contact_id,channel,kind,note,source_url,happened_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                  (lead_id, cid, channel, kind, note, source, happened, time.time())).lastrowid
        if kind != "note":
            stop_company(con, lead_id, "replied" if kind == "reply" else "hold")
            if kind == "reply":
                con.execute("INSERT INTO tasks(lead_id,kind,title,due_at,created_at) VALUES(?,?,?,?,?)",
                            (lead_id, "review", "Review response and fulfill any promised asset", time.time() + 86400, time.time()))
            if kind == "opt_out":
                emails = con.execute("SELECT email FROM contacts WHERE lead_id=?" + (" AND id=?" if cid else ""), (lead_id, cid) if cid else (lead_id,)).fetchall()
                for email in emails:
                    db.suppress(email[0], "Operator-recorded opt-out: " + channel, con)
            elif kind == "reply" and cid:
                con.execute("UPDATE contacts SET status='replied' WHERE id=? AND status<>'suppressed'", (cid,))
            if record["stage"] in {"new", "contacted"} and kind in {"outreach", "reply"}:
                con.execute("UPDATE sales SET stage='contacted' WHERE lead_id=?", (lead_id,))
    db.event("manual_activity", {"lead_id": lead_id, "activity_id": activity_id, "channel": channel, "kind": kind})
    return activity_id


def release_outreach_hold(db, lead_id, note):
    if len(note.strip()) < 20:
        raise ValueError("Explain why another cold-email approach is appropriate")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = ensure_sales(con, lead_id)
        if not row["cold_email_hold"]:
            raise ValueError("Company has no shared outreach hold")
        if con.execute("SELECT id FROM activities WHERE lead_id=? AND kind IN ('reply','opt_out')", (lead_id,)).fetchone() or row["stage"] not in {"new", "contacted"}:
            raise ValueError("Replies, opt-outs and sales conversations remain stopped; continue the human conversation")
        if con.execute("SELECT id FROM contacts WHERE lead_id=? AND status IN ('replied','suppressed')", (lead_id,)).fetchone():
            raise ValueError("Company already has a replied or suppressed contact")
        con.execute("UPDATE sales SET cold_email_hold=0,version=version+1,updated_at=? WHERE lead_id=?", (time.time(), lead_id))
    db.event("shared_hold_released", {"lead_id": lead_id, "reason": note})


def update_sales(db, lead_id, value):
    details = dict(value)
    stage, version = details.pop("stage"), details.pop("version")
    for key in ("call_at", "next_action_at"):
        if details.get(key) is not None and (not math.isfinite(details[key]) or details[key] <= 0):
            raise ValueError("Call and next-action dates must be valid positive timestamps")
    if stage not in STAGES:
        raise ValueError("Unsupported sales stage")
    if stage in {"qualified", "call_booked", "proposal", "won", "delivery", "completed"}:
        if any(len(str(details.get(key, "")).strip()) < 8 for key in QUALIFICATION):
            raise ValueError("Record confirmed problem, goal, success metric, buyer, timeline and budget context")
    if stage == "call_booked" and (not details.get("call_at") or not details.get("next_action_at")):
        raise ValueError("Record the agreed call time and dated next-action")
    if stage in {'call_booked', 'proposal', 'won', 'delivery', 'completed'} and len(details.get('baseline_notes', '').strip()) < 12:
        raise ValueError('Record the baseline or explicitly record an unknown baseline and measurement plan')
    if stage == "nurture" and (not details.get("next_action_at") or details["next_action_at"] <= time.time()):
        raise ValueError("Nurture requires a future next-action date")
    if stage == "lost" and len(details.get("outcome_notes", "").strip()) < 12:
        raise ValueError("Record why the opportunity was closed")
    if stage in {"won", "delivery", "completed"} and any(len(details.get(key, "").strip()) < 8 for key in ("agreement_reference", "payment_reference")):
        raise ValueError("Record the actual agreement and initial-payment references")
    if stage == "completed" and any(len(details.get(key, "").strip()) < 12 for key in ("acceptance_reference", "outcome_notes")):
        raise ValueError("Completion requires client acceptance and measured outcome notes, including inconclusive results")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        current = ensure_sales(con, lead_id)
        if current["version"] != version:
            raise ValueError("Sales record changed; reload before saving")
        if stage == 'completed' and con.execute("SELECT id FROM tasks WHERE lead_id=? AND kind='delivery' AND state='open'", (lead_id,)).fetchone():
            raise ValueError('Close remaining delivery tasks with their actual outcomes before recording completion')
        if stage in {"proposal", "won", "delivery", "completed"}:
            proposal = con.execute("SELECT * FROM proposals WHERE id=? AND lead_id=?", (details.get("proposal_id"), lead_id)).fetchone()
            if not proposal or proposal["state"] != "sent":
                raise ValueError("Record delivery of a reviewed proposal before this stage")
        if stage in {"interested", "qualified", "call_booked", "proposal", "won", "delivery", "completed"}:
            actual_reply = con.execute("SELECT id FROM activities WHERE lead_id=? AND kind='reply'", (lead_id,)).fetchone()
            inbox_reply = con.execute("SELECT e.id FROM events e JOIN contacts c ON c.id=e.contact_id WHERE c.lead_id=? AND e.kind='reply'", (lead_id,)).fetchone()
            if not actual_reply and not inbox_reply:
                raise ValueError("Record an actual reply/conversation before advancing the opportunity")
        con.execute("UPDATE sales SET stage=?,details=?,version=version+1,updated_at=? WHERE lead_id=?",
                    (stage, json.dumps(details), time.time(), lead_id))
        if stage not in {"new", "contacted"}:
            stop_company(con, lead_id, "replied" if stage not in {"nurture", "lost"} else "hold")
    db.event("sales_stage", {"lead_id": lead_id, "stage": stage, "operator_recorded": True})


def create_task(db, lead_id, value):
    if value["kind"] not in {"audit", "concept", "demo", "call", "proposal", "followup", "delivery", "review"}:
        raise ValueError("Unsupported task kind")
    if not math.isfinite(value["due_at"]) or value["due_at"] <= 0 or len(value["title"].strip()) < 8:
        raise ValueError("Provide a task title and valid due date")
    with db.connect() as con:
        company(con, lead_id)
        return con.execute("INSERT INTO tasks(lead_id,kind,title,due_at,created_at) VALUES(?,?,?,?,?)",
                            (lead_id, value["kind"], value["title"].strip(), value["due_at"], time.time())).lastrowid


def finish_task(db, task_id, state, outcome):
    if state not in {"done", "cancelled"} or len(outcome.strip()) < 12:
        raise ValueError("Record completion/cancellation and what actually happened")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row or row["state"] != "open":
            raise ValueError("Task does not exist or was already closed")
        con.execute("UPDATE tasks SET state=?,outcome=? WHERE id=? AND state='open'", (state, outcome, task_id))
    db.event("task_closed", {"lead_id": row["lead_id"], "task_id": task_id, "state": state, "outcome": outcome})


def create_proposal(db, lead_id, value):
    required = ("title", "scope", "deliverables", "timeline", "exclusions", "acceptance_criteria", "payment_terms", "ownership_revision_terms")
    if any(len(value.get(key, "").strip()) < 12 for key in required):
        raise ValueError("Complete all proposal scope and commercial sections")
    fee = Decimal(str(value["fee"]))
    if not fee.is_finite() or fee <= 0 or fee.as_tuple().exponent < -2 or value["currency"] not in {"USD", "GBP"}:
        raise ValueError("Provide a positive fee with at most two decimals in USD or GBP")
    value = {**value, "fee": str(fee)}
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        lead = company(con, lead_id)
        record = ensure_sales(con, lead_id)
        details = json.loads(record["details"])
        if record["stage"] not in {"qualified", "call_booked", "proposal", "won", "delivery", "completed"} or any(len(details.get(key, "").strip()) < 8 for key in QUALIFICATION):
            raise ValueError("Qualify the confirmed client need before preparing a proposal")
        if len(details.get('baseline_notes', '').strip()) < 12:
            raise ValueError('Record the baseline or an unknown baseline and measurement plan before proposal preparation')
        value['client_context'] = {key: details[key] for key in (*QUALIFICATION, 'baseline_notes')}
        parts = [f"# {value['title']}", f"Prepared for: {lead['company']}", "Status: DRAFT — review before sharing", f"## Confirmed problem\n\n{details['confirmed_problem']}"]
        parts.append(f"## Measurement baseline\n\n{details['baseline_notes']}\n\nAgreed success metric: {details['success_metric']}")
        for key in required[1:]:
            parts.append(f"## {key.replace('_', ' ').title()}\n\n{value[key]}")
        parts.append(f"## Fee\n\n{value['currency']} {fee}")
        body = "\n\n".join(parts) + "\n"
        pid = con.execute("INSERT INTO proposals(lead_id,details,body,created_at) VALUES(?,?,?,?)", (lead_id, json.dumps(value), body, time.time())).lastrowid
    db.event("proposal_drafted", {"lead_id": lead_id, "proposal_id": pid})
    return pid


def proposal_context_current(record, proposal):
    """An unsent reviewed proposal must still describe the confirmed client need."""
    if not record or record['stage'] not in {'qualified', 'call_booked', 'proposal', 'won', 'delivery', 'completed'}:
        return False
    details = json.loads(record['details'])
    expected = json.loads(proposal['details']).get('client_context')
    return bool(expected) and expected == {key: details.get(key, '') for key in (*QUALIFICATION, 'baseline_notes')}


def proposal_action(db, proposal_id, action, reference=""):
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        proposal = con.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if not proposal:
            raise ValueError("Proposal not found")
        if action == "approve" and proposal["state"] == "draft":
            record = ensure_sales(con, proposal['lead_id'])
            if not proposal_context_current(record, proposal):
                raise ValueError('Client qualification context changed or is historical; create and review a current proposal draft')
            con.execute("UPDATE proposals SET state='approved',body=replace(body,?,?) WHERE id=?",
                        ("Status: DRAFT — review before sharing", "Status: Reviewed proposal", proposal_id))
        elif action == "sent" and proposal["state"] == "approved" and len(reference.strip()) >= 12:
            con.execute("UPDATE proposals SET state='sent',delivery_reference=? WHERE id=?", (reference, proposal_id))
        else:
            raise ValueError("Review the proposal before recording actual delivery; provide a delivery reference")
    db.event("proposal_" + action, {"lead_id": proposal["lead_id"], "proposal_id": proposal_id, "reference": reference})


def report(db):
    from .learning import report as learning_report
    from .finance import report as financial_report
    from .aftercare import report as aftercare_report
    stages = db.all("SELECT l.campaign,COALESCE(s.stage,'new') stage,COUNT(*) n FROM leads l LEFT JOIN sales s ON s.lead_id=l.id GROUP BY l.campaign,COALESCE(s.stage,'new')")
    amounts = {}
    for row in db.all("SELECT p.details FROM sales s JOIN proposals p ON p.id=json_extract(s.details,'$.proposal_id') WHERE s.stage IN ('won','delivery','completed')"):
        proposal = json.loads(row["details"])
        currency = proposal["currency"]
        amounts[currency] = amounts.get(currency, Decimal("0")) + Decimal(proposal["fee"])
    return {"stages": stages, "recorded_contract_value": {k: str(v) for k, v in amounts.items()},
            "learning": learning_report(db),
            "finance": financial_report(db), "aftercare": aftercare_report(db),
            "open_tasks": db.one("SELECT COUNT(*) n FROM tasks WHERE state='open'")["n"],
            "overdue_tasks": db.one("SELECT COUNT(*) n FROM tasks WHERE state='open' AND due_at<?", (time.time(),))["n"],
            "note": "Operator-recorded contract values are not verified revenue or payment receipts."}
