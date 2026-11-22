"""Routes moved verbatim from backend/main.py."""

import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import psycopg2

def register_material_norms_module(app, deps):
    LEADERSHIP_ROLES = deps['LEADERSHIP_ROLES']
    PROJECT_DOCUMENT_ROLES = deps['PROJECT_DOCUMENT_ROLES']
    _norm_list = deps['_norm_list']
    get_db = deps['get_db']
    limit_offset_sql = deps['limit_offset_sql']
    require_project_access = deps['require_project_access']
    require_roles = deps['require_roles']
    visible_project_names = deps['visible_project_names']
    router = APIRouter()

    class MaterialNormModel(BaseModel):
        ruleKey: str = ""
        name: str = ""
        work: List[str] = []
        blockWork: List[str] = []
        material: List[str] = []
        workUnit: str = "м2"
        materialUnit: str = "кг"
        qtyPerUnit: float = 0
        thicknessBaseMm: Optional[float] = None
        defaultThicknessMm: Optional[float] = None
        label: str = ""
        active: bool = True

    class MaterialNormOverrideModel(BaseModel):
        baseNormId: Optional[int] = None
        projectName: str = ""
        estimateId: Optional[int] = None
        sectionName: str = ""
        workName: str = ""
        materialName: str = ""
        work: List[str] = []
        blockWork: List[str] = []
        material: List[str] = []
        workUnit: str = "м2"
        materialUnit: str = "кг"
        qtyPerUnit: float = 0
        thicknessBaseMm: Optional[float] = None
        defaultThicknessMm: Optional[float] = None
        label: str = ""
        reason: str = ""
        active: bool = True

    def _material_norm_row(row):
        return {
            "id": row["id"],
            "ruleKey": row["rule_key"] or "",
            "name": row["name"] or "",
            "work": _norm_list(row["work_keywords"]),
            "blockWork": _norm_list(row["block_work_keywords"]),
            "material": _norm_list(row["material_keywords"]),
            "workUnit": row["work_unit"] or "",
            "materialUnit": row["material_unit"] or "",
            "qtyPerUnit": float(row["qty_per_unit"] or 0),
            "thicknessBaseMm": float(row["thickness_base_mm"]) if row["thickness_base_mm"] is not None else None,
            "defaultThicknessMm": float(row["default_thickness_mm"]) if row["default_thickness_mm"] is not None else None,
            "label": row["label"] or "",
            "active": bool(row["active"]),
            "updatedBy": row["updated_by"] or "",
            "updatedAt": str(row["updated_at"]) if row["updated_at"] else "",
        }

    def _material_norm_values(data: MaterialNormModel, user_name: str):
        rule_key = (data.ruleKey or "").strip() or ("custom_" + uuid.uuid4().hex[:8])
        return (
            rule_key,
            data.name.strip() or rule_key,
            json.dumps(_norm_list(data.work), ensure_ascii=False),
            json.dumps(_norm_list(data.blockWork), ensure_ascii=False),
            json.dumps(_norm_list(data.material), ensure_ascii=False),
            data.workUnit or "м2",
            data.materialUnit or "кг",
            data.qtyPerUnit or 0,
            data.thicknessBaseMm,
            data.defaultThicknessMm,
            data.label.strip(),
            bool(data.active),
            user_name or "",
        )

    def _material_norm_override_row(row):
        return {
            "id": row["id"],
            "baseNormId": row["base_norm_id"],
            "projectName": row["project_name"] or "",
            "estimateId": row["estimate_id"],
            "sectionName": row["section_name"] or "",
            "workName": row["work_name"] or "",
            "materialName": row["material_name"] or "",
            "work": _norm_list(row["work_keywords"]),
            "blockWork": _norm_list(row["block_work_keywords"]),
            "material": _norm_list(row["material_keywords"]),
            "workUnit": row["work_unit"] or "",
            "materialUnit": row["material_unit"] or "",
            "qtyPerUnit": float(row["qty_per_unit"] or 0),
            "thicknessBaseMm": float(row["thickness_base_mm"]) if row["thickness_base_mm"] is not None else None,
            "defaultThicknessMm": float(row["default_thickness_mm"]) if row["default_thickness_mm"] is not None else None,
            "label": row["label"] or "",
            "reason": row["reason"] or "",
            "active": bool(row["active"]),
            "updatedBy": row["updated_by"] or "",
            "updatedAt": str(row["updated_at"]) if row["updated_at"] else "",
        }

    def _material_norm_override_values(data: MaterialNormOverrideModel, user_name: str):
        return (
            data.baseNormId,
            (data.projectName or "").strip(),
            data.estimateId,
            (data.sectionName or "").strip(),
            (data.workName or "").strip(),
            (data.materialName or "").strip(),
            json.dumps(_norm_list(data.work), ensure_ascii=False),
            json.dumps(_norm_list(data.blockWork), ensure_ascii=False),
            json.dumps(_norm_list(data.material), ensure_ascii=False),
            data.workUnit or "м2",
            data.materialUnit or "кг",
            data.qtyPerUnit or 0,
            data.thicknessBaseMm,
            data.defaultThicknessMm,
            (data.label or "").strip(),
            (data.reason or "").strip(),
            bool(data.active),
            user_name or "",
        )

    @router.get("/material-norms")
    def list_material_norms(
        search: str = "",
        limit: Optional[int] = None,
        offset: int = 0,
        _current_user: dict = Depends(require_roles(*PROJECT_DOCUMENT_ROLES)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where = ["active=TRUE"]
        params = []
        search_value = (search or "").strip()
        if search_value:
            where.append("""(
                COALESCE(rule_key, '') ILIKE %s OR
                COALESCE(name, '') ILIKE %s OR
                COALESCE(label, '') ILIKE %s OR
                COALESCE(array_to_string(work_keywords, ' '), '') ILIKE %s OR
                COALESCE(array_to_string(material_keywords, ' '), '') ILIKE %s
            )""")
            params.extend([f"%{search_value}%"] * 5)
        page_sql, page_params = limit_offset_sql(limit, offset)
        cur.execute("""SELECT id, rule_key, name, work_keywords, block_work_keywords, material_keywords,
                              work_unit, material_unit, qty_per_unit, thickness_base_mm,
                              default_thickness_mm, label, active, updated_by, updated_at
                       FROM material_norms
                       WHERE """ + " AND ".join(where) + """
                       ORDER BY name, id""" + page_sql, params + page_params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [_material_norm_row(r) for r in rows]

    @router.post("/material-norms")
    def create_material_norm(data: MaterialNormModel, current_user: dict = Depends(require_roles(*LEADERSHIP_ROLES, "прораб", "главный_инженер", "сметчик"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        vals = _material_norm_values(data, current_user.get("name", ""))
        try:
            cur.execute("""
                INSERT INTO material_norms (
                    rule_key, name, work_keywords, block_work_keywords, material_keywords,
                    work_unit, material_unit, qty_per_unit, thickness_base_mm,
                    default_thickness_mm, label, active, updated_by, updated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                RETURNING id, rule_key, name, work_keywords, block_work_keywords, material_keywords,
                          work_unit, material_unit, qty_per_unit, thickness_base_mm,
                          default_thickness_mm, label, active, updated_by, updated_at
            """, vals)
        except psycopg2.errors.UniqueViolation:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Код нормы уже используется")
        row = cur.fetchone()
        cur.close(); conn.close()
        return _material_norm_row(row)

    @router.get("/material-norms/overrides")
    def list_material_norm_overrides(project_name: str = None, estimate_id: int = None, current_user: dict = Depends(require_roles(*PROJECT_DOCUMENT_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where = ["active=TRUE"]
        params = []
        if project_name:
            require_project_access(current_user, project_name)
            where.append("project_name=%s")
            params.append(project_name)
        else:
            allowed = visible_project_names(current_user)
            if allowed is not None:
                if not allowed:
                    cur.close(); conn.close()
                    return []
                where.append("project_name = ANY(%s)")
                params.append(allowed)
        if estimate_id:
            where.append("estimate_id=%s")
            params.append(estimate_id)
        cur.execute(f"""SELECT * FROM material_norm_overrides
                        WHERE {' AND '.join(where)}
                        ORDER BY updated_at DESC, id DESC""", tuple(params))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [_material_norm_override_row(r) for r in rows]

    @router.post("/material-norms/overrides")
    def create_material_norm_override(data: MaterialNormOverrideModel, current_user: dict = Depends(require_roles(*LEADERSHIP_ROLES, "прораб", "главный_инженер", "сметчик"))):
        project_name = (data.projectName or "").strip()
        if not project_name:
            raise HTTPException(status_code=400, detail="Укажите объект для поправки нормы")
        require_project_access(current_user, project_name)
        if (data.qtyPerUnit or 0) <= 0:
            raise HTTPException(status_code=400, detail="Расход должен быть больше 0")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        vals = _material_norm_override_values(data, current_user.get("name", ""))
        cur.execute("""
            INSERT INTO material_norm_overrides (
                base_norm_id, project_name, estimate_id, section_name, work_name, material_name,
                work_keywords, block_work_keywords, material_keywords, work_unit, material_unit,
                qty_per_unit, thickness_base_mm, default_thickness_mm, label, reason, active,
                updated_by, updated_at, created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            RETURNING *
        """, vals)
        row = cur.fetchone()
        cur.close(); conn.close()
        return _material_norm_override_row(row)

    @router.put("/material-norms/overrides/{id}")
    def update_material_norm_override(id: int, data: MaterialNormOverrideModel, current_user: dict = Depends(require_roles(*LEADERSHIP_ROLES, "прораб", "главный_инженер", "сметчик"))):
        project_name = (data.projectName or "").strip()
        if not project_name:
            raise HTTPException(status_code=400, detail="Укажите объект для поправки нормы")
        require_project_access(current_user, project_name)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        vals = _material_norm_override_values(data, current_user.get("name", ""))
        cur.execute("""
            UPDATE material_norm_overrides
            SET base_norm_id=%s, project_name=%s, estimate_id=%s, section_name=%s,
                work_name=%s, material_name=%s, work_keywords=%s, block_work_keywords=%s,
                material_keywords=%s, work_unit=%s, material_unit=%s, qty_per_unit=%s,
                thickness_base_mm=%s, default_thickness_mm=%s, label=%s, reason=%s,
                active=%s, updated_by=%s, updated_at=NOW()
            WHERE id=%s
            RETURNING *
        """, vals + (id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Поправка нормы не найдена")
        return _material_norm_override_row(row)

    @router.delete("/material-norms/overrides/{id}")
    def delete_material_norm_override(id: int, current_user: dict = Depends(require_roles(*LEADERSHIP_ROLES, "прораб", "главный_инженер", "сметчик"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT project_name FROM material_norm_overrides WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Поправка нормы не найдена")
        require_project_access(current_user, row["project_name"] or "")
        cur.execute("UPDATE material_norm_overrides SET active=FALSE, updated_by=%s, updated_at=NOW() WHERE id=%s", (current_user.get("name", ""), id))
        cur.close(); conn.close()
        return {"ok": True}

    @router.put("/material-norms/{id}")
    def update_material_norm(id: int, data: MaterialNormModel, current_user: dict = Depends(require_roles(*LEADERSHIP_ROLES, "прораб", "главный_инженер", "сметчик"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        vals = _material_norm_values(data, current_user.get("name", ""))
        cur.execute("""
            UPDATE material_norms
            SET rule_key=%s, name=%s, work_keywords=%s, block_work_keywords=%s,
                material_keywords=%s, work_unit=%s, material_unit=%s, qty_per_unit=%s,
                thickness_base_mm=%s, default_thickness_mm=%s, label=%s, active=%s,
                updated_by=%s, updated_at=NOW()
            WHERE id=%s
            RETURNING id, rule_key, name, work_keywords, block_work_keywords, material_keywords,
                      work_unit, material_unit, qty_per_unit, thickness_base_mm,
                      default_thickness_mm, label, active, updated_by, updated_at
        """, vals + (id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Норма не найдена")
        return _material_norm_row(row)

    @router.delete("/material-norms/{id}")
    def delete_material_norm(id: int, current_user: dict = Depends(require_roles(*LEADERSHIP_ROLES, "прораб", "главный_инженер", "сметчик"))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE material_norms SET active=FALSE, updated_by=%s, updated_at=NOW() WHERE id=%s", (current_user.get("name", ""), id))
        affected = cur.rowcount
        cur.close(); conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Норма не найдена")
        return {"ok": True}

    app.include_router(router)

