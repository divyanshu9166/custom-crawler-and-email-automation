"""Source-backed value artifacts for review; no invented completed work or external delivery."""
import html
import json
import time
import base64
import re
import hashlib


def current_source(reader, lead_id, evidence_id):
    page = reader("""SELECT e.* FROM evidence e WHERE e.lead_id=? AND e.id=?
        AND e.fetched_at>=COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
        AND e.fetched_at BETWEEN ? AND ?""", (lead_id, evidence_id, time.time()-30*86400, time.time()+60))
    if not page:
        raise ValueError('Source must be current and fresh; refresh research before preparing or approving this artifact')
    return dict(page)


def check_sources(reader, lead_id, proof):
    lead = reader('SELECT * FROM leads WHERE id=?', (lead_id,))
    if not lead or lead['status'] == 'researching':
        raise ValueError('Source research is running; wait before preparing or approving an artifact')
    if (lead['service'] != proof['service'] or
            hashlib.sha256(lead['findings'].encode()).hexdigest() != proof['findings_sha256']):
        raise ValueError('Source review or selected offer changed; regenerate the artifact')
    for point in [*proof['points'], *proof.get('qualification_sources', [])]:
        page = current_source(reader, lead_id, point['evidence_id'])
        if page['sha256'] != point['sha256'] or point['quote'] not in page['text']:
            raise ValueError('Source changed since artifact preparation; regenerate and review it')
    if 'audit_context' in proof:
        if reader("SELECT 1 FROM jobs WHERE state IN ('pending','running') AND kind IN ('research','contact_research','professional_research','social_research','screenshot','performance') AND json_extract(payload,'$.lead_id')=?", (lead_id,)):
            raise ValueError('Research or audits are running; wait before reviewing the proof preview')
        from .diagnostics import snapshot
        class SourceReader:
            one = staticmethod(reader)
        if snapshot(SourceReader(), dict(lead)) != proof['audit_context']:
            raise ValueError('Audit context changed or expired; regenerate the proof preview')


def assert_current_artifact(db, row, con=None):
    reader = (lambda sql, params: con.execute(sql, params).fetchone()) if con else db.one
    event = reader("SELECT detail FROM events WHERE kind='artifact_source_snapshot' AND json_extract(detail,'$.artifact_id')=? ORDER BY id DESC LIMIT 1", (row['id'],))
    if not event:
        raise ValueError('Source snapshot is missing for this historical artifact; regenerate before approving')
    proof = json.loads(event['detail'])
    check_sources(reader, row['lead_id'], proof)
    if proof.get('content_sha256'):
        body_row = reader('SELECT body FROM deliverables WHERE id=?', (row['id'],))
        if not body_row:
            raise ValueError('Proof preview is unavailable; regenerate before using it')
        stable_body = body_row['body'].replace('Status: Reviewed discussion artifact', 'Status: DRAFT — review before sharing')
        if hashlib.sha256(stable_body.encode()).hexdigest() != proof['content_sha256']:
            raise ValueError('Proof preview content changed; regenerate before using it')


def esc(value):
    return html.escape(str(value), quote=True)


def source_point(db, lead_id, value):
    page = current_source(db.one, lead_id, value['evidence_id'])
    quote = value["quote"].strip()
    if not page or len(quote) < 8 or quote not in page["text"]:
        raise ValueError("Each artifact point requires an exact quote from this company's saved page")
    return page, quote


