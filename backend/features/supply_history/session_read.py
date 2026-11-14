"""Cookie-session lookup that can stay read-only.

Ordinary requests still refresh last_seen_at. A read-only screen, such as
procurement history, passes touch_session=False and must not write.
"""

SESSION_SELECT_SQL = """SELECT u.*, s.id AS auth_session_id, s.two_factor_passed AS auth_session_two_factor_passed
           FROM user_sessions s
           JOIN users u ON u.id=s.user_id
           WHERE s.session_hash=%s
             AND s.revoked_at IS NULL
             AND s.expires_at>NOW()
           LIMIT 1"""

LAST_SEEN_UPDATE_SQL = "UPDATE user_sessions SET last_seen_at=NOW() WHERE id=%s"


def load_cookie_session_user(cur, conn, session_hash: str, *, touch_session: bool, enrich=None):
    if not touch_session:
        cur.execute("SET TRANSACTION READ ONLY")
    cur.execute(SESSION_SELECT_SQL, (session_hash,))
    user = cur.fetchone()
    if user and touch_session:
        cur.execute(LAST_SEEN_UPDATE_SQL, (user.get("auth_session_id"),))
        conn.commit()
    if user and enrich is not None:
        user = enrich(cur, user)
    return user
