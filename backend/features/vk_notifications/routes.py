"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException

def register_vk_notifications_module(app, deps):
    VK_TOKEN = deps['VK_TOKEN']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    router = APIRouter()

    def send_vk_notification(vk_user_id: int, message: str):
        import requests
        if not VK_TOKEN:
            print("VK notify skipped: VK_TOKEN is not configured")
            return
        try:
            requests.post("https://api.vk.com/method/messages.send", params={
                "user_id": vk_user_id,
                "message": message,
                "random_id": 0,
                "access_token": VK_TOKEN,
                "v": "5.131"
            }, timeout=5)
        except Exception as e:
            print("VK error:", e)

    @router.post("/vk-connect")
    def vk_connect(data: dict, current_user: dict = Depends(get_current_user)):
        if data.get("email") and data.get("email") != current_user.get("email"):
            raise HTTPException(status_code=403, detail="Можно подключить только свой VK")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS vk_id INTEGER")
        cur.execute("UPDATE users SET vk_id=%s WHERE email=%s", (data.get("vkId"), data.get("email")))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}

    @router.post("/vk-notify")
    def vk_notify(data: dict, _current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT vk_id FROM users WHERE id=%s", (data.get("userId"),))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0]:
            send_vk_notification(row[0], data.get("message",""))
        return {"ok": True}

    app.include_router(router)

