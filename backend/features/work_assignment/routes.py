import math
from typing import Optional

from fastapi import Depends, Header, HTTPException

try:
    from backend.features.brigade_lineage.snapshot_service import (
        LineageResolutionError,
        SnapshotItemCoordinate,
    )
except ModuleNotFoundError:
    from features.brigade_lineage.snapshot_service import (
        LineageResolutionError,
        SnapshotItemCoordinate,
    )

try:
    from backend.features.brigade_lineage.writer_service import (
        LineageWriteConflict,
        load_existing_estimate_contract_items,
        write_estimate_contract_item,
    )
except ModuleNotFoundError:
    from features.brigade_lineage.writer_service import (
        LineageWriteConflict,
        load_existing_estimate_contract_items,
        write_estimate_contract_item,
    )

try:
    from backend.features.brigade_lineage.source_item import (
        estimate_item_unit_price,
        is_estimate_work_item,
        number,
    )
except ModuleNotFoundError:
    from features.brigade_lineage.source_item import (
        estimate_item_unit_price,
        is_estimate_work_item,
        number,
    )


def _text(value, limit=255):
    return str(value or "").strip()[:limit]


def _contract_match_sql(contractor_user_id):
    if contractor_user_id:
        return "COALESCE(contractor_id,0)=%s", [contractor_user_id]
    return "LOWER(TRIM(COALESCE(brigade_name,'')))=LOWER(TRIM(%s))", []


