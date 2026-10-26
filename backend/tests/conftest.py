import os, tempfile
_db = os.path.join(tempfile.gettempdir(), "studio_test.db")
if os.path.exists(_db):
    os.remove(_db)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db}"
os.environ["JWT_SECRET"] = "test-secret-not-for-production"
os.environ["DISABLE_RATE_LIMITS"] = "1"
os.environ["MAX_CONCURRENT_JOBS"] = "1"
