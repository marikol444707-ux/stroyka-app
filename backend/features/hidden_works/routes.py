"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Request
import psycopg2

def register_hidden_works_module(app, deps):
    FINANCE_ROLES = deps['FINANCE_ROLES']
    JOURNAL_WRITE_ROLES = deps['JOURNAL_WRITE_ROLES']
    ModelGatewayError = deps['ModelGatewayError']
    PACKAGE_LIMIT_ROLES = deps['PACKAGE_LIMIT_ROLES']
    PROJECT_DOCUMENT_CONTENT_WRITE_ROLES = deps['PROJECT_DOCUMENT_CONTENT_WRITE_ROLES']
    PROJECT_DOCUMENT_WRITE_ROLES = deps['PROJECT_DOCUMENT_WRITE_ROLES']
    WORKER_EXECUTION_ROLES = deps['WORKER_EXECUTION_ROLES']
    YANDEX_API_KEY = deps['YANDEX_API_KEY']
    YANDEX_FOLDER_ID = deps['YANDEX_FOLDER_ID']
    _lock_legacy_work_settlement = deps['_lock_legacy_work_settlement']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    effective_company_actors = deps['effective_company_actors']
    generate_yandex_text = deps['generate_yandex_text']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    hidden_act_internal_actor = deps['hidden_act_internal_actor']
    hidden_work_effective_status = deps['hidden_work_effective_status']
    log_audit = deps['log_audit']
    package_access_filter = deps['package_access_filter']
    project_record_scope = deps['project_record_scope']
    require_hidden_work_actor_access = deps['require_hidden_work_actor_access']
    require_row_project_access = deps['require_row_project_access']
    save_doc_version = deps['save_doc_version']
    visible_project_names = deps['visible_project_names']
    work_acceptance_records = deps['work_acceptance_records']
    router = APIRouter()

    @router.get("/hidden-works-acts")
    def list_hidden_works_acts(project_name: str = None, current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as context_cur:
                context = _resolve_work_company_context(context_cur, current_user, None, 'read',
                    x_company_id=request.headers.get('x-company-id') if request else None,
                    x_company_mode=request.headers.get('x-company-mode') if request else None)
                actors = effective_company_actors(current_user, context)
                actors = [a for a in actors if a.get('role') != 'заказчик']
                if len(actors) != 1:
                    raise HTTPException(403, 'Выберите компанию с правами на внутренние акты')
                current_user = actors[0]
        except Exception:
            conn.close()
            raise
        cur = conn.cursor()
        owner_sql = 'company_id=%s'
        owner_params = [current_user.get('companyId') or current_user.get('company_id')]
        cols = """id, project_name, estimate_id, act_number, work_name, section_name, brigade,
                  quantity, unit, price_per_unit, total, work_date, status,
                  signed_customer, signed_supervisor, signed_contractor, signed_subcontractor,
                  signed_customer_at, signed_supervisor_at, signed_contractor_at, signed_subcontractor_at,
                  conclusion, comments, materials_used, project_docs,
                  photos, certificates, city, ai_filled,
                  paid_status, paid_amount, paid_at, paid_by, paid_note,
                  work_journal_id, COALESCE(NULLIF(work_package,''),'Основная') AS work_package, created_at"""
        allowed_projects = visible_project_names(current_user)
        role = current_user.get("role")
        if role not in ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик", "прораб", "стройконтроль", "технадзор", "заказчик", *WORKER_EXECUTION_ROLES):
            cur.close(); conn.close()
            return []
        if project_name:
            if allowed_projects is not None and project_name not in allowed_projects:
                cur.close(); conn.close()
                return []
            package_sql, package_params = package_access_filter(current_user, "work_package")
            cur.execute(f"SELECT {cols} FROM hidden_works_acts WHERE {owner_sql} AND project_name=%s{package_sql} ORDER BY id DESC", owner_params + [project_name] + package_params)
        elif allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            package_sql, package_params = package_access_filter(current_user, "work_package")
            cur.execute(f"SELECT {cols} FROM hidden_works_acts WHERE {owner_sql} AND project_name = ANY(%s){package_sql} ORDER BY id DESC", owner_params + [allowed_projects] + package_params)
        else:
            cur.execute(f"SELECT {cols} FROM hidden_works_acts WHERE {owner_sql} ORDER BY id DESC", owner_params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        result = []
        actor_name_key = (current_user.get("name") or "").strip().lower()
        for r in rows:
            signed_customer = r[13] or ""
            signed_supervisor = r[14] or ""
            signed_contractor = r[15] or ""
            signed_subcontractor = r[16] or ""
            if role in WORKER_EXECUTION_ROLES:
                own_names = {
                    str(r[6] or "").strip().lower(),
                    str(signed_contractor or "").strip().lower(),
                    str(signed_subcontractor or "").strip().lower(),
                }
                if actor_name_key not in own_names:
                    continue
            price_per_unit = 0 if role in WORKER_EXECUTION_ROLES else float(r[9] or 0)
            total = 0 if role in WORKER_EXECUTION_ROLES else float(r[10] or 0)
            paid_amount = 0 if role in WORKER_EXECUTION_ROLES else float(r[30] or 0)
            result.append({"id":r[0],"projectName":r[1],"estimateId":r[2],"actNumber":r[3],"workName":r[4],
                 "sectionName":r[5],"workPackage":r[35] or "Основная","brigade":r[6],"quantity":float(r[7] or 0),"unit":r[8],
                 "pricePerUnit":price_per_unit,"total":total,"workDate":str(r[11]) if r[11] else "",
                 "status":hidden_work_effective_status(r[12], signed_customer, signed_supervisor, signed_contractor, signed_subcontractor),
                 "signedCustomer":signed_customer,"signedSupervisor":signed_supervisor,
                 "signedContractor":signed_contractor,"signedSubcontractor":signed_subcontractor,
                 "signedCustomerAt":str(r[17]) if r[17] else "","signedSupervisorAt":str(r[18]) if r[18] else "",
                 "signedContractorAt":str(r[19]) if r[19] else "","signedSubcontractorAt":str(r[20]) if r[20] else "",
                 "conclusion":r[21] or "","comments":r[22] or "",
                 "materialsUsed":r[23] or "","projectDocs":r[24] or "",
                 "photos":r[25] or "","certificates":r[26] or "","city":r[27] or "",
                 "aiFilled":bool(r[28]),
                 "paidStatus":"" if role in WORKER_EXECUTION_ROLES else (r[29] or "Не оплачен"),"paidAmount":paid_amount,
                 "paidAt":"" if role in WORKER_EXECUTION_ROLES else (str(r[31]) if r[31] else ""),"paidBy":"" if role in WORKER_EXECUTION_ROLES else (r[32] or ""),"paidNote":"" if role in WORKER_EXECUTION_ROLES else (r[33] or ""),
                 "workJournalId":r[34],
                 "createdAt":str(r[36])})
        return result

    @router.put("/hidden-works-acts/{act_id}")
    def update_hidden_works_act(act_id: int, data: dict, _current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            _lock_legacy_work_settlement(cur)
            try:
                _current_user = hidden_act_internal_actor(cur, project_record_scope, _current_user, request, act_id, (*PROJECT_DOCUMENT_CONTENT_WRITE_ROLES, *WORKER_EXECUTION_ROLES))
            except Exception:
                cur.close(); conn.close()
                raise
            require_row_project_access(cur, "hidden_works_acts", act_id, _current_user, "project_name")
            if _current_user.get("role") in PACKAGE_LIMIT_ROLES:
                require_hidden_work_actor_access(cur, act_id, _current_user)
            if _current_user.get("role") in WORKER_EXECUTION_ROLES:
                cur.execute("""SELECT brigade, signed_customer, signed_supervisor, signed_contractor, signed_subcontractor,
                                      signed_customer_at, signed_supervisor_at, signed_contractor_at, signed_subcontractor_at,
                                      conclusion, comments, project_docs, materials_used, photos, certificates, city, status
                               FROM hidden_works_acts WHERE id=%s""", (act_id,))
                own_row = cur.fetchone()
                if not own_row:
                    cur.close(); conn.close()
                    raise HTTPException(status_code=404, detail="АОСР не найден")
                actor_key = (_current_user.get("name") or "").strip().lower()
                own_names = {
                    str(own_row[0] or "").strip().lower(),
                    str(own_row[3] or "").strip().lower(),
                    str(own_row[4] or "").strip().lower(),
                }
                if actor_key not in own_names:
                    cur.close(); conn.close()
                    raise HTTPException(status_code=403, detail="Исполнитель может подписывать только свой АОСР")
                data = {
                    "status": own_row[16] or "Черновик",
                    "signedCustomer": own_row[1] or "",
                    "signedSupervisor": own_row[2] or "",
                    "signedContractor": own_row[3] or "",
                    "signedSubcontractor": (_current_user.get("name") or own_row[4] or ""),
                    "signedCustomerAt": own_row[5] or None,
                    "signedSupervisorAt": own_row[6] or None,
                    "signedContractorAt": own_row[7] or None,
                    "signedSubcontractorAt": data.get("signedSubcontractorAt") or __import__("datetime").date.today().isoformat(),
                    "conclusion": own_row[9] or "",
                    "comments": data.get("comments", own_row[10] or ""),
                    "projectDocs": own_row[11] or "",
                    "materialsUsed": own_row[12] or "",
                    "photos": own_row[13] or "",
                    "certificates": own_row[14] or "",
                    "city": own_row[15] or "",
                }
            work_acceptance_records.guard_hidden_act(cur, act_id)
            cur.execute('SELECT signed_customer,signed_customer_at,conclusion,city FROM hidden_works_acts WHERE id=%s', (act_id,))
            confirmed = cur.fetchone()
            if confirmed and confirmed[0]:
                before = (str(confirmed[0]), str(confirmed[1] or ''), confirmed[2] or '', confirmed[3] or '')
                after = (str(data.get('signedCustomer') or ''), str(data.get('signedCustomerAt') or ''),
                         data.get('conclusion') or '', data.get('city') or '')
                if before != after:
                    raise HTTPException(409, 'Нельзя изменять подтверждение заказчика и согласованные условия акта')
            # Снапшот текущего состояния перед изменением (версионирование)
            try:
                cur.execute("SELECT row_to_json(t) FROM hidden_works_acts t WHERE id=%s", (act_id,))
                prev_row = cur.fetchone()
                if prev_row and prev_row[0]:
                    save_doc_version("hidden_works_act", act_id, prev_row[0],
                                     changed_by=data.get("_actor","—"),
                                     change_reason="PUT /hidden-works-acts/"+str(act_id))
            except Exception as e:
                print("VERSION snapshot skipped:", str(e))
            # Подписи помогают контролю, но не являются обязательным стоп-краном.
            sc = data.get("signedCustomer","").strip()
            ss = data.get("signedSupervisor","").strip()
            sk = data.get("signedContractor","").strip()
            sb = data.get("signedSubcontractor","").strip()
            auto_status = hidden_work_effective_status(data.get("status","Черновик"), sc, ss, sk, sb)
            cur.execute("""UPDATE hidden_works_acts SET
                           status=%s,
                           signed_customer=%s, signed_supervisor=%s, signed_contractor=%s, signed_subcontractor=%s,
                           signed_customer_at=%s, signed_supervisor_at=%s, signed_contractor_at=%s, signed_subcontractor_at=%s,
                           conclusion=%s, comments=%s, project_docs=%s, materials_used=%s,
                           photos=%s, certificates=%s, city=%s,
                           ai_filled=FALSE
                           WHERE id=%s""",
                (auto_status,
                 sc, ss, sk, sb,
                 data.get("signedCustomerAt") or None, data.get("signedSupervisorAt") or None,
                 data.get("signedContractorAt") or None, data.get("signedSubcontractorAt") or None,
                 data.get("conclusion",""), data.get("comments",""),
                 data.get("projectDocs",""), data.get("materialsUsed",""),
                 data.get("photos",""), data.get("certificates",""), data.get("city",""),
                 act_id))
            conn.commit(); cur.close(); conn.close()
            log_audit(user_name=data.get("_actor","система"), user_role="—",
                      action="update", entity_type="hidden_works_act", entity_id=act_id,
                      description="Изменён АОСР, статус: "+auto_status, project_name=data.get("_project",""))
            return {"ok": True, "status": auto_status}
        finally:
            if not conn.closed:
                conn.rollback()
                cur.close()
                conn.close()

    @router.post("/hidden-works-acts/{act_id}/pay")
    def pay_hidden_works_act(act_id: int, data: dict, _current_user: dict = Depends(get_current_user), request: Request = None):
        """Отметить оплату в карточке АОСР без влияния на финансы объекта."""
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            try:
                _current_user = hidden_act_internal_actor(cur, project_record_scope, _current_user, request, act_id, FINANCE_ROLES)
            except Exception:
                cur.close(); conn.close()
                raise
            require_row_project_access(cur, "hidden_works_acts", act_id, _current_user, "project_name")
            cur.execute("SELECT project_name, act_number, total FROM hidden_works_acts WHERE id=%s", (act_id,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                raise HTTPException(status_code=404, detail="акт не найден")
            proj, act_no, default_total = row[0] or "", row[1] or "", float(row[2] or 0)
            amount = float(data.get("amount") or default_total)
            paid_by = (data.get("paidBy") or "").strip()
            paid_note = (data.get("paidNote") or "Оплата по АОСР " + act_no).strip()
            paid_at = data.get("paidAt") or __import__("datetime").date.today().isoformat()
            cur.execute("""UPDATE hidden_works_acts
                           SET paid_status='Оплачен', paid_amount=%s, paid_at=%s, paid_by=%s, paid_note=%s
                           WHERE id=%s""",
                        (amount, paid_at, paid_by, paid_note, act_id))
            conn.commit()
            cur.close(); conn.close()
            log_audit(user_name=paid_by or "—", user_role="—",
                      action="pay", entity_type="hidden_works_act", entity_id=act_id,
                      description="Отмечена оплата в карточке АОСР "+act_no+" на сумму "+str(amount)+" ₽",
                      project_name=proj)
            return {"ok": True, "paidStatus": "Оплачен", "paidAmount": amount, "paidAt": paid_at, "financeDetached": True}

        finally:
            if not conn.closed:
                conn.rollback()
                cur.close(); conn.close()

    @router.delete("/hidden-works-acts/{act_id}")
    def delete_hidden_works_act(act_id: int, _current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            try:
                _current_user = hidden_act_internal_actor(cur, project_record_scope, _current_user, request, act_id, PROJECT_DOCUMENT_WRITE_ROLES)
            except Exception:
                cur.close(); conn.close()
                raise
            require_row_project_access(cur, "hidden_works_acts", act_id, _current_user, "project_name")
            cur.execute("UPDATE hidden_works_acts SET status='Аннулирован' WHERE id=%s", (act_id,))
            conn.commit(); cur.close(); conn.close()
            return {"ok": True}

        finally:
            if not conn.closed:
                conn.rollback()
                cur.close(); conn.close()

    @router.post("/hidden-works-acts/{act_id}/ai-prefill")
    def ai_prefill_hidden_works_act(act_id: int, _current_user: dict = Depends(get_current_user), request: Request = None):
        import json as j, re
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            _current_user = hidden_act_internal_actor(cur, project_record_scope, _current_user, request, act_id, JOURNAL_WRITE_ROLES)
            require_hidden_work_actor_access(cur, act_id, _current_user)
            cur.execute("""SELECT work_name, section_name, brigade, materials_used, unit, quantity, project_name
                           FROM hidden_works_acts WHERE id=%s""", (act_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="act not found")
            work_name, section_name, brigade, materials_used, unit, quantity, project_name = row
            cur.execute('SELECT row_to_json(h)::text FROM hidden_works_acts h WHERE id=%s', (act_id,))
            source_snapshot = cur.fetchone()[0]
        finally:
            conn.rollback()
            cur.close(); conn.close()

        user_text = (
            "Работа: " + (work_name or "—") + "\n"
            "Раздел сметы: " + (section_name or "—") + "\n"
            "Бригада: " + (brigade or "—") + "\n"
            "Объём: " + str(quantity or 0) + " " + (unit or "") + "\n"
            "Использованные материалы (если указаны): " + (materials_used or "—") + "\n\n"
            "Верни СТРОГО JSON-объект с тремя полями (без markdown, без тройных кавычек):\n"
            '{"conclusion": "...", "normatives": "...", "projectDocs": "..."}\n'
            "Где:\n"
            "- conclusion: формальная формулировка заключения комиссии о качестве работ "
            "со ссылкой на нормативы и проектные документы; разрешение на производство последующих работ; "
            "официальный канцелярский русский, 2-4 предложения.\n"
            "- normatives: перечень применимых СНиП/СП/ГОСТ через запятую (только реально применимые к этому виду работ).\n"
            "- projectDocs: перечень типовых проектных документов (разделы, листы), к которым относится эта работа."
        )

        instructions = "Ты отвечаешь СТРОГО валидным JSON. Никакого markdown, никаких тройных кавычек, никакого текста до или после JSON. Только сам JSON."
        try:
            answer = generate_yandex_text(
                capability="hidden_works_act_prefill",
                instructions=instructions,
                input_text=user_text,
                temperature=0.1,
                max_output_tokens=2000,
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
        except ModelGatewayError as error:
            raise HTTPException(status_code=502, detail="AI не ответил: " + error.code)
        text = answer.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
        try:
            parsed = j.loads(text)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=502, detail="AI вернул невалидный JSON: " + str(e)[:200])

        conclusion = (parsed.get("conclusion") or "").strip()
        normatives = (parsed.get("normatives") or "").strip()
        project_docs = (parsed.get("projectDocs") or "").strip()

        if normatives:
            full_conclusion = "Применимые нормативные документы: " + normatives + "\n\n" + conclusion
        else:
            full_conclusion = conclusion

        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            _lock_legacy_work_settlement(cur)
            hidden_act_internal_actor(cur, project_record_scope, _current_user, request, act_id, JOURNAL_WRITE_ROLES)
            work_acceptance_records.guard_hidden_act(cur, act_id)
            cur.execute('SELECT row_to_json(h)::text FROM hidden_works_acts h WHERE id=%s', (act_id,))
            if cur.fetchone()[0] != source_snapshot:
                raise HTTPException(409, 'Акт изменился во время подготовки текста. Обновите его и повторите запрос')
            cur.execute('SELECT signed_customer FROM hidden_works_acts WHERE id=%s', (act_id,))
            if cur.fetchone()[0]:
                raise HTTPException(409, 'Подтверждённый заказчиком акт нельзя заполнять заново')
            cur.execute("""UPDATE hidden_works_acts
                           SET conclusion=%s, project_docs=%s, ai_filled=TRUE
                           WHERE id=%s""", (full_conclusion, project_docs, act_id))
            conn.commit()
        finally:
            conn.rollback()
            cur.close(); conn.close()
        return {"ok": True, "conclusion": full_conclusion, "projectDocs": project_docs, "normatives": normatives, "aiFilled": True}

    app.include_router(router)

