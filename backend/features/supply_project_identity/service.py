"""Resolve a supply request to one exact project inside its company."""

from dataclasses import dataclass
from typing import Optional


MAIN_WAREHOUSE = "Основной склад"


@dataclass(frozen=True)
class SupplyProjectIdentity:
    project_id: Optional[int]
    project_name: str


class SupplyProjectIdentityError(ValueError):
    def __init__(self, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    return row[index] if row is not None and len(row) > index else None


def resolve_supply_project(cur, *, company_id, project_id=None, project_name=""):
    company_id = _positive_int(company_id)
    project_id = _positive_int(project_id)
    project_name = str(project_name or "").strip()
    if not company_id:
        raise SupplyProjectIdentityError("Компания заявки не определена")
    if not project_name:
        raise SupplyProjectIdentityError(
            "Заявка снабжения должна быть привязана к объекту или складу",
            status_code=400,
        )
    if project_name == MAIN_WAREHOUSE:
        if project_id:
            raise SupplyProjectIdentityError(
                "Для основного склада projectId не используется"
            )
        return SupplyProjectIdentity(None, MAIN_WAREHOUSE)

    if project_id:
        cur.execute(
            "SELECT id,company_id,name,COALESCE(archived,FALSE) AS archived "
            "FROM projects WHERE id=%s AND company_id=%s",
            (project_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            raise SupplyProjectIdentityError(
                "Объект не найден в выбранной компании", status_code=404
            )
        stored_name = str(_row_value(row, "name", 2) or "").strip()
        if stored_name != project_name:
            raise SupplyProjectIdentityError(
                "projectId и название объекта указывают на разные записи"
            )
        if bool(_row_value(row, "archived", 3)):
            raise SupplyProjectIdentityError("Нельзя создать заявку для архивного объекта")
        return SupplyProjectIdentity(project_id, stored_name)

    cur.execute(
        "SELECT id,company_id,name,COALESCE(archived,FALSE) AS archived "
        "FROM projects WHERE company_id=%s AND BTRIM(name)=BTRIM(%s) ORDER BY id",
        (company_id, project_name),
    )
    rows = list(cur.fetchall() or [])
    active = [row for row in rows if not bool(_row_value(row, "archived", 3))]
    if not active:
        raise SupplyProjectIdentityError(
            "Объект не найден в выбранной компании", status_code=404
        )
    if len(active) != 1:
        raise SupplyProjectIdentityError(
            "В выбранной компании несколько объектов с таким названием. Выберите точный объект заново"
        )
    row = active[0]
    return SupplyProjectIdentity(
        _positive_int(_row_value(row, "id", 0)),
        str(_row_value(row, "name", 2) or "").strip(),
    )
