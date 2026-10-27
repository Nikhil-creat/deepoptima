"""Transactional email over HTTPS APIs (works on hosts that block SMTP). Providers: brevo, resend, console (dev: logs the email)."""
import html as _html, json, logging, re, urllib.error, urllib.request
from .settings import settings

log = logging.getLogger("studio.mail")
OUTBOX: list[dict] = []          # filled by the console provider (used by tests / local dev)


def enabled() -> bool:
    p = settings.email_provider
    return p == "console" or (p in ("brevo", "resend") and bool(settings.email_api_key and settings.email_from))


def _post(url: str, headers: dict, payload: dict) -> bool:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={**headers, "Content-Type": "application/json", "User-Agent": "deepoptima-studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        log.warning("email provider rejected the message (%s): %s", e.code, e.read()[:200])
    except Exception as e:                                           # network problems must never break a request
        log.warning("email send failed: %s", e)
    return False


def send_email(to: str, subject: str, text: str) -> bool:
    """Blocking; call via BackgroundTasks / a thread."""
    if not enabled():
        return False
    body = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', _html.escape(text)).replace("\n", "<br>")
    page = f'<div style="font-family:system-ui,Segoe UI,sans-serif;font-size:15px;line-height:1.55;color:#111827">{body}</div>'
    p = settings.email_provider
    if p == "console":
        OUTBOX.append({"to": to, "subject": subject, "text": text})
        log.info("EMAIL to=%s subject=%s\n%s", to, subject, text)
        return True
    if p == "brevo":
        return _post("https://api.brevo.com/v3/smtp/email", {"api-key": settings.email_api_key, "accept": "application/json"},
                     {"sender": {"name": settings.email_from_name, "email": settings.email_from}, "to": [{"email": to}],
                      "subject": subject, "textContent": text, "htmlContent": page})
    if p == "resend":
        return _post("https://api.resend.com/emails", {"Authorization": f"Bearer {settings.email_api_key}"},
                     {"from": f"{settings.email_from_name} <{settings.email_from}>", "to": [to], "subject": subject, "text": text, "html": page})
    return False


def verify_text(name: str, link: str) -> str:
    return f"Hi {name},\n\nConfirm your email address for DeepOptima Studio:\n{link}\n\nThe link works for 3 days. If you did not create an account, ignore this message."


def reset_text(name: str, link: str) -> str:
    return f"Hi {name},\n\nSomeone asked to reset your DeepOptima Studio password. To choose a new one, open:\n{link}\n\nThe link works for 1 hour and only once. If this was not you, ignore this message; your password stays the same."
