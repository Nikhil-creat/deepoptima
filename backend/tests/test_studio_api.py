"""End-to-end API tests (run in CI where fastapi/sqlalchemy are installed)."""
import io
import pytest

pytest.importorskip("fastapi"); pytest.importorskip("httpx"); pytest.importorskip("aiosqlite"); pytest.importorskip("sqlalchemy")
import anyio, httpx
from app.studio.db import init_db
from app.studio.main import app
from tests.test_studio_engine import wine_csv

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def client():
    await init_db()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def signup(c, email, name="Tester"):
    r = await c.post("/api/auth/register", json={"email": email, "password": "a-Good_pass-phrase-42", "name": name, "accept_terms": True})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


async def test_auth_flow():
    async with await client() as c:
        bad = await c.post("/api/auth/register", json={"email": "a@b.co", "password": "short", "name": "x", "accept_terms": True})
        assert bad.status_code == 400
        assert (await c.post("/api/auth/register", json={"email": "a@b.co", "password": "a-Good_pass-phrase-42", "name": "x", "accept_terms": False})).status_code == 400
        h = await signup(c, "auth@example.com")
        assert (await c.post("/api/auth/register", json={"email": "AUTH@example.com", "password": "a-Good_pass-phrase-42", "name": "x", "accept_terms": True})).status_code == 409
        assert (await c.post("/api/auth/login", json={"email": "auth@example.com", "password": "wrong-password"})).status_code == 401
        assert (await c.post("/api/auth/login", json={"email": "auth@example.com", "password": "a-Good_pass-phrase-42"})).status_code == 200
        assert (await c.get("/api/me")).status_code == 401
        me = await c.get("/api/me", headers=h)
        assert me.status_code == 200 and me.json()["user"]["email"] == "auth@example.com"
        r = await c.post("/api/me/password", headers=h, json={"old_password": "a-Good_pass-phrase-42", "new_password": "another-Good_phrase-77"})
        assert r.status_code == 200
        assert (await c.get("/api/me", headers=h)).status_code == 401           # old token revoked by password change


async def test_full_flow_and_isolation():
    async with await client() as c:
        h = await signup(c, "flow@example.com")
        other = await signup(c, "other@example.com")
        bad = await c.post("/api/datasets", headers=h, files={"file": ("x.exe", b"abc", "application/octet-stream")})
        assert bad.status_code == 400
        up = await c.post("/api/datasets", headers=h, data={"name": "Wine"}, files={"file": ("wine.csv", wine_csv(), "text/csv")})
        assert up.status_code == 201, up.text
        did = up.json()["id"]
        assert any(t["name"] == "target" and t["usable"] for t in up.json()["profile"]["targets"])
        assert (await c.get(f"/api/datasets/{did}", headers=other)).status_code == 404

        body = {"dataset_id": did, "name": "t1", "target": "target", "families": ["tree", "linear"], "generations": 1, "population": 4, "time_limit_s": 20}
        ex = await c.post("/api/experiments", headers=h, json=body)
        assert ex.status_code == 201, ex.text
        eid = ex.json()["id"]
        assert (await c.post("/api/experiments", headers=h, json=body)).status_code == 409        # one active job per user
        for _ in range(180):
            d = (await c.get(f"/api/experiments/{eid}", headers=h)).json()
            if d["status"] in ("done", "failed", "cancelled"):
                break
            await anyio.sleep(0.5)
        assert d["status"] == "done", d
        assert d["trials"] and d["result"]["best_trial_id"] and d["baseline_score"] is not None
        assert (await c.get(f"/api/experiments/{eid}", headers=other)).status_code == 404

        tid = d["result"]["best_trial_id"]
        row = {"alcohol": 13.0, "malic_acid": 2.0, "ash": 2.4, "alcalinity_of_ash": 19.0, "magnesium": 100, "total_phenols": 2.5, "flavanoids": 2.6,
               "nonflavanoid_phenols": 0.3, "proanthocyanins": 1.5, "color_intensity": 5.0, "hue": 1.0, "od280/od315_of_diluted_wines": 3.0, "proline": 1000, "region": "north"}
        p = await c.post(f"/api/experiments/{eid}/predict", headers=h, json={"rows": [row, row]})
        assert p.status_code == 200 and len(p.json()["predictions"]) == 2, p.text
        pf = await c.post(f"/api/experiments/{eid}/predict-file", headers=h, data={"fmt": "csv"}, files={"file": ("n.csv", b"alcohol,proline\n13,1000\n12,500\n", "text/csv")})
        assert pf.status_code == 200 and "prediction" in pf.text.splitlines()[0]
        assert len((await c.get(f"/api/experiments/{eid}/models/{tid}/download", headers=h)).content) > 100
        assert "joblib.load" in (await c.get(f"/api/experiments/{eid}/script", headers=h)).text
        assert (await c.get(f"/api/experiments/{eid}/models/{tid}/download", headers=other)).status_code == 404

        tok = (await c.post(f"/api/experiments/{eid}/share", headers=h, json={"enabled": True})).json()["share_token"]
        pub = await c.get(f"/api/public/experiments/{tok}")
        assert pub.status_code == 200 and "features" not in pub.json()["result"]
        await c.post(f"/api/experiments/{eid}/share", headers=h, json={"enabled": False})
        assert (await c.get(f"/api/public/experiments/{tok}")).status_code == 404

        assert (await c.delete(f"/api/datasets/{did}", headers=other)).status_code == 404
        assert (await c.delete(f"/api/experiments/{eid}", headers=h)).status_code == 200
        assert (await c.delete(f"/api/datasets/{did}", headers=h)).status_code == 200


