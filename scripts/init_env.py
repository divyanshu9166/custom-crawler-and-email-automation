"""Create a private .env without overwriting an existing configuration or printing secrets."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists; edit it in place. No values were changed.")
text = (root / ".env.example").read_text(encoding="utf-8")
for key in ["ADMIN_PASSWORD", "API_TOKEN", "REACHER_SECRET", "SEARXNG_SECRET", "N8N_ENCRYPTION_KEY"]:
    text = text.replace(f"{key}=\n", f"{key}={secrets.token_urlsafe(36)}\n")
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
    stream.write(text)
print("Created .env with private random credentials. Open it locally to configure your sender and services.")
