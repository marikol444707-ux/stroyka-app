import json

from fastapi import Depends, HTTPException


def _text(value, limit=255):
    return str(value or "").strip()[:limit]


def _num(value):
    try:
        return float(str(value if value is not None else 0).replace(" ", "").replace(",", "."))
    except Exception:
        return 0.0


def _json_sections(raw):
    try:
        return json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        return []


def _is_work_item(item):
    raw_type = str((item or {}).get("itemType") or (item or {}).get("type") or (item or {}).get("kind") or "work").lower()
    if any(token in raw_type for token in ("material", "материал", "equipment", "оборуд", "delivery", "доставка", "other", "прочее", "note", "adjustment")):
        return False
    return not (_num((item or {}).get("priceMaterial")) > 0 and _num((item or {}).get("priceWork")) <= 0)


def _item_total(item):
    item = item or {}
    qty = _num(item.get("quantity"))
    for field in ("totalWork", "lineTotal", "currentTotal", "total", "baseTotal", "estimatedCost", "workTotal", "workSum", "amount", "sum"):
        total = _num(item.get(field))
        if abs(total) > 0:
            return total
    return 0


def _unit_price(item):
    for field in (
        "executionPricePerUnit",
        "priceBrigade",
        "masterPricePerUnit",
        "contractorPricePerUnit",
        "executorPricePerUnit",
        "internalPricePerUnit",
        "priceWork",
        "priceSmeta",
        "price",
        "baseUnitPrice",
    ):
        value = _num((item or {}).get(field))
        if value > 0:
            return value
    qty = _num((item or {}).get("quantity"))
    if qty > 0:
        total = _item_total(item)
        if total:
            return round(total / qty, 6)
    return 0


def _item_keys(estimate_id, section_idx, item_idx, item):
    keys = []
    for field in ("estimateItemKey", "estimate_item_key", "itemKey", "workKey", "key", "id", "code", "sourceCode", "obosn"):
        value = _text((item or {}).get(field), 200)
        if value and value not in keys:
            keys.append(value)
    generated = f"{estimate_id}:{section_idx}:{item_idx}"
    if generated not in keys:
        keys.append(generated)
    return keys


def _find_estimate_item(estimate_id, sections, assignment):
    target_key = _text(assignment.get("estimateItemKey") or assignment.get("estimate_item_key"), 200)
    section_index = assignment.get("sectionIndex")
    item_index = assignment.get("itemIndex")
    try:
        section_index = int(section_index)
        item_index = int(item_index)
        section = sections[section_index]
        item = (section.get("items") or [])[item_index]
        return section_index, item_index, section, item, _item_keys(estimate_id, section_index, item_index, item)[0]
    except Exception:
        pass
    target_name = _text(assignment.get("name") or assignment.get("description"), 500).lower()
    target_section = _text(assignment.get("section") or assignment.get("estimateSection"), 500).lower()
    fallback = None
    for si, section in enumerate(sections or []):
        section_name = _text((section or {}).get("name"), 500)
        for ii, item in enumerate((section or {}).get("items") or []):
            keys = _item_keys(estimate_id, si, ii, item)
            name_match = target_name and _text((item or {}).get("name") or (item or {}).get("description"), 500).lower() == target_name
            section_match = not target_section or section_name.lower() == target_section
            if target_key and target_key in keys:
                return si, ii, section, item, target_key
            if name_match and section_match:
                return si, ii, section, item, keys[0]
            if name_match and fallback is None:
                fallback = (si, ii, section, item, keys[0])
    if fallback:
        return fallback
    raise HTTPException(status_code=400, detail="Строка сметы не найдена: " + (_text(assignment.get("name"), 120) or target_key or "без названия"))


def _contract_match_sql(contractor_user_id):
    if contractor_user_id:
        return "COALESCE(contractor_id,0)=%s", [contractor_user_id]
    return "LOWER(TRIM(COALESCE(brigade_name,'')))=LOWER(TRIM(%s))", []