def create(db, lead_id, value, *, automatic_context=None):
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise ValueError("Company not found")
    if lead['status'] == 'researching':
        raise ValueError('Source research is running; wait before preparing an artifact')
    kind = value["kind"]
    if kind not in {"audit", "concept", "faq_demo", "whatsapp_flow", "call_flow"}:
        raise ValueError("Unsupported value artifact")
    findings = json.loads(lead["findings"])
    points = value.get("points") or [f for f in findings if f.get("review_required") is False]
    if not points:
        raise ValueError("Review source-backed findings or supply reviewed artifact points first")
    if len(points) > 3:
        raise ValueError("Use at most three focused audit points")
    ids, sections, source_proofs = set(), [], []
    for point in points:
        page, quote = source_point(db, lead_id, point)
        if len(point.get("observation", "").strip()) < 12 or len(point.get("suggestion", "").strip()) < 12:
            raise ValueError("Provide a specific observation and proposed improvement")
        ids.add(page["id"])
        source_proofs.append({'evidence_id': page['id'], 'sha256': page['sha256'], 'quote': quote})
        sections.append(f'<section><h2>{len(sections)+1}. {esc(point["observation"])}</h2><blockquote>{esc(quote)}</blockquote><p><strong>Proposed next step:</strong> {esc(point["suggestion"])}</p><p class="small">Source: <a href="{esc(page["url"])}">{esc(page["url"])}</a> · Captured {esc(time.strftime("%Y-%m-%d", time.gmtime(page["fetched_at"])))}</p></section>')
    content = "".join(sections)
    if automatic_context is not None:
        content += '<section><h2>Evidence and test plan</h2><p>' + esc(automatic_context['basis']['note']) + '</p>'
        from .conclusions import build
        conclusion = build(automatic_context['audit_context'], lead['service'])
        content += '<h3>Research conclusion</h3><p>' + esc(conclusion['summary']) + '</p>'
        for finding in conclusion['findings'][:1]:
            content += '<p><strong>Proposed fix:</strong> ' + esc(finding['proposed_fix']) + '</p><p><strong>Reproduce:</strong> ' + esc(finding['reproduce']) + '</p><p><strong>Verify:</strong> ' + esc(finding['verification']) + '</p><p>' + esc(finding['limitations']) + '</p>'
            for metric in finding['supporting_measurements']:
                content += '<p>' + esc(metric['metric']) + ': ' + esc(metric['numericValue']) + ' ' + esc(metric['numericUnit']) + '</p>'
        for item in automatic_context['audit_context'].get('observations', []):
            if lead['service'] == 'ai_calling_agent':
                continue
            content += '<p>' + esc(item['fact']) + '</p><p class="small">Test/capture source: ' + esc(item['url']) + ' · ' + esc(time.strftime('%Y-%m-%d', time.gmtime(item['captured_at']))) + '</p>'
        content += '<p>Agree the baseline, test task and success metric with the business before implementation. No form was submitted and no client outcome has been measured.</p></section>'
    disclaimer = "Source-backed observations and proposed tests. No private analytics or guaranteed conversion uplift is assumed."
    if value.get("screenshot_name"):
        filename = value["screenshot_name"]
        if not re.fullmatch(rf"lead-{lead_id}-\d+(?:-[a-f0-9]{{6}}-(?:mobile|desktop))?\.png", filename):
            raise ValueError("Select an existing screenshot belonging to this company")
        path = db.path.parent / "screenshots" / filename
        if not path.is_file() or path.stat().st_size > 10_000_000:
            raise ValueError("Screenshot unavailable or exceeds artifact image budget")
        raw = path.read_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Screenshot is not a valid PNG")
        markers = []
        for marker in value.get("markers") or []:
            index, left, top = marker["point_index"], marker["left"], marker["top"]
            if not 0 <= index < len(points) or not 0 <= left <= 100 or not 0 <= top <= 100:
                raise ValueError("Callouts must refer to a reviewed point and a valid percentage position")
            markers.append(f'<span style="position:absolute;left:{float(left)}%;top:{float(top)}%;background:#a63636;color:white;border-radius:50%;padding:4px 10px">{index+1}</span>')
        encoded = base64.b64encode(raw).decode()
        content = f'<figure><div style="position:relative"><img alt="Saved company screenshot with reviewed numbered callouts" style="width:100%;display:block" src="data:image/png;base64,{encoded}">{"".join(markers)}</div><figcaption class="small">Saved screenshot: {esc(filename)}. Numbered callouts reference the corresponding observations below; inspect the original render report before claiming a visual defect.</figcaption></figure>' + content
    elif value.get("markers"):
        raise ValueError("Callouts require a selected company screenshot")
    if kind == "concept":
        headline, intro, action = [value.get(key, "").strip() for key in ("headline", "intro", "primary_action")]
        if any(len(text) < 8 for text in (headline, intro, action)):
            raise ValueError("Provide proposed headline, introduction and primary action")
        content = f'<section class="hero"><p>PROPOSED PAGE DIRECTION</p><h2>{esc(headline)}</h2><p>{esc(intro)}</p><span class="action">{esc(action)}</span><p class="small">Illustrative CTA only; no live form or integration.</p></section><h2>Why explore this direction?</h2>' + content
        disclaimer = "A discussion concept, not a finished client website. Copy, design, accessibility and integrations require review."
    elif kind == "faq_demo":
        faqs = value.get("faqs") or []
        if not 1 <= len(faqs) <= 10:
            raise ValueError("Provide one to ten approved source-backed FAQ questions")
        answers = []
        for faq in faqs:
            page, quote = source_point(db, lead_id, faq)
            if len(faq["question"].strip()) < 5:
                raise ValueError("Provide a meaningful FAQ question")
            ids.add(page["id"])
            source_proofs.append({'evidence_id': page['id'], 'sha256': page['sha256'], 'quote': quote})
            answers.append(f'<details><summary>{esc(faq["question"])}</summary><p>{esc(quote)}</p><a href="{esc(page["url"])}">Read approved source</a></details>')
        content = '<section><h2>Try the approved knowledge excerpts</h2>' + "".join(answers) + f'<p>For other questions, reach the team through its <a href="{esc(lead["website"])}">official website</a>.</p></section>' + content
        disclaimer = "Interactive FAQ knowledge prototype. Answers are exact approved excerpts; this is not a live AI assistant, account lookup or helpdesk integration."
    elif kind == 'call_flow':
        from .offers import selected_offer
        from .calling import pitch_plan
        if selected_offer(db, lead) != 'ai_calling_agent':
            raise ValueError('Qualify a current Campaign A calling-agent offer before creating its call flow')
        plan = pitch_plan(findings[0]['quote'])
        steps = [plan['proposed_work'], 'Introduce the automated assistant and confirm the caller wishes to continue.',
                 'Confirm collected details before recording or booking anything; provide a clear human transfer.',
                 *plan['pilot_checks']]
        content = '<section><h2>Proposed '+esc(plan['use_case'].replace('_', ' '))+' call flow</h2><ol class="flow">'+''.join('<li>'+esc(step)+'</li>' for step in steps)+'</ol><p>'+esc(plan['intended_benefit'])+'</p></section>'+content
        disclaimer = 'Discussion outline only, not a deployed calling agent or live calendar/CRM connection. No phone calls, recordings or bookings were made.'
    elif kind == "whatsapp_flow":
        if lead['status'] != 'qualified' or lead["service"] not in {"whatsapp_marketing", "whatsapp_automation"}:
            raise ValueError("Select and qualify a WhatsApp offer before creating its workflow")
        if not findings or len(findings[0].get("channel_fit_notes", "")) < 20:
            raise ValueError("Record channel fit and qualification unknowns first")
        from .offers import selected_offer
        if not selected_offer(db, lead):
            raise ValueError('Review current D2C source evidence and offer context first')
        steps = ["Confirm customer channel fit and appropriate permission", "Choose one eligible customer segment or ecommerce event", "Check current messaging, template and timing requirements", "Send the allowed useful message in the proposed pilot", "Provide human support and honor opt-outs", "Compare incremental outcomes and costs before expanding"]
        context = findings[0].get('offer_context', {})
        ready = context.get('channel_fit_status') == context.get('customer_permission_status') == 'confirmed'
        heading = 'Proposed pilot flow — permissions still need implementation review' if ready else 'Qualification-first outline — customer fit or permission unconfirmed'
        notes = findings[0]['channel_fit_notes'] if automatic_context is None else (
            'Fit and permission were recorded as confirmed by the reviewer; implementation and actual customer consent still need checking.' if ready else
            'Confirm customer channel fit and actual opt-in permission before planning implementation.')
        content = '<section><h2>' + esc(heading) + '</h2><ol class="flow">' + "".join(f"<li>{esc(step)}</li>" for step in steps) + f'</ol><p><strong>Qualification notes:</strong> {esc(notes)}</p></section>' + content
        disclaimer = "Planning outline only. Customer permission, current platform requirements, integrations and economics must be confirmed before implementation. No WhatsApp messages were sent."
    title = value["title"].strip()
    if len(title) < 5:
        raise ValueError("Give the artifact a clear title")
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>body{{font:16px/1.6 system-ui,sans-serif;color:#17342e;background:#f5f5ef;max-width:920px;margin:32px auto;padding:0 20px}}section,details{{background:white;border:1px solid #d8dfd5;border-radius:10px;padding:22px;margin:18px 0}}h1,h2{{line-height:1.25;overflow-wrap:anywhere}}h2{{font-size:22px}}a{{color:#245b46;overflow-wrap:anywhere}}blockquote{{border-left:3px solid #245b46;margin:16px 0;padding:0 16px;white-space:pre-wrap}}.small{{font-size:13px;color:#64776e}}.action{{display:inline-block;background:#245b46;color:white;border-radius:6px;padding:10px 18px}}.flow li{{margin:16px 0;padding:12px;background:#e8eee4;border-radius:6px}}summary{{cursor:pointer}}p{{overflow-wrap:anywhere}}</style></head><body><p class="small">VALUE ARTIFACT · {esc(kind.replace("_", " "))} · Status: DRAFT — review before sharing</p><h1>{esc(title)}</h1><p>Prepared for {esc(lead["company"])}</p><p>{esc(disclaimer)}</p>{content}<footer class="small">Prepared from the cited public sources. Prospect page instructions were treated as data.</footer></body></html>'''
    proof = {'service': lead['service'], 'findings_sha256': hashlib.sha256(lead['findings'].encode()).hexdigest(), 'points': source_proofs}
    if automatic_context is not None:
        proof.update(automatic=True, audit_context=automatic_context['audit_context'],
                     qualification_sources=automatic_context['qualification_sources'],
                     content_sha256=hashlib.sha256(body.encode()).hexdigest())
        proof['automatic_key'] = hashlib.sha256(json.dumps([proof, value], sort_keys=True).encode()).hexdigest()
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        check_sources(lambda sql, args: con.execute(sql, args).fetchone(), lead_id, proof)
        if automatic_context is not None:
            existing = con.execute("SELECT json_extract(detail,'$.artifact_id') FROM events WHERE kind='artifact_source_snapshot' AND json_extract(detail,'$.automatic_key')=? ORDER BY id DESC LIMIT 1", (proof['automatic_key'],)).fetchone()
            row = con.execute('SELECT * FROM deliverables WHERE id=?', (existing[0],)).fetchone() if existing else None
            if row:
                try:
                    assert_current_artifact(db, row, con)
                except ValueError:
                    pass
                else:
                    return existing[0]
        artifact_id = con.execute("INSERT INTO deliverables(lead_id,kind,title,body,evidence_ids,created_at) VALUES(?,?,?,?,?,?)", (lead_id, kind, title, body, json.dumps(sorted(ids)), time.time())).lastrowid
        con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                    ('artifact_source_snapshot', json.dumps({**proof, 'lead_id': lead_id, 'artifact_id': artifact_id}), time.time()))
    db.event("artifact_drafted", {"lead_id": lead_id, "artifact_id": artifact_id, "kind": kind})
    return artifact_id


def prepare_automatic(db, lead_id):
    """Prepare one idempotent, unsent discussion preview without touching email copy."""
    from .offers import selected_offer, evidence_basis, ARTIFACTS
    from .research import fresh_evidence
    from .web import crawl_url
    from .diagnostics import snapshot
    from .preparation import source_busy
    lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
    if not lead or source_busy(db, lead_id) or not selected_offer(db, lead):
        raise ValueError('Wait for a current source-backed offer before preparing proof of value')
    finding = json.loads(lead['findings'])[0]
    audit = snapshot(db, lead)
    pages = fresh_evidence(db, lead_id)
    basis = evidence_basis(lead, finding, pages, audit)
    if not basis['draft_allowed']:
        raise ValueError('Insufficient evidence for a useful proof preview')
    service = lead['service']
    plans = {
        'ai_calling_agent': 'Scope one source-backed inbound or requested-callback task, approved qualification/booking/support steps, and a human handoff before a synthetic-call pilot.',
        'website_build': 'Explore one proposed service page with a clear service description and inquiry route; confirm scope with the business first.',
        'website_improvement': 'Test one existing service-to-inquiry journey on mobile with representative buyers; observe clarity and task completion before suggesting changes.',
        'chatbot': 'Review the published answer excerpts with the business, then test a narrow FAQ prototype and a proposed human-support route.',
        'store_launch': 'Outline a small product-to-purchase launch journey; confirm product, delivery, returns and support requirements before building.',
        'store_improvement': 'Test one product-to-purchase journey and record task completion and unanswered questions before recommending changes.',
        'whatsapp_marketing': 'Confirm customer channel fit and permission first; only then scope one eligible customer segment, opt-out handling and a measurable pilot.',
        'whatsapp_automation': 'Confirm customer channel fit and permission first; only then map one eligible order/support event and a human-support route.',
    }
    kind = ARTIFACTS[service][0]
    if service == 'ai_calling_agent':
        from .calling import pitch_plan
        plans[service] = pitch_plan(finding['quote'])['proposed_work']
    # Summaries may contain unsupported historical model claims. Only the exact
    # cited business quote becomes an observation; the test plan is a proposal.
    value = {'kind': kind, 'title': lead['company']+' — proposed '+kind.replace('_', ' '),
             'points': [{'evidence_id': finding['evidence_id'], 'quote': finding['quote'],
                         'observation': 'Published business context for a proposed assessment', 'suggestion': plans[service]}]}
    if kind == 'concept':
        value.update(headline='Proposed '+('service-page' if finding.get('offer_context', {}).get('website_scope') == 'new_service_page' else 'launch')+' direction',
                     intro='A discussion concept based on the cited business information; scope and copy need confirmation.',
                     primary_action='Discuss the proposed next step')
    if kind == 'faq_demo':
        value['faqs'] = [{'evidence_id': finding['evidence_id'], 'quote': finding['quote'], 'question': 'What information has the business published?'}]
    country = next(p for p in pages if crawl_url(p['url']) == crawl_url(lead['country_source']))
    qualification = [{'evidence_id': country['id'], 'sha256': country['sha256'], 'quote': finding['country_quote']}]
    context = finding.get('offer_context', {})
    if context.get('commerce_evidence_id'):
        page = next(p for p in pages if p['id'] == context['commerce_evidence_id'])
        qualification.append({'evidence_id': page['id'], 'sha256': page['sha256'], 'quote': context['commerce_quote']})
    return create(db, lead_id, value, automatic_context={'basis': basis, 'audit_context': audit, 'qualification_sources': qualification})


def writer_context(db, lead_id):
    """Bounded artifact metadata; availability does not mean review or delivery."""
    rows = db.all("SELECT d.*,e.detail FROM deliverables d JOIN events e ON e.kind='artifact_source_snapshot' AND json_extract(e.detail,'$.artifact_id')=d.id WHERE d.lead_id=? AND json_extract(e.detail,'$.automatic')=1 ORDER BY d.id DESC", (lead_id,))
    for row in rows:
        try:
            assert_current_artifact(db, row)
        except ValueError:
            continue
        stable_body = row['body'].replace('Status: Reviewed discussion artifact', 'Status: DRAFT — review before sharing')
        return {'id': row['id'], 'kind': row['kind'], 'title': row['title'],
                'body_sha256': hashlib.sha256(stable_body.encode()).hexdigest(),
                'availability': 'Local discussion preview only; not shared with prospect. Review before offering delivery.'}
    return {}


def action(db, artifact_id, operation, reference=""):
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM deliverables WHERE id=?", (artifact_id,)).fetchone()
        if not row:
            raise ValueError("Artifact not found")
        if operation == "approve" and row["state"] == "draft":
            assert_current_artifact(db, row, con)
            con.execute("UPDATE deliverables SET state='approved',body=replace(body,?,?) WHERE id=?", ("Status: DRAFT — review before sharing", "Status: Reviewed discussion artifact", artifact_id))
        elif operation == "sent" and row["state"] == "approved" and len(reference.strip()) >= 12:
            con.execute("UPDATE deliverables SET state='sent',delivery_reference=? WHERE id=?", (reference, artifact_id))
        else:
            raise ValueError("Review the artifact before recording actual delivery, with a source reference")
    db.event("artifact_" + operation, {"lead_id": row["lead_id"], "artifact_id": artifact_id, "reference": reference})
