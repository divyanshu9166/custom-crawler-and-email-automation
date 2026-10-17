import asyncio
from pathlib import Path
from typing import Literal
from pydantic import Field, PrivateAttr
from threading import RLock
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    data_dir: Path = Path("data")
    admin_user: str = "admin"
    admin_password: str = ""
    admin_password_hash: str = ""
    session_version: str = ""
    _mailbox_lock: RLock = PrivateAttr(default_factory=RLock)
    api_token: str = ""
    public_url: str = "http://localhost:8000"
    worker_enabled: bool = True
    sending_enabled: bool = False
    sender_name: str = ""
    sender_company: str = ""
    sender_email: str = ""
    sender_website: str = ""
    postal_address: str = ""
    domain_auth_confirmed: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_security: str = "starttls"
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    daily_send_limit: int = Field(20, ge=1, le=500)
    min_send_interval_seconds: int = Field(180, ge=60)
    send_hour_start: int = Field(9, ge=0, le=23)
    send_hour_end: int = Field(17, ge=1, le=24)
    verification_max_age_hours: int = Field(72, ge=1, le=168)
    reacher_url: str = "http://localhost:8080"
    reacher_secret: str = ""
    reacher_path: str = "/v0/check_email"
    reacher_from_email: str = ""
    reacher_hello_name: str = ""
    verification_interval_seconds: int = Field(10, ge=1)
    search_provider: str = "searxng"
    search_language: str = "en-GB"
    searxng_url: str = "http://localhost:8888"
    search_fallback_engines: str = "yahoo,mojeek"
    search_cache_seconds: int = Field(900, ge=0, le=86400)
    search_failure_cooldown_seconds: int = Field(60, ge=1, le=3600)
    commoncrawl_hints_enabled: bool = True
    professional_refresh_official_links: bool = True
    _discovery_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _discovery_state: dict = PrivateAttr(default_factory=dict)
    discovery_platforms: str = "linkedin.com,x.com,peopleperhour.com,clutch.co,crunchbase.com,facebook.com,instagram.com,google.com"
    discovery_query_delay_seconds: float = Field(2, ge=0.1)
    discovery_max_signals: int = Field(40, ge=1, le=200)
    auto_contact_research: bool = True
    contact_research_max_pages: int = Field(6, ge=1, le=30)
    auto_professional_research: bool = True
    professional_max_profiles: int = Field(6,ge=1,le=20)
    professional_max_queries: int = Field(10,ge=1,le=20)
    linkedin_people_search_enabled: bool = True
    linkedin_profile_experience_enabled: bool = True
    linkedin_contact_info_enabled: bool = False
    social_posts_enabled: bool = True
    social_posts_max_profiles: int = Field(2, ge=1, le=4)
    social_posts_max_posts: int = Field(3, ge=1, le=10)
    fxembed_profiles_enabled: bool = False
    serpapi_key: str = ""
    pagespeed_api_key: str = ""
    crawl_max_pages: int = Field(30, ge=1, le=500)
    crawl_max_depth: int = Field(3, ge=1, le=10)
    crawl_max_sitemaps: int = Field(6, ge=0, le=50)
    crawl_render_mode: Literal["always", "auto", "never"] = "always"
    crawl_concurrency: int = Field(1, ge=1, le=8)
    job_timeout_seconds: int = Field(1800, ge=60, le=14400)
    crawl_delay_seconds: float = Field(2, ge=0.1)
    crawl_request_timeout_seconds: float = Field(30, ge=5, le=120)
    crawl_http_retries: int = Field(1, ge=0, le=2)
    crawl_resume_max_retries: int = Field(2, ge=0, le=5)
    crawl_auto_continue: bool = True
    crawl_auto_max_passes: int = Field(6, ge=1, le=30)
    crawl_auto_max_pages: int = Field(180, ge=1, le=1500)
    crawl_adaptive_pacing: bool = True
    crawl_adaptive_max_delay_seconds: float = Field(10, ge=1, le=60)
    crawl_adaptive_concurrency: bool = True
    crawl_memory_budget_mb: int = Field(0, ge=0, le=131072)
    crawl_task_memory_mb: int = Field(512, ge=128, le=8192)
    crawl_retry_max_wait_seconds: float = Field(10, ge=1, le=60)
    crawler_user_agent: str = "OutreachResearchBot/0.1"
    max_page_bytes: int = 4_000_000
    browser_resource_bytes: int = Field(8_000_000, ge=100000)
    browser_page_bytes: int = Field(60_000_000, ge=1000000)
    browser_resource_concurrency: int = Field(6, ge=1, le=16)
    browser_settle_seconds: float = Field(2, ge=0.1, le=15)
    openai_api_key: str = ""
    openai_model: str = ""
    draft_api_url: str = "https://integrate.api.nvidia.com/v1"
    draft_api_key: str = ""
    draft_model: str = ""
    draft_timeout_seconds: float = Field(90, ge=5, le=180)
    browser_enabled: bool = True
    platform_browser_enabled: bool = False
    platform_browser_public_fallback: bool = True
    platform_browser_headless: bool = True
    platform_browser_timeout_seconds: float = Field(45, ge=10, le=120)
    platform_browser_delay_seconds: float = Field(5, ge=1, le=60)
    platform_browser_search_steps: int = Field(6, ge=1, le=20)
    platform_browser_search_pages: int = Field(3, ge=1, le=5)
    platform_browser_search_timeout_seconds: float = Field(60, ge=10, le=180)
    _platform_browser_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _platform_browser_holds: dict = PrivateAttr(default_factory=dict)
    _platform_browser_persisted_holds: set = PrivateAttr(default_factory=set)
    auto_visual_audit: bool = True

    @property
    def database(self):
        return self.data_dir / "outreach.db"

    def sending_gaps(self):
        required = ["sender_name", "sender_company", "sender_email", "postal_address",
                    "smtp_host", "smtp_user", "smtp_password", "imap_host", "imap_user", "imap_password"]
        gaps = [key for key in required if not getattr(self, key)]
        if not self.domain_auth_confirmed:
            gaps.append("domain_auth_confirmed")
        if not self.public_url.startswith("https://"):
            gaps.append("public_url must be HTTPS for unsubscribe links")
        if self.smtp_security not in {"starttls", "ssl"}:
            gaps.append("smtp_security must be starttls or ssl")
        if self.send_hour_end <= self.send_hour_start:
            gaps.append("send_hour_end must be later than send_hour_start")
        return gaps