def register_work_assignment_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    require_estimate_access = deps["require_estimate_access"]
    resolve_staff_or_user_id = deps["resolve_staff_or_user_id"]
    grant_user_project_package_access = deps.get("grant_user_project_package_access")
    log_audit = deps.get("log_audit")
    assign_roles = deps.get("assign_roles") or ()
    assign_access = require_roles(*assign_roles)

    @app.post("/estimates/{estimate_id}/work-assignment")
    def assign_estimate_work(estimate_id: int, data: dict, current_user: dict = Depends(assign_access)):
        data = data or {}
        assignee = data.get("assignee") or {}
        brigade_name = _text(assignee.get("brigadeName") or assignee.get("name") or data.get("brigadeName"), 255)
        contractor_type = _text(assignee.get("contractorType") or data.get("contractorType") or "Своя бригада", 100)
        contractor_id = assignee.get("contractorId") or data.get("contractorId")
        if not brigade_name:
            raise HTTPException(status_code=400, detail="Выберите мастера или укажите название бригады")
        assignments = data.get("items") or data.get("assignments") or []
        if not assignments:
            raise HTTPException(status_code=400, detail="Выберите работы для назначения")
        price_mode = _text(data.get("priceMode") or "coefficient", 40)
        coefficient = _num(data.get("coefficient") or 0.6)
        if price_mode == "coefficient" and coefficient <= 0:
            raise HTTPException(status_code=400, detail="Коэффициент должен быть больше нуля")

        conn = get_db()
        cur = conn.cursor()
        try:
            project_name, allowed_package = require_estimate_access(cur, estimate_id, current_user)
            cur.execute(
                """SELECT id, name, project_id, project_name, COALESCE(NULLIF(work_package,''),'Основная'), sections_json, status
                   FROM estimates WHERE id=%s""",
                (estimate_id,),
            )
            estimate = cur.fetchone()
            if not estimate:
                raise HTTPException(status_code=404, detail="Смета не найдена")
            estimate_name = estimate[1] or ""
            project_id = estimate[2]
            project_name = estimate[3] or project_name
            work_package = estimate[4] or allowed_package or "Основная"
            sections = _json_sections(estimate[5])
            contractor_user_id = resolve_staff_or_user_id(cur, contractor_id, brigade_name)

            match_sql, match_params = _contract_match_sql(contractor_user_id)
            if contractor_user_id:
                match_params = [contractor_user_id]
            else:
                match_params = [brigade_name]
            cur.execute(
                f"""SELECT id FROM brigade_contracts
                    WHERE project_name=%s
                      AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                      AND COALESCE(status,'') NOT IN ('Аннулирован','Удалён','Удален')
                      AND {match_sql}
                    ORDER BY id DESC LIMIT 1""",
                tuple([project_name, work_package] + match_params),
            )
            row = cur.fetchone()
            created_contract = False
            if row:
                contract_id = row[0]
                cur.execute(
                    """UPDATE brigade_contracts
                       SET brigade_name=%s, contractor_type=%s, contractor_id=COALESCE(%s, contractor_id)
                       WHERE id=%s""",
                    (brigade_name, contractor_type, contractor_user_id, contract_id),
                )
            else:
                cur.execute(
                    """INSERT INTO brigade_contracts
                         (project_id, project_name, work_package, brigade_name, contractor_type, contractor_id, total_amount, status, notes, pricelist_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                    (
                        project_id or None,
                        project_name,
                        work_package,
                        brigade_name,
                        contractor_type,
                        contractor_user_id or None,
                        0,
                        "Черновик",
                        "Простое назначение работ из сметы: " + estimate_name,
                        None,
                    ),
                )
                contract_id = cur.fetchone()[0]
                created_contract = True

            inserted = 0
            updated = 0
            result_items = []
            for assignment in assignments:
                si, ii, section, item, estimate_item_key = _find_estimate_item(estimate_id, sections, assignment)
                if not _is_work_item(item):
                    continue
                qty = _num(item.get("quantity"))
                if qty <= 0:
                    raise HTTPException(status_code=400, detail="В работе нулевой объем: " + _text(item.get("name"), 120))
                price_smeta = _unit_price(item)
                if price_smeta <= 0:
                    raise HTTPException(status_code=400, detail="В работе нет цены сметы: " + _text(item.get("name"), 120))
                row_mode = _text(assignment.get("priceMode") or price_mode, 40)
                row_coefficient = _num(assignment.get("coefficient") or coefficient)
                manual_price = _num(assignment.get("manualPrice") or assignment.get("priceBrigade"))
                price_brigade = manual_price if row_mode == "manual" else round(price_smeta * row_coefficient, 2)
                if price_brigade <= 0:
                    raise HTTPException(status_code=400, detail="Цена исполнителю должна быть больше нуля: " + _text(item.get("name"), 120))
                section_name = _text(section.get("name"), 500)
                item_name = _text(item.get("name") or item.get("description"), 500)
                unit = _text(item.get("unit") or "шт", 80)
                cur.execute(
                    """SELECT id FROM brigade_contract_items
                       WHERE contract_id=%s
                         AND (
                           (%s<>'' AND COALESCE(estimate_item_key,'')=%s)
                           OR (
                             LOWER(TRIM(COALESCE(description,'')))=LOWER(TRIM(%s))
                             AND LOWER(TRIM(COALESCE(estimate_section,'')))=LOWER(TRIM(%s))
                             AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                           )
                         )
                       LIMIT 1""",
                    (contract_id, estimate_item_key, estimate_item_key, item_name, section_name, work_package),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """UPDATE brigade_contract_items
                           SET estimate_section=%s, description=%s, work_package=%s, estimate_item_key=%s,
                               unit=%s, quantity=%s, price_smeta=%s, price_brigade=%s
                           WHERE id=%s""",
                        (section_name, item_name, work_package, estimate_item_key, unit, qty, price_smeta, price_brigade, existing[0]),
                    )
                    updated += 1
                    item_id = existing[0]
                else:
                    cur.execute(
                        """INSERT INTO brigade_contract_items
                             (contract_id, estimate_section, description, work_package, estimate_item_key, unit, quantity, price_smeta, price_brigade, done_quantity)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id""",
                        (contract_id, section_name, item_name, work_package, estimate_item_key, unit, qty, price_smeta, price_brigade, 0),
                    )
                    item_id = cur.fetchone()[0]
                    inserted += 1
                result_items.append({
                    "id": item_id,
                    "section": section_name,
                    "name": item_name,
                    "unit": unit,
                    "quantity": qty,
                    "priceSmeta": price_smeta,
                    "priceBrigade": price_brigade,
                    "coefficient": round(price_brigade / price_smeta, 4) if price_smeta else 0,
                    "estimateItemKey": estimate_item_key,
                })

            if not result_items:
                raise HTTPException(status_code=400, detail="В выбранных строках нет работ для назначения")

            cur.execute(
                """UPDATE brigade_contracts
                   SET total_amount=COALESCE((
                     SELECT SUM(COALESCE(quantity,0)*COALESCE(price_brigade,0))
                     FROM brigade_contract_items WHERE contract_id=%s
                   ),0)
                   WHERE id=%s""",
                (contract_id, contract_id),
            )
            if contractor_user_id and grant_user_project_package_access:
                grant_user_project_package_access(cur, contractor_user_id, project_name, work_package)
            conn.commit()
        except HTTPException:
            conn.rollback()
            cur.close()
            conn.close()
            raise
        except Exception as exc:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=500, detail="Не удалось назначить работы: " + str(exc))
        cur.close()
        conn.close()
        if log_audit:
            log_audit(
                current_user.get("name") or "",
                current_user.get("role") or "",
                "assign_estimate_work",
                "brigade_contract",
                contract_id,
                "Назначены работы исполнителю " + brigade_name,
                project_name,
            )
        return {
            "ok": True,
            "contractId": contract_id,
            "createdContract": created_contract,
            "inserted": inserted,
            "updated": updated,
            "brigadeName": brigade_name,
            "contractorId": contractor_user_id,
            "projectName": project_name,
            "workPackage": work_package,
            "items": result_items,
        }
