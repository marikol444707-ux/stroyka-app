"""Selected-company scope for rooms, openings, works and measurements.

Company users only see rows whose company_id and project_id point at a project
of a company they belong to. Rows left unowned by the backfill are invisible to
them. Platform staff can read those unowned rows and cannot claim them here.
"""
from collections.abc import Mapping

from fastapi import HTTPException

from ..project_access.service import (
    project_visibility_filter,
    require_project_parent_access,
    require_project_write_actor,
    resolve_project_parent,
)


FULL_COMPANY_VIEW_ROLES = (
    "директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик",
)
NAMED_TABLES = {
    "rooms": "project",
    "room_works": "project",
    "project_measurements": "project_name",
    "measurement_room_drafts": "project_name",
    "room_windows": None,
    "room_doors": None,
}
_ALIASES = {"r", "w", "d", "m"}
_UNOWNED_MUTATION = (
    "Запись не привязана к компании. Её нельзя изменить, пока владелец "
    "не назначен отдельным проверенным переносом."
)


def _positive(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def header_value(request, name):
    headers = getattr(request, "headers", None) or {}
    target = str(name or "").lower()
    items = headers.items() if hasattr(headers, "items") else ()
    for key, value in items:
        if str(key).lower() == target and value not in (None, ""):
            return value
    return None


def _mapping(cur, row):
    if row is None:
        return None
    if isinstance(row, Mapping):
        return dict(row)
    columns = [column[0] for column in (getattr(cur, "description", None) or [])]
    if columns and len(columns) == len(row):
        return dict(zip(columns, row))
    raise TypeError("Owner query returned a row without column names")


def _check_alias(alias):
    if alias not in _ALIASES:
        raise ValueError("Invalid room ownership alias")
    return alias


def project_fields(data):
    """Read a project reference from a dict or a request model. Ignore companyId."""
    if hasattr(data, "model_dump"):
        payload = data.model_dump()
    elif hasattr(data, "dict"):
        payload = data.dict()
    elif isinstance(data, Mapping):
        payload = dict(data)
    else:
        payload = {
            "projectId": getattr(data, "projectId", None),
            "project": getattr(data, "project", None),
            "projectName": getattr(data, "projectName", None),
        }
    project_id = None
    for key in ("projectId", "project_id"):
        if payload.get(key) not in (None, ""):
            project_id = payload.get(key)
            break
    name = ""
    for key in ("project", "projectName", "project_name"):
        if payload.get(key) not in (None, ""):
            name = payload.get(key)
            break
    return project_id, str(name or "")


class RoomOwnership:
    def __init__(self, resolve_context, effective_actors, *, full_view_roles, platform_staff_roles,
                 read_roles=(), write_roles=()):
        self.resolve_context = resolve_context
        self.effective_actors = effective_actors
        self.full_view_roles = tuple(full_view_roles or ())
        self.platform_staff_roles = tuple(platform_staff_roles or ())
        self.read_roles = tuple(read_roles or ())
        self.write_roles = tuple(write_roles or ())

    def actors(self, cur, user, request, *, write, roles=None):
        allowed = tuple(roles or (self.write_roles if write else self.read_roles))
        role = str((user or {}).get("role") or "")
        company_header = header_value(request, "x-company-id")
        mode_header = str(header_value(request, "x-company-mode") or "").strip().lower()
        if role in self.platform_staff_roles and not write and (not company_header or mode_header == "all_companies"):
            return [{"id": (user or {}).get("id"), "role": role, "platformReview": True}], "platform_unowned"
        context = self.resolve_context(
            cur, user, None, "write" if write else "read",
            x_company_id=company_header, x_company_mode=mode_header or None,
        )
        actors = list(self.effective_actors(user, context) or [])
        if write:
            return [require_project_write_actor(actors, allowed)], "company"
        visible = [actor for actor in actors if actor.get("role") in allowed]
        if not visible:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет читать эти данные")
        return visible, "company"

    def list_clause(self, actors, mode, alias="r"):
        alias = _check_alias(alias)
        if mode == "platform_unowned":
            return "", f"{alias}.company_id IS NULL", []
        where, params = project_visibility_filter(actors, self.full_view_roles, "p")
        join = f"JOIN projects p ON p.id={alias}.project_id AND p.company_id={alias}.company_id"
        return join, where, params

    def verified_project(self, cur, actor, data):
        project_id, name = project_fields(data)
        parent = resolve_project_parent(
            cur, actor, project_id=project_id, project_name=name, for_update=True,
        )
        require_project_parent_access(cur, actor, parent, self.full_view_roles)
        return parent

    def mutable_row(self, cur, table, row_id, actors, mode):
        if table not in NAMED_TABLES:
            raise ValueError("Unsupported owned room table")
        row_id = _positive(row_id)
        if not row_id:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        if mode == "platform_unowned":
            cur.execute(
                f"SELECT id FROM {table} WHERE id=%s AND company_id IS NULL AND project_id IS NULL",
                (row_id,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=_UNOWNED_MUTATION)
            raise HTTPException(status_code=404, detail="Запись не найдена")
        join, where, params = self.list_clause(actors, mode)
        cur.execute(
            f"SELECT r.company_id, r.project_id, p.name AS project_name "
            f"FROM {table} r {join} WHERE r.id=%s AND {where}",
            (row_id, *params),
        )
        row = _mapping(cur, cur.fetchone())
        if not row or not _positive(row.get("company_id")) or not _positive(row.get("project_id")):
            raise HTTPException(status_code=404, detail="Запись не найдена")
        return {
            "companyId": int(row["company_id"]),
            "projectId": int(row["project_id"]),
            "name": str(row.get("project_name") or ""),
        }


def resolve_stored_project_owner(cur, company_id, project_name, project_id=None):
    """Resolve a journal or estimate parent that was already stored for one company."""
    company_id = _positive(company_id)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания работы не определена")
    parent = resolve_project_parent(
        cur,
        {"companyId": company_id, "role": "директор"},
        project_id=project_id,
        project_name=project_name or "",
    )
    return parent
