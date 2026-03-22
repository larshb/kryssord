"""
Norsk Kryssordløser — backend
Step 1: /api/lookup and DELETE /api/cache. No frontend yet.

Run with:
    uvicorn main:app --reload
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import urllib.error

from kryssord import KryssordOrg
from cache import Cache

app = FastAPI(title="Kryssordløser")

scraper = KryssordOrg()
cache = Cache("cache/lookups")

# ---------------------------------------------------------------------------
# Static files (Step 2+). The static/ dir may not exist yet during Step 1 —
# only mount it when it exists so the backend still starts cleanly.
# ---------------------------------------------------------------------------
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", include_in_schema=False)
    def root():
        from fastapi.responses import FileResponse
        return FileResponse("static/index.html")


# ---------------------------------------------------------------------------
# GET /api/lookup
# ---------------------------------------------------------------------------
@app.get("/api/lookup")
def lookup(
    a: str = Query(default="", description="Clue text (ledetekst). Required."),
    b: str = Query(default="", description="Pattern string, e.g. kr?ss?rd. Optional."),
):
    """
    Look up matching words on kryssord.org.

    - a: clue (required). If empty but b is present, b is promoted to a (pattern-as-clue).
    - b: pattern using ? (one unknown char) or * (any chars, manual use only).
    """
    # Promote b → a if a is empty (pattern-only search)
    if not a.strip() and b.strip():
        a, b = b.strip(), ""

    # Both empty → reject
    if not a.strip():
        raise HTTPException(status_code=400, detail="Ledetekst (a) er påkrevd")

    # Check cache first
    cached_result = cache.get(a, b)
    if cached_result is not None:
        return JSONResponse({**cached_result, "cached": True})

    # Fetch from kryssord.org
    try:
        result = scraper.search(a=a, b=b)
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Oppslag feilet: {exc.reason}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Oppslag feilet: {exc}")

    # Flatten to the response shape the frontend expects
    response = {
        "words": result["results"]["words"],
        "total": result["results"]["total"],
        "query": result["query"],
        "cached": False,
    }

    cache.set(a, b, response)
    return JSONResponse(response)


# ---------------------------------------------------------------------------
# DELETE /api/cache  — clear the lookup cache ("Tøm hurtigbuffer")
# ---------------------------------------------------------------------------
@app.delete("/api/cache")
def clear_cache():
    """Clear all cached lookups."""
    cleared = cache.clear()
    return {"ok": True, "cleared": cleared}


# ---------------------------------------------------------------------------
# GET /api/cache/stats  — handy during development
# ---------------------------------------------------------------------------
@app.get("/api/cache/stats")
def cache_stats():
    return {"entries": cache.size()}
