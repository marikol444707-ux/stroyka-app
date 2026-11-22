"""Routes moved verbatim from backend/main.py."""

import time
from fastapi import APIRouter

def register_health_module(app, deps):
    _app_version = deps['_app_version']
    _utc_now_iso = deps['_utc_now_iso']
    get_db = deps['get_db']
    router = APIRouter()

    @router.get("/health")
    def health():
        started = time.time()
        db = {"ok": False}
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close(); conn.close()
            db = {"ok": True, "latencyMs": round((time.time() - started) * 1000, 1)}
        except Exception as e:
            db = {"ok": False, "error": e.__class__.__name__}
        return {
            "ok": db["ok"],
            "status": "ok" if db["ok"] else "degraded",
            "service": "stroyka-backend",
            "time": _utc_now_iso(),
            "version": _app_version(),
            "db": db,
        }

    app.include_router(router)

