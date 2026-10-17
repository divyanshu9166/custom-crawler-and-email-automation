"""Operator-recorded costs and cash receipts. Currency totals never use an implicit FX rate."""
import json
import time
from decimal import Decimal, InvalidOperation

KINDS = {'acquisition_cost', 'delivery_cost', 'maintenance_cost', 'payment', 'refund'}


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Provide a positive amount with at most two decimal places') from exc
    if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999.99') or amount != amount.quantize(Decimal('.01')):
        raise ValueError('Provide a positive amount with at most two decimal places')
    return int(amount * 100)


def record(db, lead_id, value):
    amount = money(value['amount'])
    kind, currency = value['kind'], value['currency']
    reference, note = value['reference'].strip(), value['note'].strip()
    happened = value.get('happened_at') if value.get('happened_at') is not None else time.time()
    if kind not in KINDS or currency not in {'USD', 'GBP'}:
        raise ValueError('Unsupported financial kind or currency')
    if len(reference) < 12 or len(note) < 12 or not 0 < happened <= time.time() + 1:
        raise ValueError('Record the actual reference, context and a past transaction date')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if not con.execute('SELECT id FROM leads WHERE id=?', (lead_id,)).fetchone():
            raise ValueError('Company not found')
        existing = con.execute('SELECT * FROM financial_entries WHERE lead_id=? AND reference=?', (lead_id, reference)).fetchone()
        if existing:
            if (existing['kind'], existing['currency'], existing['amount_minor'], existing['note']) != (kind, currency, amount, note) or existing['voided_at']:
                raise ValueError('Reference already recorded; void mistakes and use a new correction reference')
            if value.get('happened_at') is not None and existing['happened_at'] != happened:
                raise ValueError('Reference already recorded with a different date')
            return existing['id']
        eid = con.execute('INSERT INTO financial_entries(lead_id,kind,currency,amount_minor,reference,note,happened_at,created_at) VALUES(?,?,?,?,?,?,?,?)',
                          (lead_id, kind, currency, amount, reference, note, happened, time.time())).lastrowid
        con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                    ('financial_record', json.dumps({'lead_id': lead_id, 'entry_id': eid, 'operator_recorded': True}), time.time()))
        return eid


def void(db, entry_id, reason):
    reason = reason.strip()
    if len(reason) < 12:
        raise ValueError('Explain the correction; transaction history is retained')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM financial_entries WHERE id=?', (entry_id,)).fetchone()
        if not row or row['voided_at']:
            raise ValueError('Entry not found or already voided')
        con.execute('UPDATE financial_entries SET voided_at=?,void_reason=? WHERE id=?', (time.time(), reason, entry_id))
        con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                    ('financial_void', json.dumps({'lead_id': row['lead_id'], 'entry_id': entry_id, 'reason': reason}), time.time()))


def entries(db, lead_id):
    return [{**r, 'amount': f"{Decimal(r['amount_minor']) / 100:.2f}"} for r in db.all(
        'SELECT * FROM financial_entries WHERE lead_id=? ORDER BY happened_at DESC,id DESC', (lead_id,))]


def report(db, lead_id=None):
    with db.connect() as con:
        con.execute('BEGIN')
        rows = [dict(r) for r in con.execute('SELECT lead_id,kind,currency,amount_minor FROM financial_entries WHERE voided_at IS NULL' +
                (' AND lead_id=?' if lead_id else ''), (lead_id,) if lead_id else ())]
        won = {r[0] for r in con.execute("SELECT lead_id FROM sales WHERE stage IN ('won','delivery','completed')")}
        for r in con.execute("SELECT detail FROM events WHERE kind='sales_stage'"):
            detail = json.loads(r[0])
            if detail.get('stage') in {'won', 'delivery', 'completed'}:
                won.add(detail.get('lead_id'))
    currencies = []
    for currency in sorted({r['currency'] for r in rows}):
        relevant = [r for r in rows if r['currency'] == currency]
        totals = {kind: sum(r['amount_minor'] for r in relevant if r['kind'] == kind) for kind in KINDS}
        cost = sum(totals[k] for k in ('acquisition_cost', 'delivery_cost', 'maintenance_cost'))
        received = totals['payment'] - totals['refund']
        contribution = received - cost
        acquisition_leads = {r['lead_id'] for r in relevant if r['kind'] == 'acquisition_cost'}
        acquired_won = len(acquisition_leads & won)
        currencies.append({'currency': currency, **{k: f'{Decimal(v)/100:.2f}' for k, v in totals.items()},
            'total_cost': f'{Decimal(cost)/100:.2f}', 'net_receipts': f'{Decimal(received)/100:.2f}',
            'recorded_contribution': f'{Decimal(contribution)/100:.2f}',
            'recorded_return_on_cost': float(Decimal(contribution)/cost) if cost else None,
            'acquisition_records_with_cost': len(acquisition_leads), 'recorded_won_with_acquisition_cost': acquired_won,
            'cost_per_recorded_win': f'{Decimal(totals["acquisition_cost"])/100/acquired_won:.2f}' if acquired_won else None})
    return {'currencies': currencies, 'note': 'Operator-recorded cash and costs, not audited revenue, profit or causal ROI. USD and GBP stay separate. Missing costs are not estimated.',
            'definitions': {'recorded_return_on_cost': '(payments - refunds - all recorded costs) / all recorded costs; unknown with no recorded costs.',
                'cost_per_recorded_win': 'All recorded acquisition costs in this currency / recorded won business records with acquisition costs in this currency. Other channels and incomplete costs affect this descriptive figure.'}}
