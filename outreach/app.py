import asyncio
import csv
import io
import json
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from decimal import Decimal

from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Settings
from .db import DB
from .research import add_lead, add_contact, contact_candidates, assert_contact_ownership
from .campaigns import review_lead, create_drafts, approve, resume_contact, revise_unsent_sequence
from .mail import mark_sent
from .worker import run, WorkerLock
from . import sales, deliverables, finance, aftercare, priorities
from .auth import COOKIE, MAX_AGE, issue_session, valid_session
from .preferences import Preferences, password_matches, session_key


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class LoginInput(Input):
    username: str = Field(max_length=200)
    password: str = Field(max_length=1000)


class CredentialsInput(Input):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_.@-]+$")
    new_password: str = Field(min_length=1, max_length=256)
    current_password: str = Field(max_length=1000)


class RuntimeSettingsInput(Input):
    worker_enabled: bool | None = Field(default=None, strict=True)
    sending_enabled: bool | None = Field(default=None, strict=True)


class ResearchSettingsInput(Input):
    auto_prepare_enabled: bool | None = Field(default=None, strict=True)
    linkedin_people_search_enabled: bool | None = Field(default=None, strict=True)
    linkedin_profile_experience_enabled: bool | None = Field(default=None, strict=True)
    linkedin_contact_info_enabled: bool | None = Field(default=None, strict=True)
    social_posts_enabled: bool | None = Field(default=None, strict=True)
    social_posts_max_profiles: int | None = Field(default=None, ge=1, le=4, strict=True)
    social_posts_max_posts: int | None = Field(default=None, ge=1, le=10, strict=True)


class MailSettingsInput(Input):
    sender_name: str | None = Field(default=None, max_length=150)
    sender_company: str | None = Field(default=None, max_length=200)
    sender_email: str | None = Field(default=None, max_length=254)
    sender_website: str | None = Field(default=None, max_length=2000)
    postal_address: str | None = Field(default=None, max_length=1000)
    smtp_host: str | None = Field(default=None, max_length=254)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = Field(default=None, max_length=254)
    smtp_password: str | None = Field(default=None, max_length=1000)
    smtp_security: Literal["starttls", "ssl"] | None = None
    imap_host: str | None = Field(default=None, max_length=254)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_user: str | None = Field(default=None, max_length=254)
    imap_password: str | None = Field(default=None, max_length=1000)
    imap_folder: str | None = Field(default=None, max_length=150)
    daily_send_limit: int | None = Field(default=None, ge=1, le=500)
    hourly_send_limit: int | None = Field(default=None, ge=1, le=500)
    min_send_interval_seconds: int | None = Field(default=None, ge=60, le=86400)
    send_hour_start: int | None = Field(default=None, ge=0, le=23)
    send_hour_end: int | None = Field(default=None, ge=1, le=24)
    domain_auth_confirmed: bool | None = None
    clear_smtp_password: bool = False
    clear_imap_password: bool = False


class WriterSettingsInput(Input):
    draft_api_url: str | None = Field(default=None, max_length=2000)
    draft_api_key: str | None = Field(default=None, max_length=1000)
    draft_model: str | None = Field(default=None, max_length=200)
    draft_timeout_seconds: float | None = Field(default=None, ge=5, le=180)
    clear_draft_api_key: bool = False


class LeadInput(Input):
    company: str = Field(min_length=2, max_length=200)
    website: str = Field(max_length=2000)
    campaign: Literal["A", "B"]
    source_url: str = Field(max_length=2000)
    country_hint: str = Field(default="", max_length=50)
    campaign_id: int | None = Field(default=None, ge=1)


class ContactInput(Input):
    email: str = Field(max_length=254)
    source_url: str = Field(max_length=2000)
    name: str = Field(default="", max_length=150)
    role: str = Field(default="", max_length=150)
    ownership_notes: str = Field(default="", max_length=2000)


class ProfileLeadInput(Input):
    company: str = Field(min_length=2, max_length=200)
    profile_url: str = Field(max_length=2000)
    campaign: Literal["A", "B"]
    country_hint: Literal["US", "UK"]
    campaign_id: int | None = Field(default=None, ge=1)


class ProfessionalResearchInput(Input):
    profile_url:str=Field(default='',max_length=2000)


class ProfessionalReviewInput(Input):
    capture_id:int=Field(ge=1)
    email:str=Field(max_length=254)
    employer_quote:str=Field(min_length=8,max_length=700)
    role_quote:str=Field(min_length=3,max_length=700)
    company_evidence_id:int=Field(ge=1)
    company_quote:str=Field(min_length=8,max_length=700)
    ownership_notes:str=Field(min_length=30,max_length=2000)
    reviewed_current_employer_and_publication:Literal[True]


class SearchInput(Input):
    query: str = Field(min_length=5, max_length=400)
    campaign: Literal["A", "B"]
    country_hint: Literal["US", "UK"]
    limit: int = Field(default=10, ge=1, le=30)
    campaign_id: int | None = Field(default=None, ge=1)
    profile_first: bool = False
    discovery_source: Literal['mixed', 'google_maps'] = 'mixed'


class CampaignCreateInput(Input):
    name: str = Field(min_length=3, max_length=100)
    goal: Literal['A', 'B']


class CampaignStateInput(Input):
    state: Literal['active', 'paused']


class CampaignBulkInput(Input):
    lead_ids: list[Annotated[int, Field(ge=1, strict=True)]] = Field(min_length=1, max_length=200)
    action: Literal['assign', 'delete', 'restore', 'prepare']
    campaign_id: int | None = Field(default=None, ge=1)
    reason: str = Field(default='', max_length=500)


class BrowserReferenceInput(Input):
    company: str = Field(min_length=2, max_length=200)
    source_url: str = Field(max_length=2000)
    website: str = Field(max_length=2000)
    campaign: Literal['A', 'B']
    country_hint: Literal['US', 'UK']
    observed_at: float
    observation: str = Field(min_length=8, max_length=300)
    public_business_confirmed: Literal[True]
    capture_method: Literal['operator_browser_reference', 'browser_connector_reference'] = 'operator_browser_reference'


class BusinessToolReviewInput(Input):
    chatbot_status: Literal['present', 'unknown']
    source_url: str = Field(max_length=2000)
    evidence_reference: str = Field(min_length=12, max_length=500)


