"""Online presence routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 1):
POST /online and GET /online keep their URLs and payloads; the
in-memory presence dict lives here because nothing else reads it.
"""

from fastapi import Depends

online_users = {}


def register_online_presence_module(app, deps):
    get_current_user = deps["get_current_user"]

    @app.post("/online")
    def update_online(data: dict, current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        if user_id:
            online_users[str(user_id)] = {
                "userId": user_id,
                "userName": current_user.get("name",""),
                "userRole": current_user.get("role",""),
                "lastSeen": data.get("lastSeen",""),
                "page": data.get("page","")
            }
        return {"ok": True}

    @app.get("/online")
    def get_online(_current_user: dict = Depends(get_current_user)):
        import time
        now = time.time()
        # Возвращаем пользователей активных за последние 2 минуты
        return list(online_users.values())