def register_work_assignment_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_estimate_mutation_actor = deps["resolve_estimate_mutation_actor"]
    resolve_brigade_contractor_user = deps["resolve_brigade_contractor_user"]
    grant_brigade_contractor_scope = deps["grant_brigade_contractor_scope"]
    ensure_estimate_snapshot_lineages = deps["ensure_estimate_snapshot_lineages"]
    log_audit = deps.get("log_audit")
    assign_roles = deps.get("assign_roles") or ()
    project_scoped_roles = deps.get("project_scoped_roles") or ()
    package_required_roles = deps.get("package_required_roles") or ()

    @app.post("/estimates/{estimate_id}/work-assignment")
    def assign_estimate_work(
        estimate_id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
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
        coefficient_value = data.get("coefficient")
        coefficient = number(0.6 if coefficient_value in (None, "") else coefficient_value)
        if price_mode == "coefficient" and coefficient <= 0:
            raise HTTPException(status_code=400, detail="Коэффициент должен быть больше нуля")

        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            actor, estimate_scope = resolve_estimate_mutation_actor(
                conn,
                current_user,
                estimate_id,
                assign_roles,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_id = int(estimate_scope["companyId"])
            project_id = estimate_scope.get("projectId")
            if not project_id:
                raise HTTPException(status_code=409, detail="Смета не привязана к точному объекту выбранной компании")
            coordinates = []
            for assignment in assignments:
                if not isinstance(assignment, dict):
                    raise HTTPException(status_code=400, detail="Некорректная строка назначения")
                coordinates.append(SnapshotItemCoordinate(
                    assignment.get("sectionIndex"),
                    assignment.get("itemIndex"),
                    assignment.get("estimateItemKey", assignment.get("estimate_item_key")),
                ))
            try:
                lineages = ensure_estimate_snapshot_lineages(
                    cur,
                    estimate_id=estimate_id,
                    company_id=company_id,
                    project_id=int(project_id),
                    coordinates=coordinates,
                    created_by=actor.get("name") or current_user.get("name") or "",
                )
            except (LineageResolutionError, ValueError) as exc:
                code = getattr(exc, "code", "source_coordinate_invalid")
                status_code = 409 if code.startswith("snapshot_") or code == "estimate_owner_mismatch" else 400
                raise HTTPException(status_code=status_code, detail="Не удалось подтвердить точную строку версии сметы")
            cur.execute(
                """SELECT id, name, project_id, project_name, COALESCE(NULLIF(work_package,''),'Основная'), sections_json, status
                   FROM estimates WHERE id=%s AND company_id=%s""",
                (estimate_id, company_id),
            )
            estimate = cur.fetchone()
            if not estimate:
                raise HTTPException(status_code=404, detail="Смета не найдена")
            estimate_name = estimate[1] or ""
            stored_project_id = estimate[2]
            if not stored_project_id or int(stored_project_id) != int(project_id):
                raise HTTPException(status_code=409, detail="Смета не привязана к точному объекту выбранной компании")
            project_name = estimate_scope.get("projectName") or estimate[3] or ""
            work_package = estimate_scope.get("workPackage") or estimate[4] or "Основная"
            contractor_user_id = resolve_brigade_contractor_user(
                cur,
                company_id,
                contractor_id,
                brigade_name,
            )

            match_sql, match_params = _contract_match_sql(contractor_user_id)
            if contractor_user_id:
                match_params = [contractor_user_id]
            else:
                match_params = [brigade_name]
            cur.execute(
                f"""SELECT id FROM brigade_contracts
                    WHERE company_id=%s
                      AND project_id=%s
                      AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                      AND COALESCE(status,'') NOT IN ('Аннулирован','Удалён','Удален')
                      AND {match_sql}
                    ORDER BY id DESC LIMIT 1 FOR UPDATE""",
                tuple([company_id, project_id, work_package] + match_params),
            )
            row = cur.fetchone()
            created_contract = False
            if row:
                contract_id = row[0]
                cur.execute(
                    """UPDATE brigade_contracts
                       SET brigade_name=%s, contractor_type=%s, contractor_id=COALESCE(%s, contractor_id)
                       WHERE id=%s AND company_id=%s AND project_id=%s
                       RETURNING id""",
                    (brigade_name, contractor_type, contractor_user_id, contract_id, company_id, project_id),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=409, detail="Договор изменился. Обновите страницу")
            else:
                cur.execute(
                    """INSERT INTO brigade_contracts
                         (company_id, project_id, project_name, work_package, brigade_name, contractor_type,
                          contractor_id, total_amount, status, notes, pricelist_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                    (
                        company_id,
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
            reused = 0
            result_items = []
            try:
                existing_items = load_existing_estimate_contract_items(
                    cur,
                    contract_id=contract_id,
                    lineages=lineages,
                )
            except LineageWriteConflict:
                raise HTTPException(status_code=409, detail="Для источника найдено несколько договорных позиций")
            for assignment, lineage in zip(assignments, lineages):
                section = lineage.section
                item = lineage.item
                estimate_item_key = lineage.source_item_key
                if not is_estimate_work_item(item):
                    continue
                qty = number(item.get("quantity"))
                if qty <= 0:
                    raise HTTPException(status_code=400, detail="В работе нулевой объем: " + _text(item.get("name"), 120))
                price_smeta = estimate_item_unit_price(item)
                if price_smeta <= 0:
                    raise HTTPException(status_code=400, detail="В работе нет цены сметы: " + _text(item.get("name"), 120))
                row_mode = _text(assignment.get("priceMode") or price_mode, 40)
                row_coefficient_value = assignment.get("coefficient")
                row_coefficient = number(
                    coefficient if row_coefficient_value in (None, "") else row_coefficient_value
                )
                manual_price = number(assignment.get("manualPrice") or assignment.get("priceBrigade"))
                if row_mode == "coefficient" and row_coefficient <= 0:
                    raise HTTPException(status_code=400, detail="Коэффициент должен быть больше нуля")
                price_brigade = manual_price if row_mode == "manual" else round(price_smeta * row_coefficient, 2)
                if not math.isfinite(price_brigade) or price_brigade <= 0:
                    raise HTTPException(status_code=400, detail="Цена исполнителю должна быть больше нуля: " + _text(item.get("name"), 120))
                section_name = _text(section.get("name"), 500)
                item_name = _text(item.get("name") or item.get("description"), 500)
                unit = _text(item.get("unit") or "шт", 80)
                try:
                    written = write_estimate_contract_item(
                        cur,
                        contract_id=contract_id,
                        work_package=work_package,
                        lineage=lineage,
                        section_name=section_name,
                        name=item_name,
                        unit=unit,
                        quantity=qty,
                        price_smeta=price_smeta,
                        price_brigade=price_brigade,
                        existing_items=existing_items,
                    )
                except LineageWriteConflict:
                    raise HTTPException(status_code=409, detail="Сохранённая строка назначения имеет несовместимый ключ источника")
                item_id = written["id"]
                section_name = written["section"]
                item_name = written["name"]
                unit = written["unit"]
                qty = written["quantity"]
                price_smeta = written["priceSmeta"]
                price_brigade = written["priceBrigade"]
                estimate_item_key = written["estimateItemKey"]
                if written["inserted"]:
                    inserted += 1
                else:
                    reused += 1
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
                   WHERE id=%s AND company_id=%s AND project_id=%s""",
                (contract_id, contract_id, company_id, project_id),
            )
            grant_brigade_contractor_scope(
                cur,
                company_id,
                contractor_user_id,
                project_name,
                work_package,
                project_scoped_roles=project_scoped_roles,
                package_required_roles=package_required_roles,
            )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=500, detail="Не удалось назначить работы")
        finally:
            cur.close()
            conn.close()
        if log_audit:
            log_audit(
                current_user.get("name") or "",
                actor.get("role") or current_user.get("role") or "",
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
            "reused": reused,
            "brigadeName": brigade_name,
            "contractorId": contractor_user_id,
            "projectName": project_name,
            "workPackage": work_package,
            "companyId": company_id,
            "projectId": project_id,
            "items": result_items,
        }
