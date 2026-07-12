import psycopg2.extras


def run_project_ai_control_safely(
    get_db,
    resolve_project_owner,
    run_project_ai_control,
    system_actor_for_project,
    project_name,
    reason="event",
    *,
    log_error=print,
):
    if not str(project_name or "").strip():
        return {}
    conn = None
    cur = None
    try:
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        project = resolve_project_owner(cur, project_name, for_update=True)
        result = run_project_ai_control(
            cur,
            project["name"],
            system_actor_for_project(project),
            reason=reason,
            project_owner=project,
        )
        conn.commit()
        return result
    except Exception as exc:
        if conn:
            conn.rollback()
        log_error("AI CONTROL AUTO-RUN ERROR:", project_name, reason, str(exc))
        return {}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
