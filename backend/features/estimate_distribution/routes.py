from typing import Optional

from fastapi import Depends, Header, HTTPException

try:
    from backend.features.brigade_lineage.snapshot_service import (
        LineageResolutionError,
        SnapshotItemCoordinate,
    )
    from backend.features.brigade_lineage.writer_service import (
        LineageWriteConflict,
        load_existing_estimate_contract_items,
    )
    from backend.features.brigade_lineage.source_item import (
        estimate_item_unit_price,
        is_estimate_work_item,
        number,
    )
except ModuleNotFoundError:
    from features.brigade_lineage.snapshot_service import (
        LineageResolutionError,
        SnapshotItemCoordinate,
    )
    from features.brigade_lineage.writer_service import (
        LineageWriteConflict,
        load_existing_estimate_contract_items,
    )
    from features.brigade_lineage.source_item import (
        estimate_item_unit_price,
        is_estimate_work_item,
        number,
    )


def _text(value, limit=255):
    return str(value or "").strip()[:limit]


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _contract_identity(contractor_user_id, brigade_name):
    if contractor_user_id:
        return "COALESCE(contractor_id,0)=%s", contractor_user_id
    return "LOWER(TRIM(COALESCE(brigade_name,'')))=LOWER(TRIM(%s))", brigade_name