class ReviewInput(Input):
    company: str = Field(min_length=2, max_length=200)
    country: Literal["US", "UK"]
    country_source: str = Field(max_length=2000)
    country_quote: str = Field(min_length=3, max_length=700)
    timezone: str = Field(max_length=100)
    business_type: Literal["corporate", "sole_trader", "other"]
    service: str
    website_scope: Literal['auto', 'website_launch', 'new_service_page'] = 'auto'
    fit_notes: str = Field(min_length=12, max_length=1500)
    evidence_id: int
    quote: str = Field(min_length=8, max_length=700)
    observation: str = Field(min_length=12, max_length=1200)
    suggestion: str = Field(min_length=12, max_length=1200)
    industry: str = Field(default="", max_length=150)
    channel_fit_notes: str = Field(default="", max_length=1500)
    primary_goal: Literal['inquiries_bookings', 'd2c_growth'] | None = None
    selling_stage: Literal['unknown', 'starting_ecommerce', 'selling_online', 'not_d2c'] = 'unknown'
    commerce_evidence_id: int | None = None
    commerce_quote: str = Field(default='', max_length=700)
    d2c_fit_notes: str = Field(default='', max_length=1500)
    channel_fit_status: Literal['unknown', 'confirmed', 'not_suitable'] = 'unknown'
    customer_permission_status: Literal['unknown', 'confirmed', 'not_suitable'] = 'unknown'
    recent_trigger: str = Field(default="", max_length=700)
    trigger_evidence_id: int | None = None
    trigger_quote: str = Field(default="", max_length=700)
    followup_suggestion: str = Field(default="", max_length=1200)
    followup_evidence_id: int | None = None
    followup_quote: str = Field(default="", max_length=700)
    profile_ownership_notes: str = Field(default="", max_length=2000)
    profile_activity_quote: str = Field(default="", max_length=700)
    website_search_notes: str = Field(default="", max_length=2000)
    website_search_reviewed: Literal[True] | None = None


class ApprovalInput(Input):
    eligibility_basis: str = Field(min_length=20, max_length=2000)
    contact_relevance: str = Field(min_length=12, max_length=1000)
    reviewed_all_messages: Literal[True]


class DraftInput(Input):
    subject: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=20, max_length=5000)

    @field_validator("subject")
    @classmethod
    def single_line(cls, value):
        if "\r" in value or "\n" in value:
            raise ValueError("Subject must be one line")
        return value


class SuppressionInput(Input):
    reason: str = Field(min_length=3, max_length=500)


class SuppressionEntryInput(SuppressionInput):
    email: str = Field(min_length=3, max_length=254)


class SequenceRevisionInput(Input):
    note: str = Field(min_length=20, max_length=2000)
    reviewed_pending_messages: Literal[True]


class ReconcileInput(Input):
    outcome: Literal["sent", "not_sent"]
    evidence: str = Field(min_length=20, max_length=2000)


class CSVInput(Input):
    content: str = Field(max_length=1_000_000)


class ScheduleInput(SearchInput):
    interval_hours: int = Field(default=24, ge=1, le=720)


class ProfileInput(Input):
    name: str = Field(max_length=150)
    role: str = Field(max_length=150)


class ResumeContactInput(Input):
    note: str = Field(min_length=20, max_length=2000)
    next_at: float
    reviewed_remaining_messages: Literal[True]


class ActivityInput(Input):
    channel: Literal["email", "linkedin", "x", "phone", "meeting", "other"]
    kind: Literal["note", "outreach", "reply", "opt_out"]
    note: str = Field(min_length=12, max_length=3000)
    source_url: str = Field(default="", max_length=2000)
    contact_id: int | None = None
    happened_at: float | None = None


class HoldReleaseInput(Input):
    note: str = Field(min_length=20, max_length=2000)
    reviewed_shared_history: Literal[True]


class SalesInput(Input):
    version: int = Field(ge=0)
    stage: Literal["new", "contacted", "interested", "qualified", "call_booked", "proposal", "won", "delivery", "completed", "nurture", "lost"]
    confirmed_problem: str = Field(default="", max_length=2000)
    primary_goal: str = Field(default="", max_length=1000)
    success_metric: str = Field(default="", max_length=1000)
    baseline_notes: str = Field(default="", max_length=2000)
    decision_maker: str = Field(default="", max_length=300)
    timeline: str = Field(default="", max_length=1000)
    budget_notes: str = Field(default="", max_length=1000)
    call_at: float | None = None
    next_action_at: float | None = None
    proposal_id: int | None = None
    agreement_reference: str = Field(default="", max_length=1000)
    payment_reference: str = Field(default="", max_length=1000)
    acceptance_reference: str = Field(default="", max_length=1000)
    outcome_notes: str = Field(default="", max_length=2000)


class TaskInput(Input):
    kind: Literal["audit", "concept", "demo", "call", "proposal", "followup", "delivery", "review"]
    title: str = Field(min_length=8, max_length=300)
    due_at: float = Field(gt=0)


class TaskCloseInput(Input):
    state: Literal["done", "cancelled"]
    outcome: str = Field(min_length=12, max_length=2000)


class FinancialInput(Input):
    kind: Literal['acquisition_cost', 'delivery_cost', 'maintenance_cost', 'payment', 'refund']
    currency: Literal['USD', 'GBP']
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str = Field(min_length=12, max_length=1000)
    note: str = Field(min_length=12, max_length=2000)
    happened_at: float | None = Field(default=None, gt=0)
    actual_transaction_confirmed: Literal[True]


class FinancialVoidInput(Input):
    reason: str = Field(min_length=12, max_length=2000)


class ClientPlanInput(Input):
    kind: Literal['maintenance', 'expansion', 'case_study']
    title: str = Field(min_length=8, max_length=200)
    scope: str = Field(min_length=20, max_length=4000)
    due_at: float = Field(gt=0)


class ClientPlanUpdate(Input):
    version: int = Field(ge=0)
    state: Literal['reviewed', 'agreed', 'completed', 'declined']
    agreement_reference: str = Field(default='', max_length=1000)
    permission_reference: str = Field(default='', max_length=1000)
    client_permission_confirmed: bool = False
    outcome_reference: str = Field(default='', max_length=1000)
    outcome_notes: str = Field(default='', max_length=2000)


class ProposalInput(Input):
    title: str = Field(min_length=12, max_length=200)
    scope: str = Field(min_length=12, max_length=4000)
    deliverables: str = Field(min_length=12, max_length=4000)
    timeline: str = Field(min_length=12, max_length=2000)
    exclusions: str = Field(min_length=12, max_length=3000)
    acceptance_criteria: str = Field(min_length=12, max_length=3000)
    payment_terms: str = Field(min_length=12, max_length=2000)
    ownership_revision_terms: str = Field(min_length=12, max_length=3000)
    fee: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["USD", "GBP"]


class ProposalReviewInput(Input):
    reviewed_scope_and_terms: Literal[True]


class ProposalDeliveryInput(Input):
    reference: str = Field(min_length=12, max_length=1000)
    actually_delivered: Literal[True]


class ArtifactPoint(Input):
    evidence_id: int
    quote: str = Field(min_length=8, max_length=700)
    observation: str = Field(min_length=12, max_length=1200)
    suggestion: str = Field(min_length=12, max_length=1200)


class FAQPoint(Input):
    evidence_id: int
    quote: str = Field(min_length=8, max_length=700)
    question: str = Field(min_length=5, max_length=300)


class ArtifactMarker(Input):
    point_index: int = Field(ge=0, le=2)
    left: float = Field(ge=0, le=100)
    top: float = Field(ge=0, le=100)


