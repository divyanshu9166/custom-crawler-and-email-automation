import asyncio
from outreach import worker

async def test_draft_starts_while_other_lead_research_is_running(db, settings, monkeypatch):
    settings.worker_enabled = True
    settings.crawl_concurrency = 1
    research = db.enqueue('research', {'lead_id': 1})
    draft = db.enqueue('prepare', {'lead_id': 2})
    started = {kind: asyncio.Event() for kind in ('research', 'prepare')}
    stop = asyncio.Event()
    async def execute(db, settings, job):
        started[job['kind']].set()
        await stop.wait()
        db.execute("UPDATE jobs SET state='done' WHERE id=?", (job['id'],))
    async def idle(*args):
        await stop.wait()
    monkeypatch.setattr(worker, 'execute_job', execute)
    monkeypatch.setattr(worker, 'mail_loop', idle)
    task = asyncio.create_task(worker.run(db, settings, stop))
    try:
        await asyncio.wait_for(asyncio.gather(*(e.wait() for e in started.values())), 5)
        assert all(db.one('SELECT state FROM jobs WHERE id=?', (j,))['state']=='running' for j in (research,draft))
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)
    assert not db.one('SELECT id FROM messages')

def test_draft_lane_preserves_same_prospect_exclusion_and_serial_claims(db):
    db.enqueue('research', {'lead_id': 1})
    db.claim({'research'})
    db.enqueue('prepare', {'lead_id': 1})
    other = db.enqueue('prepare', {'lead_id': 2})
    assert db.claim({'prepare'})['id']==other
    assert db.claim({'prepare'}) is None


async def test_parser_bug_is_not_requeued_as_another_crawl_pass(db, settings, monkeypatch):
    settings.auto_prepare_enabled = False
    async def broken(*args, **kwargs):
        raise AttributeError('controlled malformed parser state')
    def unexpected(*args):
        raise AssertionError('Deterministic bugs must not consume continuation passes')
    monkeypatch.setattr(worker, 'research_lead', broken)
    monkeypatch.setattr(worker, 'reschedule', unexpected)
    db.enqueue('research', {'lead_id': 1})
    job = db.claim({'research'})
    await worker.execute_job(db, settings, job)
    result = db.one('SELECT state,error FROM jobs WHERE id=?', (job['id'],))
    assert result == {'state':'failed','error':'AttributeError'}
