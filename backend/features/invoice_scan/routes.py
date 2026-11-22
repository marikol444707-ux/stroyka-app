"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import psycopg2

def register_invoice_scan_module(app, deps):
    ModelGatewayError = deps['ModelGatewayError']
    ModelInputPart = deps['ModelInputPart']
    PHYSICAL_RECEIPT_ROLES = deps['PHYSICAL_RECEIPT_ROLES']
    YANDEX_API_KEY = deps['YANDEX_API_KEY']
    YANDEX_FOLDER_ID = deps['YANDEX_FOLDER_ID']
    _find_supplier_invoice_template = deps['_find_supplier_invoice_template']
    _invoice_scan_ai_content = deps['_invoice_scan_ai_content']
    _invoice_scan_json_format = deps['_invoice_scan_json_format']
    _normalize_invoice_totals_payload = deps['_normalize_invoice_totals_payload']
    _parse_ai_json_object = deps['_parse_ai_json_object']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    _scan_invoice_supplier_name = deps['_scan_invoice_supplier_name']
    _supplier_invoice_template_json = deps['_supplier_invoice_template_json']
    _supplier_invoice_template_row = deps['_supplier_invoice_template_row']
    generate_yandex_parts = deps['generate_yandex_parts']
    generate_yandex_text = deps['generate_yandex_text']
    get_db = deps['get_db']
    require_roles = deps['require_roles']
    router = APIRouter()

    def _apply_supplier_invoice_template_metadata(payload: dict, company_id: int) -> dict:
        payload = dict(payload or {})
        recognition = {
            "method": "ai_ocr",
            "label": "Распознано через AI/OCR",
            "confidence": payload.get("confidence"),
            "templateId": None,
            "templateName": "",
            "supplierId": 0,
            "supplierName": _scan_invoice_supplier_name(payload),
            "warnings": [],
        }
        from backend.features.supplier_invoice_templates.scope import exact_supplier
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                supplier = exact_supplier(cur, company_id, payload)
                if supplier:
                    recognition["supplierId"] = supplier["id"]
                    recognition["supplierName"] = supplier["name"] or recognition["supplierName"]
                    match, _ = _find_supplier_invoice_template(cur, payload, company_id, supplier["id"])
                    if match:
                        template = _supplier_invoice_template_row(match["row"])
                        recognition.update({
                            "method": "template", "label": "OCR с подсказкой шаблона; проверьте оригинал",
                            "templateId": template["id"], "templateName": template["templateName"],
                        })
                else:
                    recognition["warnings"].append("Точный поставщик по ИНН в компании не определён. Выберите и проверьте его вручную.")
        finally:
            conn.close()
        payload["recognition"] = recognition
        payload["scanRecognition"] = recognition
        return payload

    def _invoice_scan_template_hint(company_id: int, limit: int = 12) -> str:
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""SELECT supplier_name, template_name, document_type, match_keywords, sample_json, usage_count
                               FROM supplier_invoice_templates
                               WHERE active=TRUE AND company_id=%s
                               ORDER BY usage_count DESC, updated_at DESC, id DESC
                               LIMIT %s""", (company_id, limit))
                rows = cur.fetchall()
        finally:
            conn.close()
        if not rows:
            return ""
        lines = []
        for row in rows:
            keywords = _supplier_invoice_template_json(row.get("match_keywords"), [])
            if not isinstance(keywords, list):
                keywords = []
            sample = _supplier_invoice_template_json(row.get("sample_json"), {})
            sample_items = sample.get("items") if isinstance(sample, dict) else []
            sample_names = []
            if isinstance(sample_items, list):
                for item in sample_items[:3]:
                    if isinstance(item, dict) and item.get("name"):
                        sample_names.append(str(item.get("name")))
            lines.append(
                "- " + (row.get("supplier_name") or "Поставщик")
                + " / " + (row.get("template_name") or "типовой шаблон")
                + " / " + (row.get("document_type") or "любой документ")
                + (": ключи " + ", ".join(str(k) for k in keywords[:4]) if keywords else "")
                + ("; пример строк: " + "; ".join(sample_names) if sample_names else "")
            )
        return "\n".join(lines)

    def _normalize_invoice_scan_image_entry(entry):
        mime_type = "image/jpeg"
        filename = ""
        if isinstance(entry, dict):
            raw = (
                entry.get("data")
                or entry.get("base64")
                or entry.get("image")
                or entry.get("imageData")
                or ""
            )
            mime_type = str(
                entry.get("mimeType")
                or entry.get("mime")
                or entry.get("contentType")
                or mime_type
            ).strip() or mime_type
            filename = str(entry.get("name") or entry.get("filename") or "")
        else:
            raw = str(entry or "")

        raw = str(raw or "").strip()
        if raw.startswith("data:"):
            header, _, payload = raw.partition(",")
            header = header[5:]
            if ";" in header:
                mime_type = header.split(";", 1)[0] or mime_type
            raw = payload.strip()

        mime_lower = mime_type.lower()
        filename_lower = filename.lower()
        if "heic" in mime_lower or "heif" in mime_lower or filename_lower.endswith((".heic", ".heif")):
            raise HTTPException(
                status_code=422,
                detail="HEIC/HEIF нужно преобразовать в JPEG/PNG перед распознаванием накладной.",
            )
        if not raw:
            return None
        if mime_lower == "application/pdf" or filename_lower.endswith(".pdf"):
            return {"data": raw, "mimeType": "application/pdf", "name": filename or "invoice.pdf"}
        if not mime_type.lower().startswith("image/"):
            raise HTTPException(
                status_code=422,
                detail="Для распознавания накладной нужен PDF или изображение.",
            )
        return {"data": raw, "mimeType": mime_type, "name": filename or "invoice-page.jpg"}

    def _repair_invoice_scan_json(answer: str, parse_error: str):
        raw_answer = (answer or "").strip()
        if not raw_answer:
            return None, parse_error or "empty"
        instructions = (
            "Ты исправляешь ответ распознавания складского или бухгалтерского документа: "
            "счета на оплату, счета поставщика, УПД, товарной накладной, приходной накладной "
            "или товарного чека. Верни только валидный JSON-объект без markdown, комментариев "
            "и текста вокруг."
        )
        prompt = (
            "Ниже ответ модели по документу, который не распарсился как JSON. "
            "Преобразуй его в один валидный JSON-объект по схеме. "
            "Не добавляй новые товары, которых нет в тексте. Если часть строки оборвана, "
            "сохрани только читаемые полноценные позиции, а явно неполные элементы отбрось. "
            "Все переносы внутри строк замени пробелами, кавычки экранируй. "
            "Если это счет на оплату или счет поставщика с таблицей товаров, не отбрасывай его: "
            "верни documentType \"supplier_invoice\" или \"payment_invoice\" и заполни items. "
            "Если это фрагмент документа без шапки, но с таблицей товаров, сохрани читаемые строки, "
            "пустые реквизиты оставь пустыми строками и не возвращай documentType \"other\". "
            "Если данных по товарам нет, верни documentType \"other\" и пустой items. "
            f"Схема: {_invoice_scan_json_format()}\n"
            f"Ошибка JSON-парсера: {parse_error or 'invalid json'}\n"
            "Ответ модели:\n"
            f"{raw_answer[:18000]}"
        )
        try:
            repair_answer = generate_yandex_text(
                capability="invoice_scan",
                instructions=instructions,
                input_text=prompt,
                temperature=0,
                max_output_tokens=12000,
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
            parsed, repair_error = _parse_ai_json_object(repair_answer)
            if parsed is not None:
                return parsed, ""
            print("SCAN REPAIR FAILED:", repair_error)
            print("SCAN REPAIR RAW HEAD:", repair_answer[:500])
            return None, repair_error or parse_error or "invalid repaired json"
        except ModelGatewayError as error:
            print("SCAN REPAIR ERROR:", error.code)
            return None, error.code

    def _retry_invoice_scan_compact_json(images: list):
        try:
            compact_content = []
            for idx, image in enumerate(images or [], start=1):
                compact_content.extend(_invoice_scan_ai_content(image, idx, len(images or [])))
            compact_content.append(ModelInputPart(kind="text", value=(
                "Повтори распознавание в коротком режиме. Верни только валидный JSON без markdown и без пояснений. "
                "Подходят счет на оплату, счет поставщика, УПД, товарная накладная, приходная накладная и фрагмент товарной таблицы. "
                "Если видна таблица товаров, documentType не должен быть other. Не пиши переносы строк внутри строк JSON. "
                "Если строк много, верни первые 80 полностью читаемых строк и итог документа. "
                "Формат: {"
                "\"documentType\":\"supplier_invoice|payment_invoice|warehouse_invoice|universal_transfer_document|waybill|receipt|other\","
                "\"confidence\":0..1,"
                "\"pagesCount\":число,"
                "\"number\":строка,"
                "\"date\":\"YYYY-MM-DD или исходная дата\","
                "\"supplier\":строка,"
                "\"supplierInn\":строка,"
                "\"supplierKpp\":строка,"
                "\"supplierOgrn\":строка,"
                "\"buyer\":строка,"
                "\"vat\":\"Без НДС|С НДС 20%|С НДС 22%\","
                "\"vatRate\":0|20|22,"
                "\"totalBase\":число,"
                "\"totalVat\":число,"
                "\"totalWithVat\":число,"
                "\"items\":[{\"name\":строка,\"quantity\":число,\"unit\":строка,\"price\":число,\"lineTotal\":число}]"
                "}"
            )))
            retry_answer = generate_yandex_parts(
                capability="invoice_scan",
                instructions="Ты распознаешь строительные счета и накладные. Верни только короткий валидный JSON.",
                input_parts=tuple(compact_content),
                temperature=0,
                max_output_tokens=9000,
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
            parsed, retry_error = _parse_ai_json_object(retry_answer)
            if parsed is not None:
                return parsed, ""
            print("SCAN COMPACT RETRY FAILED:", retry_error)
            print("SCAN COMPACT RAW HEAD:", retry_answer[:500])
            return None, retry_error or "invalid compact json"
        except ModelGatewayError as error:
            print("SCAN COMPACT RETRY ERROR:", error.code)
            return None, error.code
        except HTTPException as error:
            return None, str(error.detail)

    @router.post("/scan-invoice")
    def scan_invoice(data: dict, x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"), x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"), _current_user: dict = Depends(require_roles(*PHYSICAL_RECEIPT_ROLES, "бухгалтер"))):
        from backend.features.supplier_invoice_templates.scope import resolve_scan_company
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                company_id = resolve_scan_company(cur, _current_user, _resolve_work_company_context,
                    (*PHYSICAL_RECEIPT_ROLES, "бухгалтер"), company_id=data.get("companyId"),
                    x_company_id=x_company_id, x_company_mode=x_company_mode)
        finally:
            conn.close()
        images = data.get("images") or data.get("pages") or []
        if isinstance(images, (str, dict)):
            images = [images]
        if not isinstance(images, list):
            images = []
        if data.get("image"):
            images = [data.get("image")] + images
        if len(images) > 8:
            raise HTTPException(422, "Выбрано больше 8 файлов. Загрузите полный документ допустимого размера или заполните его вручную.")
        images = [_normalize_invoice_scan_image_entry(img) for img in images]
        images = [img for img in images if img]
        if not images:
            return {"ok": False, "error": "Нет изображения документа"}
        template_hint = _invoice_scan_template_hint(company_id)
        try:
            content = []
            for idx, image in enumerate(images, start=1):
                content.extend(_invoice_scan_ai_content(image, idx, len(images)))
            content.append(ModelInputPart(kind="text", value=(
                "Распознай складской или бухгалтерский документ с товарными строками: счет на оплату, счет поставщика, "
                "УПД, универсальный передаточный документ, товарную накладную, приходную накладную или товарный чек. "
                "Если это 'Счет на оплату' или 'Счёт на оплату' с таблицей товаров, он подходит: верни documentType "
                "\"supplier_invoice\" или \"payment_invoice\" и распознай строки товаров. Если страниц несколько, это один документ: "
                "объедини позиции со всех страниц в один items, номер/дату/поставщика бери из шапки, итог — с последней страницы или строки итого. "
                "Если виден только фрагмент страницы с таблицей товаров без номера, даты или полной шапки, всё равно распознай строки: "
                "documentType оставь \"supplier_invoice\", number/date/documentTitle заполни пустыми строками, supplier бери из "
                "'Поставщик', 'Грузоотправитель' или ближайшей строки с ИНН, если она видна; ИНН/КПП/ОГРН поставщика положи отдельно в supplierInn/supplierKpp/supplierOgrn. "
                "Документ может быть повернут на 90 или 180 градусов: мысленно поверни страницу и читай таблицу по строкам. "
                "Верни только JSON без markdown. Не путай складскую накладную с личной тратой. Не выдумывай позиции: если строка товара читается плохо, "
                "заполни confidence меньше 0.6 и sourceText коротким исходным фрагментом до 60 символов. Не вставляй переносы строк внутрь JSON-строк. "
                "Для уверенно распознанных строк sourceText оставляй пустым, чтобы ответ был короче. Если виден только итог без списка товаров, "
                "верни пустой items и documentType \"other\". Для счета на оплату номер и дату бери из строки вида "
                "'Счет на оплату № ... от ...', поставщика — из поля 'Поставщик', покупателя — из поля 'Покупатель', "
                "таблицу товаров — из раздела 'Товары (работы, услуги)'. "
                f"Формат: {_invoice_scan_json_format()}. Если в документе есть строки 'Итого с НДС', 'Всего с учетом НДС', "
                "'Всего к оплате' или 'Сумма с НДС' — положи это значение в totalWithVat. "
                "Если есть 'в том числе НДС', 'В т.ч. НДС' или 'Сумма НДС' — положи сумму в totalVat. "
                "Если ставка НДС 22%, верни vat \"С НДС 22%\" и vatRate 22. Если цена дана без НДС и есть НДС, "
                "посчитай priceWithVat и lineTotalWithVat. Если цена дана только итогом строки, посчитай цену за единицу через количество. "
                "Не округляй крупные суммы до тысяч, не теряй НДС, сохраняй единицы измерения как в документе."
                + (("\nИзвестные шаблоны поставщиков для ориентира:\n" + template_hint) if template_hint else "")
            )))
            answer = generate_yandex_parts(
                capability="invoice_scan",
                instructions=(
                    "Ты распознаёшь счета на оплату, счета поставщика, УПД, товарные накладные, "
                    "приходные накладные и товарные чеки. Верни только JSON без комментариев и без markdown."
                ),
                input_parts=tuple(content),
                temperature=0.1,
                max_output_tokens=12000,
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
            parsed, parse_error = _parse_ai_json_object(answer)
            if parsed is None:
                print("SCAN PARSE FAILED:", parse_error)
                print("SCAN RAW LEN:", len(answer))
                print("SCAN RAW HEAD:", answer[:500])
                print("SCAN RAW TAIL:", answer[-500:] if len(answer) > 500 else "")
                parsed, repair_error = _repair_invoice_scan_json(answer, parse_error)
                if parsed is not None:
                    print("SCAN REPAIR OK")
                else:
                    print("SCAN REPAIR FINAL FAILED:", repair_error)
                    parsed, compact_error = _retry_invoice_scan_compact_json(images)
                    if parsed is not None:
                        print("SCAN COMPACT RETRY OK")
                    else:
                        print("SCAN COMPACT RETRY FINAL FAILED:", compact_error)
                        return {
                            "ok": False,
                            "error": "ИИ не смог корректно разобрать накладную. Попробуйте выбрать меньше страниц за раз или сделать фото ближе и ровнее.",
                        }
            page_items = []
            if isinstance(parsed.get("pages"), list):
                for page_idx, page in enumerate(parsed.get("pages") or [], start=1):
                    if not isinstance(page, dict):
                        continue
                    for item in page.get("items") or []:
                        if isinstance(item, dict):
                            item = dict(item)
                            item.setdefault("page", page.get("page") or page_idx)
                            page_items.append(item)
            if page_items and not parsed.get("items"):
                parsed["items"] = page_items
            parsed["pagesCount"] = int(parsed.get("pagesCount") or len(images))
            parsed = _normalize_invoice_totals_payload(parsed)
            parsed["pagesCount"] = int(parsed.get("pagesCount") or len(images))
            from backend.features.supplier_invoice_templates.amounts import scan_amount_errors
            parsed["validationWarnings"] = scan_amount_errors(parsed)
            parsed = _apply_supplier_invoice_template_metadata(parsed, company_id)
            print("SCAN OK: recognition completed")
            return {"ok": True, "data": parsed}
        except HTTPException as e:
            return {"ok": False, "error": str(e.detail or "Ошибка распознавания PDF/фото")}
        except ModelGatewayError as error:
            print("SCAN ERROR:", error.code)
            return {"ok": False, "error": "AI не ответил: " + error.code}
        except Exception as e:
            print("SCAN ERROR:", str(e))
            return {"ok": False, "error": str(e)}

    app.include_router(router)
    globals()['scan_invoice'] = scan_invoice

