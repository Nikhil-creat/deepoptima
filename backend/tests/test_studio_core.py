import time
import pytest
from app.studio import security as sec
from app.studio.settings import normalize_db_url
from app.studio.engine.profile import csv_safe


def test_password_hash_roundtrip():
    h = sec.hash_password("correct horse battery")
    assert sec.verify_password("correct horse battery", h)
    assert not sec.verify_password("wrong", h) and not sec.verify_password("x", "garbage")
    assert sec.hash_password("same") != sec.hash_password("same")          # salted


def test_token_roundtrip_and_tamper():
    t = sec.make_token({"sub": "5", "tv": 0}, "secret", 1)
    assert sec.read_token(t, "secret")["sub"] == "5"
    assert sec.read_token(t, "other") is None
    head, body, sig = t.split(".")
    forged = ".".join([head, sec._b64(b'{"sub":"1","tv":0,"exp":9999999999}'), sig])
    assert sec.read_token(forged, "secret") is None
    assert sec.read_token("a.b", "secret") is None
    expired = sec.make_token({"sub": "5"}, "secret", -1)
    assert sec.read_token(expired, "secret") is None


def test_password_policy_and_email():
    assert sec.password_problem("short") and sec.password_problem("aaaaaaaaaaaa") and sec.password_problem("password1")
    assert sec.password_problem("a-Good_pass-phrase-42") is None
    assert sec.clean_email("  Me@Example.COM ") == "me@example.com"
    assert sec.clean_email("nope") is None and sec.clean_email("a@b") is None


def test_limiter_window():
    lim = sec.Limiter()
    assert all(lim.allow("k", 3, 0.2) for _ in range(3)) and not lim.allow("k", 3, 0.2)
    time.sleep(0.25)
    assert lim.allow("k", 3, 0.2)
    lim.reset("k"); assert lim.count("k", 10) == 0


def test_db_url_normalisation():
    assert normalize_db_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    n = normalize_db_url("postgresql://u:p@h/db?sslmode=require&channel_binding=require")
    assert n == "postgresql+asyncpg://u:p@h/db?ssl=require"
    assert normalize_db_url("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"


def test_csv_formula_injection_neutralised():
    assert csv_safe("=1+1") == "'=1+1" and csv_safe("@SUM(A1)") == "'@SUM(A1)" and csv_safe("hello") == "hello" and csv_safe(3) == 3


def test_purpose_tokens_and_api_keys():
    t = sec.purpose_token("reset", 7, "s", 3600, f=sec.fingerprint("pw-hash"))
    body = sec.read_purpose(t, "reset", "s")
    assert body["sub"] == "7" and body["f"] == sec.fingerprint("pw-hash")
    assert sec.read_purpose(t, "verify", "s") is None            # wrong purpose
    assert sec.read_purpose(sec.purpose_token("reset", 7, "s", -5), "reset", "s") is None   # expired
    key, prefix, h = sec.new_api_key()
    assert key.startswith("dok_") and key.startswith(prefix) and h == sec.hash_key(key) and len(h) == 64


def test_mailer_console_provider(monkeypatch=None):
    from app.studio import mailer
    from app.studio.settings import settings
    old = settings.email_provider
    settings.email_provider = "console"
    try:
        assert mailer.enabled() and mailer.send_email("a@b.co", "hi", "link https://x.y/#/reset?token=abc")
        assert mailer.OUTBOX[-1]["to"] == "a@b.co"
        settings.email_provider = ""
        assert not mailer.enabled() and not mailer.send_email("a@b.co", "hi", "x")
    finally:
        settings.email_provider = old