class ArtifactInput(Input):
    kind: Literal["audit", "concept", "faq_demo", "whatsapp_flow", "call_flow"]
    title: str = Field(min_length=5, max_length=200)
    points: list[ArtifactPoint] = Field(default_factory=list, max_length=3)
    faqs: list[FAQPoint] = Field(default_factory=list, max_length=10)
    headline: str = Field(default="", max_length=300)
    intro: str = Field(default="", max_length=1200)
    primary_action: str = Field(default="", max_length=150)
    screenshot_name: str = Field(default="", max_length=100)
    markers: list[ArtifactMarker] = Field(default_factory=list, max_length=3)
    reviewed_source_points: Literal[True]


def create_app(settings=None):
    settings = settings or Settings()
    preferences = Preferences(settings)
    if not settings.admin_password_hash and not settings.admin_password:
        raise RuntimeError("Configure a nonempty ADMIN_PASSWORD in .env, then recreate the app container")
    if len(settings.api_token) < 32:
        raise RuntimeError("Configure API_TOKEN with at least 32 characters in .env, then recreate the app container")
    db = DB(settings.database)

    @asynccontextmanager
    async def lifespan(app):
        # Keep one idle supervisor available so dashboard controls take effect
        # without recreating the container. Disabled lanes do no provider work.
        stop = asyncio.Event()
        lock = WorkerLock(settings.data_dir / "worker.lock")
        task = asyncio.create_task(run(db, settings, stop))
        try:
            yield
        finally:
            stop.set()
            try:
                await task
            finally:
                lock.close()

    app = FastAPI(title="Outreach Workbench", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.settings = db, settings
    basic, bearer = HTTPBasic(auto_error=False), HTTPBearer(auto_error=False)
    login_attempts = {}

    def auth(request: Request, creds: HTTPBasicCredentials | None = Depends(basic),
             token: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if token and secrets.compare_digest(token.credentials, settings.api_token):
            return "api"
        with preferences.lock:
            admin_ok = (valid_session(request.cookies.get(COOKIE), session_key(settings))
                        or (creds and secrets.compare_digest(creds.username.encode(), settings.admin_user.encode())
                            and password_matches(settings, creds.password)))
        if admin_ok:
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin")
                expected = settings.public_url.rstrip("/")
                if origin != expected:
                    raise HTTPException(403, "A same-origin request or bearer API token is required")
            return "admin"
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Basic"})

    @app.middleware("http")
    async def security(request, call_next):
        length = request.headers.get("content-length", "0")
        if length.isdigit() and int(length) > 1_100_000:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse({"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]}, status_code=422)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/login")
    async def login(value: LoginInput, request: Request):
        if request.headers.get("origin") != settings.public_url.rstrip("/"):
            raise HTTPException(403, "Use the configured workspace URL to sign in")
        now = time.time()
        for key in list(login_attempts):
            login_attempts[key] = [t for t in login_attempts[key] if now-t < 60]
            if not login_attempts[key]:
                del login_attempts[key]
        ip = request.client.host if request.client else "unknown"
        attempts = login_attempts.setdefault(ip, [])
        if len(attempts) >= 10 or len(login_attempts) > 1000:
            raise HTTPException(429, "Too many sign-in attempts; wait one minute")
        attempts.append(now)
        with preferences.lock:
            user_ok = secrets.compare_digest(value.username.encode(), settings.admin_user.encode())
            password_ok = password_matches(settings, value.password)
            login_key = session_key(settings)
        if not (user_ok and password_ok):
            raise HTTPException(401, "Username or password is incorrect")
        response = JSONResponse({"signed_in": True})
        response.set_cookie(COOKIE, issue_session(login_key), max_age=MAX_AGE,
                            httponly=True, secure=settings.public_url.startswith("https://"), samesite="strict", path="/")
        return response

    @app.post("/api/logout", dependencies=[Depends(auth)])
    def logout():
        response = JSONResponse({"signed_in": False})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/")
    def dashboard(request: Request, creds: HTTPBasicCredentials | None = Depends(basic),
                  token: HTTPAuthorizationCredentials | None = Depends(bearer)):
        try:
            auth(request, creds, token)
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
            return FileResponse(Path(__file__).parent / "static" / "login.html")
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/static/{name}")
    def static(name: str, request: Request, creds: HTTPBasicCredentials | None = Depends(basic),
               token: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if name not in {"app.js", "campaigns-dashboard.js", "campaigns-dashboard.css", "workspace.js", "sales.js", "growth.js", "workflow.js", "settings.js", "style.css", "login.js"}:
            raise HTTPException(404)
        if name in {"app.js", "campaigns-dashboard.js", "workspace.js", "sales.js", "growth.js", "workflow.js", "settings.js"}:
            auth(request, creds, token)
        return FileResponse(Path(__file__).parent / "static" / name)

    @app.get("/api/openapi", dependencies=[Depends(auth)])
    def spec():
        return app.openapi()

    @app.get("/api/settings", dependencies=[Depends(auth)])
    def workspace_settings():
        return {**preferences.public(), 'demo': db.get('demo') == 'true',
                'writer_last_check': json.loads(db.get('writer_last_check', 'null')),
                'paused': db.get('paused', 'true') != 'false'}

    @app.put("/api/settings/mail", dependencies=[Depends(auth)])
    def mail_settings(value: MailSettingsInput):
        return preferences.update_mail(db, value.model_dump(exclude_none=True))

    @app.put('/api/settings/writer', dependencies=[Depends(auth)])
    def writer_settings(value: WriterSettingsInput):
        return preferences.update_writer(db, value.model_dump(exclude_none=True))

    @app.post('/api/providers/writer/test', dependencies=[Depends(auth)])
    async def test_writer():
        from .email_writer import test_connection
        if db.get('demo') == 'true':
            raise ValueError('Offline demo cannot call the AI provider')
        frozen = settings.model_copy()
        started = time.time()
        marker = secrets.token_hex(8)
        def save(value):
            # A newer test or writer-settings save supersedes this check.
            with db.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute("SELECT value FROM settings WHERE key='writer_last_check'").fetchone()
                current = json.loads(row[0]) if row else None
                if current and current.get('check_id') == marker:
                    con.execute("UPDATE settings SET value=? WHERE key='writer_last_check'", (json.dumps(value),))
                    return True
                return False
        base = {'check_id': marker, 'model': frozen.draft_model.strip(), 'started_at': started}
        db.set('writer_last_check', json.dumps({**base, 'state': 'running', 'note': 'Synthetic AI connection test is running.'}))
        try:
            result = await asyncio.wait_for(asyncio.to_thread(test_connection, frozen), timeout=65)
            if not save({**base, **result, 'state': 'ready' if result['ready'] else 'output_incomplete', 'elapsed_seconds': round(time.time()-started, 1)}):
                raise ValueError('Writer settings or a newer test superseded this check; test the current saved configuration')
            return result
        except (ValueError, asyncio.TimeoutError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else 'AI test exceeded 65 seconds. No connection verdict; key validity is unknown. Check provider latency and VPS connectivity.'
            save({**base, 'state': 'failed', 'note': message, 'elapsed_seconds': round(time.time()-started, 1)})
            raise ValueError(message) from None

    @app.post('/api/leads/{lead_id}/prepare', dependencies=[Depends(auth)])
    def prepare_emails(lead_id: int):
        from .preparation import queue
        return {'job_id': queue(db, settings, lead_id)}

    @app.get('/api/leads/{lead_id}/preparation', dependencies=[Depends(auth)])
    def preparation_progress(lead_id: int):
        from .preparation import latest
        if not db.one('SELECT id FROM leads WHERE id=?', (lead_id,)):
            raise HTTPException(404)
        return latest(db, lead_id)

    @app.post('/api/preparation/batch', dependencies=[Depends(auth)])
    def prepare_batch(after_id: int = Query(default=0, ge=0)):
        from .preparation import queue
        queued, skipped = [], []
        leads = db.all("SELECT id FROM leads WHERE status IN ('review','qualified') AND id>? ORDER BY id LIMIT 100", (after_id,))
        for lead in leads:
            try:
                queued.append({'lead_id': lead['id'], 'job_id': queue(db, settings, lead['id'])})
            except ValueError as exc:
                skipped.append({'lead_id': lead['id'], 'reason': str(exc)})
        return {'queued': queued, 'skipped': skipped, 'limit': 100,
                'next_after_id': leads[-1]['id'] if len(leads) == 100 else 0, 'sending_changed': False}

    @app.put('/api/settings/runtime', dependencies=[Depends(auth)])
    def runtime_settings(value: RuntimeSettingsInput):
        return preferences.update_runtime(db, value.model_dump(exclude_none=True))

    @app.put('/api/settings/research', dependencies=[Depends(auth)])
    def research_settings(value: ResearchSettingsInput):
        return preferences.update_research(db, value.model_dump(exclude_none=True))

    @app.get('/api/source-status', dependencies=[Depends(auth)])
    def provider_status(lead_id: int | None = Query(default=None, ge=1)):
        from .source_status import snapshot
        return snapshot(db, settings, lead_id)

    @app.put("/api/settings/credentials", dependencies=[Depends(auth)])
    def credentials(value: CredentialsInput, request: Request):
        key = "credentials:" + (request.client.host if request.client else "unknown")
        attempts = [t for t in login_attempts.get(key, []) if time.time()-t < 60]
        if len(attempts) >= 5:
            raise HTTPException(429, "Too many account-change attempts; wait one minute")
        login_attempts[key] = attempts + [time.time()]
        preferences.update_credentials(db, value.username, value.new_password, value.current_password)
        response = JSONResponse({"saved": True, "signed_out": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/api/workflow", dependencies=[Depends(auth)])
    def workflow_state(lead_id: int | None = Query(default=None, ge=1), detail: bool = False):
        if detail:
            from .workflow_detail import detailed_snapshot
            return detailed_snapshot(db, settings, lead_id)
        from .workflow import snapshot
        return snapshot(db, settings, lead_id)

    @app.get("/api/research-status", dependencies=[Depends(auth)])
    def research_status(lead_id: int | None = Query(default=None, ge=1)):
        from .research_status import snapshot
        return snapshot(db, lead_id)

    @app.get('/api/source-coverage',dependencies=[Depends(auth)])
    def coverage(lead_id:int|None=Query(default=None,ge=1)):
        from .research_status import source_coverage
        with db.connect() as con:
            con.execute('BEGIN')
            if lead_id and not con.execute('SELECT 1 FROM leads WHERE id=?',(lead_id,)).fetchone():
                raise ValueError('Prospect not found')
            return source_coverage(con,lead_id,time.time())

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status():
        from .platform_access import access_status
        access=access_status(settings)
        return {"demo": db.get("demo") == "true", "sending_enabled": settings.sending_enabled,
                "worker_enabled": settings.worker_enabled, "paused": db.get("paused", "true") != "false",
                "sending_gaps": settings.sending_gaps(), "worker_heartbeat": db.get("worker_heartbeat"),
                "imap_error": db.get("imap_error"), "imap_caught_up": db.get("imap_caught_up") == "true",
                "imap_last_success": db.get("imap_last_success"), "search_provider": settings.search_provider,
                "discovery_platforms": settings.discovery_platforms.split(","),
                "ai_enabled": bool(settings.openai_api_key and settings.openai_model),
                "browser_enabled": settings.browser_enabled,
                'platform_browser_enabled':settings.platform_browser_enabled,
                'platform_browser_public_fallback':settings.platform_browser_public_fallback,
                'fxembed_profiles_enabled':settings.fxembed_profiles_enabled,
                'platform_browser_holds':{platform:value['reason'] for platform,value in access.items()},
                'platform_browser_access_issues':access,
                'crawler_runtime': json.loads(db.get('crawler_runtime', '{}')),
                "counts": {table: db.one(f"SELECT COUNT(*) n FROM {table}")["n"] for table in ["leads", "contacts", "suppression"]},
                "messages": db.all("SELECT state,COUNT(*) n FROM messages GROUP BY state"),
                "funnel": db.all("SELECT l.campaign,c.status,COUNT(*) n FROM contacts c JOIN leads l ON l.id=c.lead_id GROUP BY l.campaign,c.status")}

    @app.post("/api/pause", dependencies=[Depends(auth)])
    def pause():
        with preferences.lock:
            db.set("paused", "true")
            db.event("paused", {})
        return {"paused": True}

    @app.get('/api/delivery', dependencies=[Depends(auth)])
    def delivery(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        from .mail import mailbox_key, mailbox_usage
        now = time.time()
        with db.connect() as con:
            con.execute('BEGIN')
            return {
                'mailbox': mailbox_key(settings), 'daily_limit': settings.daily_send_limit,
                'hourly_limit': settings.hourly_send_limit,
                'used_24h': mailbox_usage(con, mailbox_key(settings), now - 86400),
                'used_1h': mailbox_usage(con, mailbox_key(settings), now - 3600),
                'states': [dict(r) for r in con.execute("SELECT delivery_state AS state,COUNT(*) AS count FROM contacts WHERE delivery_state<>'' GROUP BY delivery_state")],
                'queue_counts': [dict(r) for r in con.execute('SELECT state,COUNT(*) AS count FROM messages GROUP BY state')],
                'queue': [dict(r) for r in con.execute("""SELECT m.id,c.email,c.delivery_state,m.step,m.state,m.due_at,m.error,
                    (SELECT COUNT(*) FROM send_attempts a WHERE a.message_id=m.id) AS attempts
                    FROM messages m JOIN contacts c ON c.id=m.contact_id
                    WHERE m.state IN ('queued','sending','uncertain','failed') ORDER BY m.id DESC LIMIT ? OFFSET ?""", (limit, offset))],
                'suppressed_count': con.execute('SELECT COUNT(*) FROM suppression').fetchone()[0],
                'suppression': [dict(r) for r in con.execute('SELECT email,reason,created_at FROM suppression ORDER BY created_at DESC,email LIMIT ? OFFSET ?', (limit, offset))],
                'attempts': [dict(r) for r in con.execute('SELECT * FROM send_attempts ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))],
                'limit': limit, 'offset': offset,
                'note': 'SENT means SMTP accepted, not inbox placement. Unknown submissions require manual reconciliation. Budgets use rolling windows; suppression is permanent.'}

    @app.post('/api/suppression', dependencies=[Depends(auth)])
    def add_suppression(value: SuppressionEntryInput):
        from .web import normalize_email
        email = normalize_email(value.email)
        db.suppress(email, value.reason)
        db.event('suppressed', {'email': email, 'reason': value.reason})
        return {'email': email, 'state': 'UNSUBSCRIBED'}

    @app.post("/api/resume", dependencies=[Depends(auth)])
    def resume():
        with preferences.lock:
            if db.get("demo") == "true":
                raise ValueError("Offline demo cannot send; use a separate live database")
            if not settings.worker_enabled:
                raise ValueError("Enable the worker in Settings before resuming sending")
            if not settings.sending_enabled or settings.sending_gaps():
                raise ValueError("Complete email settings and enable sending in Settings before resuming")
            db.set("paused", "false")
            db.event("resumed", {})
        return {"paused": False}

    @app.get("/api/leads", dependencies=[Depends(auth)])
    def leads():
        return priorities.ranked(db, settings)

    @app.get('/api/campaigns', dependencies=[Depends(auth)])
    def campaigns_overview():
        from .campaign_manager import summary
        return summary(db)

    @app.post('/api/campaigns', dependencies=[Depends(auth)])
    def create_campaign(value: CampaignCreateInput):
        from .campaign_manager import create
        return {'id': create(db, value.name, value.goal)}

    @app.patch('/api/campaigns/{campaign_id}', dependencies=[Depends(auth)])
    def update_campaign(campaign_id: int, value: CampaignStateInput):
        from .campaign_manager import set_state
        return set_state(db, campaign_id, value.state)

    @app.get('/api/campaign-prospects', dependencies=[Depends(auth)])
    def campaign_prospects(campaign_id: int | None = Query(default=None, ge=1),
                           state: str = Query(default='all', max_length=30), market: Literal['', 'US', 'UK'] = '',
                           search: str = Query(default='', max_length=200), deleted: Literal['active', 'deleted', 'all'] = 'active',
                           limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        from .campaign_manager import prospects
        return prospects(db, campaign_id=campaign_id, state=state, market=market, search=search, deleted=deleted, limit=limit, offset=offset)

    @app.post('/api/campaign-prospects/bulk', dependencies=[Depends(auth)])
    def campaign_bulk(value: CampaignBulkInput):
        from .campaign_manager import bulk
        return bulk(db, settings, **value.model_dump())

    @app.get('/api/campaign-export', dependencies=[Depends(auth)])
    def campaign_export(campaign_id: int | None = Query(default=None, ge=1),
                        state: str = Query(default='all', max_length=30), market: Literal['', 'US', 'UK'] = '',
                        search: str = Query(default='', max_length=200), deleted: Literal['active', 'deleted', 'all'] = 'active'):
        from .campaign_manager import export_csv, where
        filters = dict(campaign_id=campaign_id, state=state, market=market, search=search, deleted=deleted)
        where(**filters)  # Validate before beginning a streaming response.
        return StreamingResponse(export_csv(db, **filters), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=campaign-prospects.csv'})

    @app.post("/api/leads", dependencies=[Depends(auth)])
    def new_lead(value: LeadInput):
        lead_id = add_lead(db, **value.model_dump())
        return {"id": lead_id, "job_id": db.enqueue("research", {"lead_id": lead_id})}

    @app.post("/api/import", dependencies=[Depends(auth)])
    def import_csv(value: CSVInput):
        rows, errors, ids = list(csv.DictReader(io.StringIO(value.content.lstrip('\ufeff')))), [], []
        if len(rows) > 500:
            raise ValueError("Import up to 500 rows at a time")
        for number, row in enumerate(rows, 2):
            try:
                parsed = LeadInput(**{key: row[key] for key in LeadInput.model_fields if row.get(key)})
                lid = add_lead(db, **parsed.model_dump())
                if row.get("email"):
                    cid = add_contact(db, lid, row["email"], row.get("email_source") or row["source_url"], row.get("name", ""), row.get("role", ""))
                    db.enqueue("verify", {"contact_id": cid})
                db.enqueue("research", {"lead_id": lid})
                ids.append(lid)
            except ValueError as exc:
                errors.append({"row": number, "error": str(exc)[:250]})
        return {"ids": ids, "errors": errors}

    @app.post("/api/discover", dependencies=[Depends(auth)])
    def discover(value: SearchInput):
        from .campaign_manager import assert_target
        assert_target(db, value.campaign_id, value.campaign)
        payload = value.model_dump(exclude_none=True)
        if value.discovery_source == 'google_maps':
            from .google_business import campaign
            if value.campaign != 'A':
                raise ValueError('Campaign 3 Google business prospects use website/inquiry goal A')
            payload['campaign_id'] = campaign(db, value.campaign_id)
            payload['profile_first'] = True
        else:
            payload.pop('discovery_source')
        if not payload['profile_first']:
            payload.pop('profile_first')
        return {"job_id": db.enqueue("discover", payload)}

    @app.get("/api/schedules", dependencies=[Depends(auth)])
    def schedules():
        return db.all("SELECT * FROM schedules ORDER BY id")

    @app.post("/api/schedules", dependencies=[Depends(auth)])
    def add_schedule(value: ScheduleInput):
        from .campaign_manager import assert_target
        assert_target(db, value.campaign_id, value.campaign)
        target = value.campaign_id
        if value.discovery_source == 'google_maps':
            from .google_business import campaign
            if value.campaign != 'A':
                raise ValueError('Campaign 3 Google business prospects use website/inquiry goal A')
            target = campaign(db, target)
        sid = db.execute("INSERT INTO schedules(query,campaign,country_hint,result_limit,interval_hours,next_run,campaign_id,profile_first,discovery_source) VALUES(?,?,?,?,?,?,?,?,?)",
                         (value.query, value.campaign, value.country_hint, value.limit, value.interval_hours, time.time(), target, int(value.profile_first or value.discovery_source == 'google_maps'), value.discovery_source))
        return {"id": sid}

    @app.delete("/api/schedules/{schedule_id}", dependencies=[Depends(auth)])
    def disable_schedule(schedule_id: int):
        db.execute("UPDATE schedules SET enabled=0 WHERE id=?", (schedule_id,))
        return {"status": "disabled"}

    @app.post("/api/profile-leads", dependencies=[Depends(auth)])
    def profile_lead(value: ProfileLeadInput):
        from .profiles import add_profile_lead
        lid = add_profile_lead(db, **value.model_dump())
        return {"id": lid, "job_id": db.enqueue("research", {"lead_id": lid})}

    @app.post('/api/browser-references', dependencies=[Depends(auth)])
    def browser_reference(value: BrowserReferenceInput):
        from .browser_references import save_reference
        return save_reference(db, **value.model_dump())

    @app.get("/api/leads/{lead_id}", dependencies=[Depends(auth)])
    def lead_detail(lead_id: int):
        from .professionals import captures,reviewed_publication
        row = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
        if not row:
            raise HTTPException(404)
        professional_captures=captures(db,lead_id)
        for source in professional_captures:
            source['reviewed_emails']=[email for email in source['published_emails'] if reviewed_publication(db,row,source['url'],email)]
        professional_report=db.one("SELECT detail FROM events WHERE kind='professional_research' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1",(lead_id,))
        crawl = db.one("SELECT * FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1", (lead_id,))
        evidence = db.all("SELECT * FROM evidence WHERE lead_id=?", (lead_id,))
        for page in evidence:
            page["current_for_review"] = (not crawl or page["fetched_at"] >= crawl["created_at"]) and time.time()-30*86400 <= page['fetched_at'] <= time.time()+60
            from .profiles import source_allowed
            page['business_for_review']=source_allowed(row,page['url'])
            from .social_research import is_social_evidence
            page['social_for_review'] = is_social_evidence(db, lead_id, page)
        from . import offers
        from .social_research import latest as latest_social_captures
        from .opportunities import proposals as offer_proposals
        from .email_writer import assert_ai_origin, configuration as writer_configuration
        contacts = db.all("SELECT * FROM contacts WHERE lead_id=?", (lead_id,))
        for contact in contacts:
            contact['verification_fresh'] = bool(contact['verification'] == 'safe' and contact['verified_at']
                and 0 <= time.time()-contact['verified_at'] <= settings.verification_max_age_hours*3600)
            origin = db.one("SELECT detail FROM events WHERE kind='drafts_created' AND contact_id=? ORDER BY id DESC LIMIT 1", (contact['id'],))
            contact['draft_origin'] = json.loads(origin['detail']) if origin else {}
            try:
                assert_ai_origin(db, contact['id'])
                contact['ai_drafts'] = True
                contact['ai_draft_issue'] = ''
            except ValueError as exc:
                contact['ai_drafts'] = False
                contact['ai_draft_issue'] = str(exc)
            try:
                assert_contact_ownership(db, contact, row)
                contact.update(source_eligible=True, source_issue='')
            except ValueError as exc:
                contact.update(source_eligible=False, source_issue=str(exc))
        artifacts = db.all('SELECT * FROM deliverables WHERE lead_id=? ORDER BY id DESC', (lead_id,))
        for artifact in artifacts:
            try:
                deliverables.assert_current_artifact(db, artifact)
                artifact['current_for_review'] = True
            except ValueError:
                artifact['current_for_review'] = False
        from .preparation import latest as preparation_status
        from .diagnostics import snapshot as audit_snapshot
        return {"lead": row, "evidence": evidence, "crawl": crawl,
                "diagnostics": {**audit_snapshot(db, row), 'journey_audit_available': settings.browser_enabled and settings.journey_audit_enabled and settings.auto_visual_audit},
                'preparation': preparation_status(db, lead_id),
                'professional_captures':professional_captures,
                'professional_report':json.loads(professional_report['detail']) if professional_report else None,
                'social_captures': latest_social_captures(db, lead_id),
                "contacts": contacts,
                "email_writer": writer_configuration(settings),
                "review_candidates": contact_candidates(db, lead_id),
                "messages": db.all("SELECT m.* FROM messages m JOIN contacts c ON c.id=m.contact_id WHERE c.lead_id=? ORDER BY m.contact_id,m.step", (lead_id,)),
                "events": db.all("SELECT e.* FROM events e LEFT JOIN contacts c ON c.id=e.contact_id WHERE c.lead_id=? OR json_extract(e.detail,'$.lead_id')=? ORDER BY e.id DESC LIMIT 50", (lead_id, lead_id)),
                "sales": db.one("SELECT * FROM sales WHERE lead_id=?", (lead_id,)) or {"stage": "new", "version": 0, "details": "{}", "cold_email_hold": 0},
                "activities": db.all("SELECT * FROM activities WHERE lead_id=? ORDER BY happened_at DESC,id DESC LIMIT 100", (lead_id,)),
                "tasks": db.all("SELECT * FROM tasks WHERE lead_id=? ORDER BY state,due_at", (lead_id,)),
                "proposals": db.all("SELECT * FROM proposals WHERE lead_id=? ORDER BY id DESC", (lead_id,)),
                "deliverables": artifacts,
                "priority": priorities.ranked(db, settings, lead_id)[0]['priority'],
                'offer_workflow': offers.snapshot(db, lead_id),
                'offer_proposals': offer_proposals(row, [e for e in evidence if e['current_for_review'] and e['business_for_review']]),
                "financial_entries": finance.entries(db, lead_id), "financial_report": finance.report(db, lead_id),
                "client_plans": db.all('SELECT * FROM client_plans WHERE lead_id=? ORDER BY due_at,id', (lead_id,))}

    @app.post('/api/leads/{lead_id}/finance', dependencies=[Depends(auth)])
    def financial_record(lead_id: int, value: FinancialInput):
        return {'id': finance.record(db, lead_id, value.model_dump())}

    @app.post('/api/finance/{entry_id}/void', dependencies=[Depends(auth)])
    def financial_void(entry_id: int, value: FinancialVoidInput):
        finance.void(db, entry_id, value.reason)
        return {'status': 'voided'}

    @app.post('/api/leads/{lead_id}/client-plans', dependencies=[Depends(auth)])
    def client_plan_create(lead_id: int, value: ClientPlanInput):
        return {'id': aftercare.create(db, lead_id, value.model_dump())}

    @app.put('/api/client-plans/{plan_id}', dependencies=[Depends(auth)])
    def client_plan_update(plan_id: int, value: ClientPlanUpdate):
        aftercare.update(db, plan_id, value.model_dump())
        return {'status': 'saved'}

    @app.get('/api/client-plans/{plan_id}/download', dependencies=[Depends(auth)])
    def client_plan_download(plan_id: int):
        return Response(aftercare.export(db, plan_id), media_type='text/html',
                        headers={'Content-Disposition': f'attachment; filename="case-study-{plan_id}.html"'})

    @app.post("/api/leads/{lead_id}/artifacts", dependencies=[Depends(auth)])
    def artifact_create(lead_id: int, value: ArtifactInput):
        return {"id": deliverables.create(db, lead_id, value.model_dump())}

    @app.post("/api/leads/{lead_id}/proof-preview", dependencies=[Depends(auth)])
    def prepare_proof_preview(lead_id: int):
        return {'id': deliverables.prepare_automatic(db, lead_id), 'sending': False}

    @app.post("/api/artifacts/{artifact_id}/approve", dependencies=[Depends(auth)])
    def artifact_review(artifact_id: int, value: ProposalReviewInput):
        deliverables.action(db, artifact_id, "approve")
        return {"status": "approved"}

    @app.post("/api/artifacts/{artifact_id}/sent", dependencies=[Depends(auth)])
    def artifact_delivery(artifact_id: int, value: ProposalDeliveryInput):
        deliverables.action(db, artifact_id, "sent", value.reference)
        return {"status": "recorded"}

    @app.get("/api/artifacts/{artifact_id}/download", dependencies=[Depends(auth)])
    def artifact_download(artifact_id: int):
        artifact = db.one("SELECT * FROM deliverables WHERE id=?", (artifact_id,))
        if not artifact:
            raise HTTPException(404)
        return Response(artifact["body"], media_type="text/html", headers={"Content-Disposition": f'attachment; filename="artifact-{artifact_id}.html"'})

    @app.get("/api/sales/report", dependencies=[Depends(auth)])
    def sales_report():
        return sales.report(db)

    @app.put("/api/leads/{lead_id}/sales", dependencies=[Depends(auth)])
    def sales_update(lead_id: int, value: SalesInput):
        sales.update_sales(db, lead_id, value.model_dump())
        return {"status": "saved"}

    @app.post("/api/leads/{lead_id}/activity", dependencies=[Depends(auth)])
    def activity(lead_id: int, value: ActivityInput):
        return {"id": sales.record_activity(db, lead_id, value.model_dump())}

    @app.post("/api/leads/{lead_id}/outreach-release", dependencies=[Depends(auth)])
    def release_company_hold(lead_id: int, value: HoldReleaseInput):
        sales.release_outreach_hold(db, lead_id, value.note)
        return {"status": "released", "note": "Held contacts still need their separate reviewed resume"}

    @app.post("/api/leads/{lead_id}/tasks", dependencies=[Depends(auth)])
    def task_create(lead_id: int, value: TaskInput):
        return {"id": sales.create_task(db, lead_id, value.model_dump())}

    @app.put("/api/tasks/{task_id}", dependencies=[Depends(auth)])
    def task_close(task_id: int, value: TaskCloseInput):
        sales.finish_task(db, task_id, value.state, value.outcome)
        return {"status": value.state}

    @app.post("/api/leads/{lead_id}/proposals", dependencies=[Depends(auth)])
    def proposal_create(lead_id: int, value: ProposalInput):
        return {"id": sales.create_proposal(db, lead_id, value.model_dump(mode="json"))}

    @app.post("/api/proposals/{proposal_id}/approve", dependencies=[Depends(auth)])
    def proposal_review(proposal_id: int, value: ProposalReviewInput):
        sales.proposal_action(db, proposal_id, "approve")
        return {"status": "approved"}

    @app.post("/api/proposals/{proposal_id}/sent", dependencies=[Depends(auth)])
    def proposal_delivered(proposal_id: int, value: ProposalDeliveryInput):
        sales.proposal_action(db, proposal_id, "sent", value.reference)
        return {"status": "recorded"}

    @app.get("/api/proposals/{proposal_id}/download", dependencies=[Depends(auth)])
    def proposal_download(proposal_id: int):
        proposal = db.one("SELECT * FROM proposals WHERE id=?", (proposal_id,))
        if not proposal:
            raise HTTPException(404)
        return Response(proposal["body"], media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="proposal-{proposal_id}.md"'})

    @app.post("/api/leads/{lead_id}/research", dependencies=[Depends(auth)])
    def research(lead_id: int):
        return {"job_id": db.enqueue("research", {"lead_id": lead_id})}

    @app.post('/api/leads/{lead_id}/continue-research', dependencies=[Depends(auth)])
    def continue_research(lead_id: int):
        from .research import research_checkpoint
        research_checkpoint(db, lead_id)
        return {'job_id': db.enqueue('research', {'lead_id': lead_id, 'continuation': True})}

    @app.post('/api/leads/{lead_id}/contact-research', dependencies=[Depends(auth)])
    def contact_research(lead_id: int):
        from .contact_recovery import eligible_lead
        eligible_lead(db, lead_id)
        return {'job_id': db.enqueue('contact_research', {'lead_id': lead_id})}

    @app.post('/api/leads/{lead_id}/social-research', dependencies=[Depends(auth)])
    def social_research_job(lead_id: int):
        from .social_research import eligible_lead
        eligible_lead(db, lead_id)
        if not settings.platform_browser_enabled or not settings.social_posts_enabled:
            raise ValueError('Enable VPS browser and social post research first')
        return {'job_id': db.enqueue('social_research', {'lead_id': lead_id})}

    @app.post('/api/leads/{lead_id}/professional-research',dependencies=[Depends(auth)])
    def professional_research(lead_id:int,value:ProfessionalResearchInput):
        from .contact_recovery import eligible_lead
        from .professionals import professional_target
        eligible_lead(db,lead_id)
        payload={'lead_id':lead_id}
        if value.profile_url:
            payload['profile_url']=professional_target(value.profile_url)[1]
        return {'job_id':db.enqueue('professional_research',payload)}

    @app.post('/api/leads/{lead_id}/professional-review',dependencies=[Depends(auth)])
    def professional_review(lead_id:int,value:ProfessionalReviewInput):
        from .professionals import review_contact
        return {'contact_id':review_contact(db,lead_id,value.model_dump()),'state':'reviewed_contact_unverified'}

    @app.get('/api/providers/reacher', dependencies=[Depends(auth)])
    async def verifier_status():
        from .providers import reacher_readiness
        return await reacher_readiness(settings)

    @app.post("/api/leads/{lead_id}/screenshot", dependencies=[Depends(auth)])
    def audit(lead_id: int):
        row = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
        if not row or row["lead_kind"] == "profile":
            raise ValueError("Website visual audit needs an official company website")
        return {"job_id": db.enqueue("screenshot", {"lead_id": lead_id})}

    @app.post("/api/leads/{lead_id}/performance", dependencies=[Depends(auth)])
    def performance(lead_id: int):
        row = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
        if not row:
            raise HTTPException(404)
        if row["lead_kind"] == "profile":
            raise ValueError("PageSpeed needs an official company website")
        return {"job_id": db.enqueue("performance", {"lead_id": lead_id})}

    @app.get("/api/screenshots/{name}", dependencies=[Depends(auth)])
    def get_screenshot(name: str):
        import re
        if not re.fullmatch(r"lead-\d+-\d+(?:-[a-f0-9]{6}-(?:mobile|desktop))?\.png", name):
            raise HTTPException(404)
        path = settings.data_dir / "screenshots" / name
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)

    @app.post("/api/leads/{lead_id}/review", dependencies=[Depends(auth)])
    def review(lead_id: int, value: ReviewInput):
        review_lead(db, lead_id, value.model_dump())
        return {"status": "qualified"}

    @app.post("/api/leads/{lead_id}/contacts", dependencies=[Depends(auth)])
    def contact(lead_id: int, value: ContactInput):
        cid = add_contact(db, lead_id, **value.model_dump())
        row = db.one('SELECT * FROM contacts WHERE id=?', (cid,))
        try:
            assert_contact_ownership(db, row, db.one('SELECT * FROM leads WHERE id=?', (lead_id,)))
        except ValueError as exc:
            return {'id': cid, 'job_id': None, 'source_eligible': False, 'source_issue': str(exc)}
        return {"id": cid, "job_id": db.enqueue("verify", {"contact_id": cid})}

    @app.post("/api/contacts/{contact_id}/verify", dependencies=[Depends(auth)])
    def verify(contact_id: int):
        row = db.one('SELECT * FROM contacts WHERE id=?', (contact_id,))
        if not row:
            raise HTTPException(404)
        assert_contact_ownership(db, row, db.one('SELECT * FROM leads WHERE id=?', (row['lead_id'],)))
        return {"job_id": db.enqueue("verify", {"contact_id": contact_id})}

    @app.put("/api/contacts/{contact_id}/profile", dependencies=[Depends(auth)])
    def profile(contact_id: int, value: ProfileInput):
        row = db.one("SELECT status FROM contacts WHERE id=?", (contact_id,))
        if not row or row["status"] != "new":
            raise ValueError("Only contacts without outreach history can be edited")
        with db.connect() as con:
            changed = con.execute("UPDATE contacts SET name=?,role=? WHERE id=? AND status='new'", (value.name, value.role, contact_id)).rowcount
            if not changed:
                raise ValueError("Contact changed; reload before editing")
        return {"status": "saved", "note": "Regenerate any existing drafts to use the updated name"}

    @app.put('/api/leads/{lead_id}/business-tools', dependencies=[Depends(auth)])
    def business_tool_review(lead_id: int, value: BusinessToolReviewInput):
        from .profiles import source_allowed
        from .research import fresh_evidence
        from .web import crawl_url
        lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
        if not lead:
            raise HTTPException(404)
        if not source_allowed(lead, value.source_url) or not any(crawl_url(p['url']) == crawl_url(value.source_url) for p in fresh_evidence(db, lead_id)):
            raise ValueError('Existing-tool review needs a current saved official business page and an inspectable evidence reference')
        db.event('business_tool_review', {'lead_id': lead_id, **value.model_dump()})
        return {'status': 'saved', 'note': 'Tool observation recorded. Existing copy preserved; rewrite to use this context.'}

    @app.post("/api/contacts/{contact_id}/draft", dependencies=[Depends(auth)])
    def draft(contact_id: int):
        create_drafts(db, settings, contact_id)
        return {"status": "drafted"}

    @app.post('/api/contacts/{contact_id}/single-email', dependencies=[Depends(auth)])
    def single_email(contact_id: int):
        from .campaigns import archive_followups
        return archive_followups(db, contact_id)

    @app.put("/api/messages/{message_id}", dependencies=[Depends(auth)])
    def edit_message(message_id: int, value: DraftInput):
        row = db.one("SELECT * FROM messages WHERE id=?", (message_id,))
        if not row or row["state"] != "draft":
            raise ValueError("Only unapproved drafts can be edited")
        with db.connect() as con:
            changed = con.execute("UPDATE messages SET subject=?,body=? WHERE id=? AND state='draft'", (value.subject, value.body, message_id)).rowcount
            if not changed:
                raise ValueError("Draft was approved during editing; reload before continuing")
        db.event("draft_edited", {"message": message_id}, row["contact_id"])
        return {"status": "saved"}

    @app.post("/api/contacts/{contact_id}/approve", dependencies=[Depends(auth)])
    def approval(contact_id: int, value: ApprovalInput):
        approve(db, settings, contact_id, value.eligibility_basis, value.contact_relevance)
        return {"status": "queued"}

    @app.post("/api/contacts/{contact_id}/suppress", dependencies=[Depends(auth)])
    def suppress(contact_id: int, value: SuppressionInput):
        row = db.one("SELECT email FROM contacts WHERE id=?", (contact_id,))
        if not row:
            raise HTTPException(404)
        db.suppress(row["email"], value.reason)
        db.event("suppressed", {"reason": value.reason}, contact_id)
        return {"status": "suppressed"}

    @app.post("/api/contacts/{contact_id}/resume", dependencies=[Depends(auth)])
    def resume_held_contact(contact_id: int, value: ResumeContactInput):
        resume_contact(db, settings, contact_id, value.note, value.next_at)
        return {"status": "active"}

    @app.post('/api/contacts/{contact_id}/revise', dependencies=[Depends(auth)])
    def revise_pilot(contact_id: int, value: SequenceRevisionInput):
        revise_unsent_sequence(db, contact_id, value.note)
        return {'status': 'draft', 'note': 'Approval revoked; review current evidence and all messages before approving again'}

    @app.post("/api/messages/{message_id}/reconcile", dependencies=[Depends(auth)])
    def reconcile(message_id: int, value: ReconcileInput):
        row = db.one("SELECT * FROM messages WHERE id=?", (message_id,))
        if not row or row["state"] != "uncertain":
            raise ValueError("Only uncertain sends can be reconciled")
        if value.outcome == "sent":
            mark_sent(db, row, time.time(), followups_enabled=settings.followups_enabled)
        else:
            from .mail import reconcile_not_sent
            reconcile_not_sent(db, row)
        # Never automatically resume after reconciliation: preserve replies/opt-outs received meanwhile.
        db.event("send_reconciled", value.model_dump(), row["contact_id"])
        return {"status": "reconciled", "note": "Contact remains held; inspect its conversation before any further outreach"}

    @app.get("/api/jobs", dependencies=[Depends(auth)])
    def jobs():
        return db.all("SELECT * FROM jobs ORDER BY id DESC LIMIT 100")

    @app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(auth)])
    def retry(job_id: int):
        db.execute("UPDATE jobs SET state='pending',attempts=0,due_at=?,error='' WHERE id=? AND state='failed'", (time.time(), job_id))
        return {"status": "queued"}

    @app.get("/api/events", dependencies=[Depends(auth)])
    def events():
        return db.all("SELECT * FROM events ORDER BY id DESC LIMIT 100")

    @app.get("/api/export", dependencies=[Depends(auth)])
    def export():
        rows = db.all("SELECT l.company,CASE WHEN l.lead_kind='profile' THEN '' ELSE l.domain END domain,l.website,l.profile_url,l.lead_kind,l.website_status,l.campaign,l.country,c.email,c.name,c.role,c.verification,c.status FROM leads l LEFT JOIN contacts c ON c.lead_id=l.id ORDER BY l.id")
        out = io.StringIO()
        writer = csv.writer(out)
        keys = ["company", "domain", "website", "profile_url", "lead_kind", "website_status", "campaign", "country", "email", "name", "role", "verification", "status"]
        writer.writerow(keys)
        for row in rows:
            writer.writerow([("'" + str(row[k]) if str(row[k] or "").startswith(("=", "+", "-", "@", "\t", "\r")) else row[k]) for k in keys])
        return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=leads.csv"})

    @app.get("/unsubscribe/{token}", response_class=HTMLResponse)
    def unsubscribe_page(token: str):
        if not db.one("SELECT id FROM contacts WHERE unsubscribe_token=?", (token,)):
            raise HTTPException(404)
        return '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Stop emails</title><h1>Stop these emails</h1><form method="post"><button type="submit">Unsubscribe</button></form></html>'

    @app.post("/unsubscribe/{token}", response_class=HTMLResponse)
    def unsubscribe(token: str):
        with db.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT id,email,delivery_state FROM contacts WHERE unsubscribe_token=?", (token,)).fetchone()
            if not row:
                raise HTTPException(404)
            db.suppress(row['email'], 'unsubscribe link', con)
            if row['delivery_state'] != 'UNSUBSCRIBED':
                con.execute('INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)',
                            ('opt_out', row['id'], '{"channel":"link"}', time.time()))
        return "<h1>You have been unsubscribed.</h1>"

    return app
