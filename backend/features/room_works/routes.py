"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import psycopg2

def register_room_works_module(app, deps):
    JOURNAL_WRITE_ROLES = deps['JOURNAL_WRITE_ROLES']
    PACKAGE_LIMIT_ROLES = deps['PACKAGE_LIMIT_ROLES']
    PLATFORM_STAFF_ROLES = deps['PLATFORM_STAFF_ROLES']
    PROJECT_DOCUMENT_ROLES = deps['PROJECT_DOCUMENT_ROLES']
    PROJECT_WRITE_ROLES = deps['PROJECT_WRITE_ROLES']
    WORKER_EXECUTION_ROLES = deps['WORKER_EXECUTION_ROLES']
    _positive_int_or_none = deps['_positive_int_or_none']
    _raise_work_journal_duplicate = deps['_raise_work_journal_duplicate']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    _room_work_duplicate = deps['_room_work_duplicate']
    _row_get = deps['_row_get']
    _run_project_ai_control_safely = deps['_run_project_ai_control_safely']
    effective_company_actors = deps['effective_company_actors']
    get_db = deps['get_db']
    has_package_access = deps['has_package_access']
    require_roles = deps['require_roles']
    require_work_journal_actor_access = deps['require_work_journal_actor_access']
    user_package_names = deps['user_package_names']
    router = APIRouter()

    class RoomWorkModel(BaseModel):
        roomId: int
        project: str
        projectId: Optional[int] = None
        roomName: str
        masterId: int
        masterName: str
        description: str
        surface: str = ""
        unit: str = "м2"
        quantity: float = 0
        pricePerUnit: float = 0
        total: float = 0
        date: str = ""
        photoUrl: str = ""
        workJournalId: Optional[int] = None
        workPackage: str = ""
        estimateItemKey: str = ""

    def _room_work_scope():
        try:
            from backend.features.room_ownership.access import FULL_COMPANY_VIEW_ROLES, RoomOwnership
        except ModuleNotFoundError:
            from features.room_ownership.access import FULL_COMPANY_VIEW_ROLES, RoomOwnership
        return RoomOwnership(
            _resolve_work_company_context,
            effective_company_actors,
            full_view_roles=FULL_COMPANY_VIEW_ROLES,
            platform_staff_roles=PLATFORM_STAFF_ROLES,
            read_roles=PROJECT_DOCUMENT_ROLES,
            write_roles=JOURNAL_WRITE_ROLES,
        )

    @router.get("/room-works")
    def get_room_works(current_user: dict = Depends(require_roles(*PROJECT_DOCUMENT_ROLES, *PLATFORM_STAFF_ROLES)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            scope = _room_work_scope()
            actors, mode = scope.actors(cur, current_user, request, write=False, roles=PROJECT_DOCUMENT_ROLES)
            role_user = actors[0] if mode == "company" and len(actors) == 1 else current_user
            role = role_user.get("role")
            package_names = user_package_names(role_user) if role in PACKAGE_LIMIT_ROLES else []
            if role in PACKAGE_LIMIT_ROLES and role != "прораб" and not package_names:
                return []
            join, where, params = scope.list_clause(actors, mode, "r")
            conditions = [where]
            params = list(params)
            if role in WORKER_EXECUTION_ROLES:
                conditions.append("(COALESCE(r.master_id,0)=%s OR (COALESCE(r.master_id,0)=0 AND LOWER(TRIM(r.master_name))=LOWER(TRIM(%s))))")
                params.extend([role_user.get("id"), role_user.get("name") or ""])
            if role in PACKAGE_LIMIT_ROLES and package_names:
                conditions.append("COALESCE(NULLIF(r.work_package,''),'Основная') = ANY(%s)")
                params.append(package_names)
            cur.execute(
                """SELECT r.id,r.room_id as \"roomId\",r.project,r.room_name as \"roomName\",r.master_id as \"masterId\",r.master_name as \"masterName\",r.description,r.surface,r.unit,r.quantity,r.price_per_unit as \"pricePerUnit\",r.total,r.date,r.status,r.photo_url as \"photoUrl\",r.confirmed_by as \"confirmedBy\",r.work_journal_id as \"workJournalId\",r.work_package as \"workPackage\",r.estimate_item_key as \"estimateItemKey\",r.company_id as \"companyId\",r.project_id as \"projectId\"
                   FROM room_works r """ + join + " WHERE " + " AND ".join(conditions) + " ORDER BY r.id DESC",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        result = [dict(r) for r in rows]
        if role in WORKER_EXECUTION_ROLES:
            for row in result:
                row["pricePerUnit"] = 0
                row["total"] = 0
        return result

    @router.post("/room-works")
    def create_room_work(w: RoomWorkModel, _current_user: dict = Depends(require_roles(*JOURNAL_WRITE_ROLES)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            scope = _room_work_scope()
            actors, mode = scope.actors(cur, _current_user, request, write=True, roles=JOURNAL_WRITE_ROLES)
            actor = actors[0]
            parent = scope.verified_project(cur, actor, w)
            role = actor.get("role")
            if role in PACKAGE_LIMIT_ROLES and not has_package_access(actor, w.workPackage or "Основная"):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ")
            if role in WORKER_EXECUTION_ROLES:
                if not w.workJournalId:
                    raise HTTPException(status_code=403, detail="Работа по помещению создаётся только через ЖПР")
                own_id = str(actor.get("id") or "")
                own_name = (actor.get("name") or "").strip().lower()
                if str(w.masterId or "") != own_id and (w.masterName or "").strip().lower() != own_name:
                    raise HTTPException(status_code=403, detail="Мастер может создавать только свои работы по помещениям")
            if w.workJournalId:
                work = require_work_journal_actor_access(cur, w.workJournalId, actor)
                cur.execute("SELECT company_id FROM work_journal WHERE id=%s", (w.workJournalId,))
                journal_company = _positive_int_or_none(_row_get(cur.fetchone(), "company_id", 0))
                if journal_company != parent["companyId"] or (work.get("project") or "") != parent["name"]:
                    raise HTTPException(status_code=400, detail="ЖПР относится к другому объекту")
            _raise_work_journal_duplicate(_room_work_duplicate(
                cur,
                parent["name"],
                room_id=w.roomId,
                room_name=w.roomName,
                estimate_item_key=w.estimateItemKey,
                description=w.description,
                work_package=w.workPackage,
                exclude_work_journal_id=w.workJournalId,
                company_id=parent["companyId"],
            ))
            cur.execute("""INSERT INTO room_works
                           (room_id,project,room_name,master_id,master_name,description,surface,unit,quantity,price_per_unit,total,date,photo_url,work_journal_id,work_package,estimate_item_key,company_id,project_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                        (w.roomId, parent["name"], w.roomName, w.masterId, w.masterName, w.description, w.surface, w.unit, w.quantity, w.pricePerUnit, w.total, w.date, w.photoUrl, w.workJournalId, w.workPackage, w.estimateItemKey, parent["companyId"], parent["id"]))
            row = dict(cur.fetchone())
            project_name = parent["name"]
        finally:
            conn.close()
        _run_project_ai_control_safely(project_name, "room_work:create")
        return row

    @router.put("/room-works/{id}")
    def update_room_work(id: int, data: dict, _current_user: dict = Depends(require_roles(*PROJECT_WRITE_ROLES, "технадзор", "стройконтроль")), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            scope = _room_work_scope()
            actors, mode = scope.actors(cur, _current_user, request, write=True, roles=(*PROJECT_WRITE_ROLES, "технадзор", "стройконтроль"))
            owner = scope.mutable_row(cur, "room_works", id, actors, mode)
            project_name = owner["name"]
            if 'status' in data:
                cur.execute("UPDATE room_works SET status=%s,confirmed_by=%s WHERE id=%s AND company_id=%s",
                            (data['status'], data.get('confirmedBy', ''), id, owner["companyId"]))
        finally:
            conn.close()
        _run_project_ai_control_safely(project_name, "room_work:update")
        return {"ok": True}

    app.include_router(router)

