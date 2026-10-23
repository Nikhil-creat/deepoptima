from app.llm.model_discovery import _best

def test_prefers_stable_and_newer():
    ids = ["gemini-2.0-flash", "gemini-2.5-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    assert _best(ids, "flash", exclude="lite") == "gemini-2.5-flash"

def test_groq_deep_pick():
    ids = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    assert _best(ids, r"(70b|versatile)") == "llama-3.3-70b-versatile"