def register_estimate_distribution_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_estimate_mutation_actor = deps["resolve_estimate_mutation_actor"]
    resolve_brigade_contractor_user = deps["resolve_brigade_contractor_user"]
    grant_brigade_contractor_scope = deps["grant_brigade_contractor_scope"]
    ensure_estimate_snapshot_lineages = deps["ensure_estimate_snapshot_lineages"]
    write_estimate_contract_item = deps["write_estimate_contract_item"]
    assign_roles = tuple(deps.get("assign_roles") or ())
    project_scoped_roles = tuple(deps.get("project_scoped_roles") or ())
    package_required_roles = tuple(deps.get("package_required_roles") or ())

    @app.post("/estimates/{estimate_id}/distribute")
    def distribute_estimate_to_brigades(
        estimate_id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        data = data or {}
        raw_assignments = data.get("assignments") or []
        if not isinstance(raw_assignments, list) or not raw_assignments:
            raise HTTPException(status_code=400, detail="Нет распределений")
        assignments = []
        for assignment in raw_assignments:
            if not isinstance(assignment, dict):
                raise HTTPException(status_code=400, detail="Некорректная строка распределения")
            if _text(assignment.get("brigadeName")):
                assignments.append(assignment)
        if not assignments:
            raise HTTPException(status_code=400, detail="Нет рабочих позиций для распределения")
        raw_default_coefficient = data.get("defaultCoefficient")
        default_coefficient = number(1 if raw_default_coefficient in (None, "") else raw_default_coefficient)
        if default_coefficient <= 0:
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
            project_id = _positive_int(estimate_scope.get("projectId"))
            if not project_id:
                raise HTTPException(status_code=409, detail="Смета не привязана к точному объекту выбранной компании")

            coordinates = [
                SnapshotItemCoordinate(
                    assignment.get("sectionIndex"),
                    assignment.get("itemIndex"),
                    assignment.get("estimateItemKey", assignment.get("estimate_item_key")),
                )
                for assignment in assignments
            ]
            try:
                lineages = ensure_estimate_snapshot_lineages(
                    cur,
                    estimate_id=estimate_id,
                    company_id=company_id,
                    project_id=project_id,
                    coordinates=coordinates,
                    created_by=actor.get("name") or current_user.get("name") or "",
                )
            except (LineageResolutionError, ValueError) as exc:
                code = getattr(exc, "code", "source_coordinate_invalid")
                status_code = 409 if code.startswith("snapshot_") or code == "estimate_owner_mismatch" else 400
                raise HTTPException(status_code=status_code, detail="Не удалось подтвердить точную строку версии сметы")

            cur.execute(
                """SELECT id,name,project_id,project_name,COALESCE(NULLIF(work_package,''),'Основная')
                   FROM estimates WHERE id=%s AND company_id=%s""",
                (estimate_id, company_id),
            )
            estimate = cur.fetchone()
            if not estimate:
                raise HTTPException(status_code=404, detail="Смета не найдена")
            estimate_name = estimate[1] or ""
            if _positive_int(estimate[2]) != project_id:
                raise HTTPException(status_code=409, detail="Смета не привязана к точному объекту выбранной компании")
            project_name = estimate_scope.get("projectName") or estimate[3] or ""
            work_package = estimate_scope.get("workPackage") or estimate[4] or "Основная"

            groups = {}
            pricelist_ids = set()
            for assignment, lineage in zip(assignments, lineages):
                assigned_package = _text(
                    assignment.get("workPackage") or assignment.get("work_package") or work_package,
                    255,
                ) or "Основная"
                if assigned_package != work_package:
                    raise HTTPException(status_code=400, detail="Пакет строки распределения не совпадает с пакетом сметы")
                if not is_estimate_work_item(lineage.item):
                    continue
                quantity = number(lineage.item.get("quantity"))
                price_smeta = estimate_item_unit_price(lineage.item)
                if quantity <= 0:
                    raise HTTPException(status_code=400, detail="В сметной строке нулевой объем: " + _text(lineage.item.get("name"), 120))
                if price_smeta <= 0:
                    raise HTTPException(status_code=400, detail="В сметной строке нет цены: " + _text(lineage.item.get("name"), 120))

                brigade_name = _text(assignment.get("brigadeName"), 255)
                contractor_id = _positive_int(assignment.get("contractorId"))
                pricelist_id = _positive_int(assignment.get("pricelistId"))
                if assignment.get("pricelistId") not in (None, "") and not pricelist_id:
                    raise HTTPException(status_code=400, detail="Некорректный прайс-лист бригады")
                group_key = (contractor_id or 0, brigade_name.lower())
                group = groups.get(group_key)
                group_metadata = (
                    _text(assignment.get("contractorType") or "Своя бригада", 100),
                    pricelist_id,
                )
                if group and group["metadata"] != group_metadata:
                    raise HTTPException(status_code=400, detail="Для одной бригады указаны разные параметры договора")
                if not group:
                    group = {
                        "brigadeName": brigade_name,
                        "contractorId": contractor_id,
                        "contractorType": group_metadata[0],
                        "pricelistId": pricelist_id,
                        "metadata": group_metadata,
                        "items": [],
                    }
                    groups[group_key] = group
                group["items"].append((assignment, lineage, quantity, price_smeta))
                if pricelist_id:
                    pricelist_ids.add(pricelist_id)
            if not groups:
                raise HTTPException(status_code=400, detail="Нет рабочих позиций для распределения")

            coefficients = {}
            if pricelist_ids:
                cur.execute(
                    "SELECT id, coefficient FROM pricelists WHERE id = ANY(%s)",
                    (sorted(pricelist_ids),),
                )
                coefficients = {int(row[0]): number(row[1]) for row in cur.fetchall()}
                if set(coefficients) != pricelist_ids or any(value <= 0 for value in coefficients.values()):
                    raise HTTPException(status_code=400, detail="Прайс-лист бригады не найден или содержит неверный коэффициент")

            created_contracts = []
            total_inserted = 0
            total_reused = 0
            for group in groups.values():
                contractor_user_id = resolve_brigade_contractor_user(
                    cur,
                    company_id,
                    group["contractorId"],
                    group["brigadeName"],
                )
                identity_sql, identity_param = _contract_identity(contractor_user_id, group["brigadeName"])
                cur.execute(
                    f"""SELECT id FROM brigade_contracts
                        WHERE company_id=%s
                          AND project_id=%s
                          AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                          AND COALESCE(status,'') NOT IN ('Аннулирован','Удалён','Удален')
                          AND {identity_sql}
                        ORDER BY id DESC LIMIT 1 FOR UPDATE""",
                    (company_id, project_id, work_package, identity_param),
                )
                contract = cur.fetchone()
                created = not bool(contract)
                if contract:
                    contract_id = contract[0]
                    cur.execute(
                        """UPDATE brigade_contracts
                           SET brigade_name=%s,contractor_type=%s,contractor_id=COALESCE(%s,contractor_id),
                               pricelist_id=COALESCE(%s,pricelist_id)
                           WHERE id=%s AND company_id=%s AND project_id=%s RETURNING id""",
                        (
                            group["brigadeName"], group["contractorType"], contractor_user_id,
                            group["pricelistId"], contract_id, company_id, project_id,
                        ),
                    )
                    if not cur.fetchone():
                        raise HTTPException(status_code=409, detail="Договор изменился. Обновите страницу")
                else:
                    cur.execute(
                        """INSERT INTO brigade_contracts
                             (company_id,project_id,project_name,work_package,brigade_name,contractor_type,
                              contractor_id,total_amount,status,notes,pricelist_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (
                            company_id, project_id, project_name, work_package, group["brigadeName"],
                            group["contractorType"], contractor_user_id, 0, "Черновик",
                            "Создан из сметы: " + estimate_name, group["pricelistId"],
                        ),
                    )
                    contract_id = cur.fetchone()[0]

                coefficient = coefficients.get(group["pricelistId"], default_coefficient)
                inserted = 0
                reused = 0
                assigned_total = 0.0
                try:
                    existing_items = load_existing_estimate_contract_items(
                        cur,
                        contract_id=contract_id,
                        lineages=[item[1] for item in group["items"]],
                    )
                except LineageWriteConflict:
                    raise HTTPException(status_code=409, detail="Для источника найдено несколько договорных позиций")
                for _assignment, lineage, quantity, price_smeta in group["items"]:
                    price_brigade = round(price_smeta * coefficient, 2)
                    try:
                        written = write_estimate_contract_item(
                            cur,
                            contract_id=contract_id,
                            work_package=work_package,
                            lineage=lineage,
                            section_name=_text(lineage.section.get("name"), 500),
                            name=_text(lineage.item.get("name") or lineage.item.get("description"), 500),
                            unit=_text(lineage.item.get("unit") or "шт", 80),
                            quantity=quantity,
                            price_smeta=price_smeta,
                            price_brigade=price_brigade,
                            existing_items=existing_items,
                        )
                    except LineageWriteConflict:
                        raise HTTPException(status_code=409, detail="Сохранённая строка назначения имеет несовместимый ключ источника")
                    except ValueError:
                        raise HTTPException(status_code=409, detail="Сметная строка содержит некорректные данные для назначения")
                    if written["inserted"]:
                        inserted += 1
                    else:
                        reused += 1
                    assigned_total += written["quantity"] * written["priceBrigade"]

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
                total_inserted += inserted
                total_reused += reused
                created_contracts.append({
                    "id": contract_id,
                    "brigadeName": group["brigadeName"],
                    "contractorId": contractor_user_id,
                    "totalAmount": round(assigned_total, 2),
                    "itemsCount": len(group["items"]),
                    "created": created,
                    "inserted": inserted,
                    "reused": reused,
                })

            conn.commit()
            return {
                "ok": True,
                "createdContracts": created_contracts,
                "inserted": total_inserted,
                "reused": total_reused,
                "companyId": company_id,
                "projectId": project_id,
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=500, detail="Не удалось распределить работы по бригадам")
        finally:
            cur.close()
            conn.close()
