from fastapi import Depends

ONLINE_USERS = {}


def register_online_status_module(app, deps):
    get_current_user = deps["get_current_user"]
    online_users = deps.get("online_users", ONLINE_USERS)

    @app.post("/online")
    def update_online(data: dict, current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id")
        if user_id:
            online_users[str(user_id)] = {
                "userId": user_id,
                "userName": current_user.get("name", ""),
                "userRole": current_user.get("role", ""),
                "lastSeen": data.get("lastSeen", ""),
                "page": data.get("page", ""),
            }
        return {"ok": True}

    @app.get("/online")
    def get_online(_current_user: dict = Depends(get_current_user)):
        return list(online_users.values())