async def test_bad_data_is_reported_not_crashed():
    async with await client() as c:
        h = await signup(c, "bad@example.com")
        r = await c.post("/api/datasets", headers=h, files={"file": ("tiny.csv", b"a,b\n1,2\n", "text/csv")})
        assert r.status_code == 400 and "30 rows" in r.json()["detail"]


def _token_from_outbox(mailer, kind):
    import re
    for m in reversed(mailer.OUTBOX):
        found = re.search(r"#/" + kind + r"\?token=([A-Za-z0-9_\-\.]+)", m["text"])
        if found:
            return found.group(1)
    return None


async def test_email_verification_and_password_reset():
    from app.studio import mailer
    from app.studio.settings import settings
    settings.email_provider = "console"
    try:
        async with await client() as c:
            h = await signup(c, "mail@example.com")
            me = (await c.get("/api/me", headers=h)).json()
            assert me["email_enabled"] is True and me["user"]["email_verified"] is False
            tok = _token_from_outbox(mailer, "verify")
            assert tok
            assert (await c.post("/api/auth/verify", json={"token": "garbage"})).status_code == 400
            assert (await c.post("/api/auth/verify", json={"token": tok})).status_code == 200
            assert (await c.get("/api/me", headers=h)).json()["user"]["email_verified"] is True

            assert (await c.post("/api/auth/forgot", json={"email": "nobody@example.com"})).json() == {"ok": True}       # no account leak
            assert (await c.post("/api/auth/forgot", json={"email": "mail@example.com"})).status_code == 200
            rt = _token_from_outbox(mailer, "reset")
            assert rt
            assert (await c.post("/api/auth/reset", json={"token": rt, "new_password": "short"})).status_code == 400
            ok = await c.post("/api/auth/reset", json={"token": rt, "new_password": "brand-New_phrase-99"})
            assert ok.status_code == 200 and ok.json()["token"]
            assert (await c.post("/api/auth/reset", json={"token": rt, "new_password": "another-New_phrase-1"})).status_code == 400   # single use
            assert (await c.get("/api/me", headers=h)).status_code == 401                                                                # old sessions revoked
            assert (await c.post("/api/auth/login", json={"email": "mail@example.com", "password": "brand-New_phrase-99"})).status_code == 200
    finally:
        settings.email_provider = ""


async def test_api_keys_exclude_columns_export_and_admin():
    from app.studio.settings import settings
    settings.admin_emails.add("boss@example.com")
    async with await client() as c:
        h = await signup(c, "dev@example.com")
        boss = await signup(c, "boss@example.com")
        up = await c.post("/api/datasets", headers=h, data={"name": "Wine"}, files={"file": ("wine.csv", wine_csv(), "text/csv")})
        did = up.json()["id"]
        assert (await c.get(f"/api/datasets/{did}/download", headers=h)).text.startswith("alcohol")
        body = {"dataset_id": did, "name": "x", "target": "target", "families": ["tree"], "generations": 1, "population": 4, "time_limit_s": 20,
                "exclude": ["proline", "not_a_column"]}
        ex = await c.post("/api/experiments", headers=h, json=body)
        assert ex.status_code == 201 and ex.json()["config"]["exclude"] == ["proline"]
        eid = ex.json()["id"]
        for _ in range(180):
            d = (await c.get(f"/api/experiments/{eid}", headers=h)).json()
            if d["status"] in ("done", "failed"):
                break
            await anyio.sleep(0.5)
        assert d["status"] == "done" and all(f["name"] != "proline" for f in d["result"]["features"])
        assert d["result"]["diagnostics"]["kind"] == "confusion" and any(t["ci_low"] is not None for t in d["trials"])

        k = await c.post("/api/me/keys", headers=h, json={"name": "my app"})
        assert k.status_code == 201
        key = k.json()["key"]
        kh = {"Authorization": "Bearer " + key}
        row = {"alcohol": 13.0, "malic_acid": 2.0}
        assert (await c.post(f"/api/experiments/{eid}/predict", headers=kh, json={"rows": [row]})).status_code == 200
        assert (await c.get(f"/api/experiments/{eid}", headers=kh)).status_code == 200
        assert (await c.get("/api/me", headers=kh)).status_code == 403                   # keys are scoped
        assert (await c.delete(f"/api/experiments/{eid}", headers=kh)).status_code == 403
        assert (await c.post("/api/me/keys", headers=kh, json={"name": "evil"})).status_code == 403
        listed = (await c.get("/api/me/keys", headers=h)).json()["keys"]
        assert listed and "key" not in listed[0]
        assert (await c.delete(f"/api/me/keys/{listed[0]['id']}", headers=h)).status_code == 200
        assert (await c.post(f"/api/experiments/{eid}/predict", headers=kh, json={"rows": [row]})).status_code == 401   # revoked

        exp = await c.get("/api/me/export", headers=h)
        assert exp.status_code == 200 and exp.json()["datasets"] and exp.json()["user"]["email"] == "dev@example.com"

        assert (await c.get("/api/admin/users", headers=h)).status_code == 403
        users = (await c.get("/api/admin/users", headers=boss)).json()["users"]
        dev = next(u for u in users if u["email"] == "dev@example.com")
        assert (await c.post(f"/api/admin/users/{dev['id']}/active", headers=boss, json={"active": False})).status_code == 200
        assert (await c.get("/api/me", headers=h)).status_code == 401                    # deactivated user is signed out
        assert (await c.post("/api/auth/login", json={"email": "dev@example.com", "password": "a-Good_pass-phrase-42"})).status_code == 401
