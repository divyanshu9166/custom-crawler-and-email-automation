import asyncio
import json
import logging
import time
import httpx

from .research import research_lead, discover_leads, verify_contact
from .mail import poll_inbox, send_one
from .browser import screenshot
from .performance import performance_audit
from .web import retry_after_seconds
from .crawl_scheduler import reschedule, resumable_restart, stop_reviewed_cycle, schedule_final_audits

log = logging.getLogger(__name__)


async def execute_job(db, settings, job):
    payload = json.loads(job["payload"])
    try:
        if job["kind"] == "research":
            payload = resumable_restart(db, job)
            if payload.get('auto_pass'):
                lead = db.one('SELECT status FROM leads WHERE id=?', (payload['lead_id'],))
                if lead and lead['status'] == 'qualified':
                    stop_reviewed_cycle(db, payload)
                    db.execute("UPDATE jobs SET state='done',error='Stopped after business review' WHERE id=?", (job['id'],))
                    return
            if payload.get('crawl_id'):
                current = db.one('SELECT id FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (payload['lead_id'],))
                if not current or current['id'] != payload['crawl_id']:
                    db.execute("UPDATE jobs SET state='done',error='Superseded crawl checkpoint' WHERE id=?", (job['id'],))
                    return
            # Use a copy: another lane never sees a temporarily changed shared Settings.
            research_settings = settings.model_copy()
            if settings.crawl_auto_continue:
                research_settings.crawl_max_pages = min(settings.crawl_max_pages, settings.crawl_auto_max_pages)
                research_settings.auto_visual_audit = False
                research_settings.auto_contact_research = False
                research_settings.auto_professional_research=False
            if payload.get('continuation'):
                row = db.one('SELECT report FROM crawls WHERE id=?', (payload.get('crawl_id'),))
                if row:
                    remaining = settings.crawl_auto_max_pages-json.loads(row['report']).get('attempted', 0)
                    if remaining <= 0 and payload.get('auto_pass'):
                        db.execute("UPDATE jobs SET state='done',error='Automatic crawl page budget reached' WHERE id=?", (job['id'],))
                        return
                    research_settings.crawl_max_pages = max(1, min(settings.crawl_max_pages, remaining))
            if payload.get('continuation'):
                await research_lead(db, research_settings, payload['lead_id'], continuation=True,
                                    protect_review=bool(payload.get('auto_pass')))
            else:
                if payload.get('seed_urls'):
                    await research_lead(db, research_settings, payload['lead_id'], seed_urls=payload['seed_urls'])
                else:
                    await research_lead(db, research_settings, payload["lead_id"])
        elif job["kind"] == "verify":
            await verify_contact(db, settings, payload["contact_id"])
        elif job["kind"] == "discover":
            await discover_leads(db, settings, **payload)
        elif job["kind"] == "screenshot":
            await screenshot(db, settings, payload["lead_id"])
        elif job["kind"] == "performance":
            await performance_audit(db, settings, payload["lead_id"])
        elif job['kind'] == 'contact_research':
            from .contact_recovery import research_contacts
            await research_contacts(db, settings, payload['lead_id'])
        elif job['kind']=='professional_research':
            from .professionals import research_professionals
            await research_professionals(db,settings,**payload)
        elif job['kind']=='social_research':
            from .social_research import research_known_posts
            await research_known_posts(db, settings, payload['lead_id'])
        else:
            raise ValueError("Unknown job kind")
        current_job = db.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
        if not reschedule(db, settings, current_job):
            db.execute("UPDATE jobs SET state='done',error='' WHERE id=?", (job["id"],))
            if job['kind'] == 'research' and settings.crawl_auto_continue:
                schedule_final_audits(db, settings, json.loads(current_job['payload']))
    except Exception as exc:
        if job['kind'] == 'research' and not isinstance(exc, ValueError) and reschedule(db, settings, db.one('SELECT * FROM jobs WHERE id=?', (job['id'],))):
            return
        # Error type only: provider exception strings can contain API keys and private URLs.
        error = str(exc)[:350] if isinstance(exc, ValueError) else type(exc).__name__
        attempts = job["attempts"] + 1
        retry = attempts < 3 and not isinstance(exc, ValueError)
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403, 404, 410}:
            retry = False
        delay = 60 * 2 ** attempts
        if isinstance(exc, httpx.HTTPStatusError):
            delay = max(delay, retry_after_seconds(exc.response.headers))
        db.execute("UPDATE jobs SET state=?,due_at=?,error=? WHERE id=?",
                   ("pending" if retry else "failed", time.time() + delay, error, job["id"]))
        db.event("job_failed", {"job": job["id"], "kind": job["kind"], "error": error, "will_retry": retry})


class WorkerLock:
    """An OS-held lock prevents two workers against the same SQLite volume."""
    def __init__(self, path):
        self.file = open(path, "a+b")
        self.file.seek(0)
        self.file.write(b"0")
        self.file.flush()
        self.file.seek(0)
        try:
            try:
                import fcntl
            except ImportError:
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("Another worker already owns this data directory")

    def close(self):
        self.file.close()


async def monitor_resources(admission, stop, interval=5):
    """Sample even when every crawl slot is busy; never cancel active work."""
    while not stop.is_set():
        try:
            admission.update()
            admission.publish()
        except Exception as exc:
            log.error('Crawler resource monitor failed: %s', type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def mail_loop(db, settings, stop):
    def mail_call(fn):
        with settings._mailbox_lock:
            if settings.worker_enabled and not stop.is_set():
                return fn(db, settings)
    last_poll = 0
    while not stop.is_set():
        try:
            if settings.worker_enabled:
                db.set("worker_heartbeat", time.time())
                if time.time() - last_poll >= 30:
                    await asyncio.to_thread(mail_call, poll_inbox)
                    last_poll = time.time()
                await asyncio.to_thread(mail_call, send_one)
        except Exception as exc:
            log.error("Worker cycle failed: %s", type(exc).__name__)
            db.event("worker_error", {"error": type(exc).__name__})
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def job_loop(db, settings, stop, kinds, schedules=False, admission=None):
    while not stop.is_set():
        job = None
        admitted = False
        try:
            if schedules and settings.worker_enabled:
                for schedule in db.all("SELECT * FROM schedules WHERE enabled=1 AND next_run<=?", (time.time(),)):
                    db.enqueue("discover", {"query": schedule["query"], "campaign": schedule["campaign"],
                                           "country_hint": schedule["country_hint"], "limit": schedule["result_limit"]})
                    db.execute("UPDATE schedules SET next_run=? WHERE id=?",
                               (time.time() + schedule["interval_hours"] * 3600, schedule["id"]))
            admitted = settings.worker_enabled and (not admission or admission.acquire())
            job = db.claim(kinds) if admitted else None
            if job:
                # Stop gracefully without waiting for an entire deep crawl. Interrupted jobs resume on startup.
                task = asyncio.create_task(execute_job(db, settings, job))
                stopping = asyncio.create_task(stop.wait())
                try:
                    done, _ = await asyncio.wait({task, stopping}, timeout=settings.job_timeout_seconds,
                                                  return_when=asyncio.FIRST_COMPLETED)
                    if task in done:
                        await task
                    else:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        continued = reschedule(db, settings, db.one('SELECT * FROM jobs WHERE id=?', (job['id'],)))
                        if not continued:
                            db.execute("UPDATE jobs SET state=?,error=? WHERE id=?",
                                   ("pending" if stop.is_set() else "failed",
                                    "Interrupted for shutdown" if stop.is_set() else "Job exceeded configured timeout", job["id"]))
                finally:
                    stopping.cancel()
                    await asyncio.gather(stopping, return_exceptions=True)
                continue
        except Exception as exc:
            log.error("Job lane failed: %s", type(exc).__name__)
            db.event("worker_error", {"error": type(exc).__name__})
        finally:
            if admission and admitted:
                admission.release()
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def run(db, settings, stop):
    if db.get("demo") == "true":
        # A demo database remains offline even if live credentials are later configured.
        while not stop.is_set():
            if settings.worker_enabled:
                db.set("worker_heartbeat", time.time())
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
        return
    db.recover()
    from .crawl_resources import AdaptiveConcurrency
    admission = AdaptiveConcurrency(settings, db)
    # Inbox monitoring/sending never waits behind a long browser crawl. Verification stays serial.
    tasks = [asyncio.create_task(mail_loop(db, settings, stop)),
             asyncio.create_task(monitor_resources(admission, stop)),
             asyncio.create_task(job_loop(db, settings, stop, {"discover", "verify"}, schedules=True))]
    tasks.extend(asyncio.create_task(job_loop(db, settings, stop, {"research", "screenshot", "performance", 'contact_research','professional_research','social_research'}, admission=admission))
                 for _ in range(settings.crawl_concurrency))
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
