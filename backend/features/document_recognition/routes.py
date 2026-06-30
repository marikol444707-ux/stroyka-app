import json
import os
import re
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET

from fastapi import Depends


FIELD_KEYS = (
    "docType",
    "documentTitle",
    "number",
    "docDate",
    "counterpartyName",
    "legalForm",
    "inn",
    "kpp",
    "ogrn",
    "legalAddress",
    "passportData",
    "bank",
    "bik",
    "bankAccount",
    "corrAccount",
    "signerName",
    "signerBasis",
    "amount",
    "contractSubject",
    "workType",
    "projectName",
    "notes",
)


def _text(value, limit=5000):
    return str(value or "").strip()[:limit]


def _digits(value):
    return re.sub(r"\D+", "", str(value or ""))


def _first_match(pattern, text, flags=re.IGNORECASE | re.MULTILINE, group=1):
    match = re.search(pattern, text or "", flags)
    if not match:
        return ""
    return _text(match.group(group), 500)


def _normalize_date(value):
    raw = _text(value, 40)
    if not raw:
        return ""
    match = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", raw)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", raw)
    if not match:
        return ""
    day, month, year = match.groups()
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _normalize_money(value):
    raw = _text(value, 80)
    if not raw:
        return ""
    raw = raw.replace("\xa0", " ")
    match = re.search(r"(\d[\d\s]*(?:[,.]\d{1,2})?)", raw)
    if not match:
        return ""
    return match.group(1).replace(" ", "").replace(",", ".")


def _compact_note(value, limit=900):
    raw = re.sub(r"\s+", " ", _text(value, limit * 2)).strip(" :-;,.")
    return raw[:limit]


def _detect_doc_type(text):
    low = (text or "").lower()
    if "дополнитель" in low and "соглаш" in low:
        return "Доп.соглашение"
    if "приложение" in low:
        return "Приложение"
    if "договор" in low or "контракт" in low:
        return "Договор"
    if "акт кс-2" in low:
        return "Акт КС-2"
    if "акт кс-3" in low:
        return "Акт КС-3"
    if "акт" in low:
        return "Акт"
    if "счет" in low or "счёт" in low:
        return "Счёт"
    if "паспорт" in low:
        return "Паспортные данные"
    if "реквизит" in low:
        return "Реквизиты"
    return "Другое"


def _detect_legal_form(fields):
    if fields.get("kpp"):
        return "Юрлицо"
    inn = _digits(fields.get("inn"))
    if len(inn) == 12 and fields.get("ogrn"):
        return "ИП"
    if fields.get("passportData"):
        return "Физлицо"
    return ""


def _extract_contract_subject(text):
    raw = text or ""
    match = re.search(
        r"(?:предмет\s+договора|предмет\s+контракта)\s*[:\n\r-]*([\s\S]{20,900}?)(?:\n\s*\d+\.|\n\s*[А-ЯЁA-Z][^\n]{0,80}[:\n]|права\s+и\s+обязанности|стоимость|срок|расчет|ответственность)",
        raw,
        re.IGNORECASE,
    )
    if match:
        return _compact_note(match.group(1), 700)
    match = re.search(r"((?:исполнитель|подрядчик|поставщик)[^\n]{0,160}(?:обязуется|выполняет|поставляет|оказывает)[^\n]{20,500})", raw, re.IGNORECASE)
    return _compact_note(match.group(1), 700) if match else ""


def _extract_counterparty(text):
    patterns = [
        r"(?:исполнитель|подрядчик|поставщик|заказчик|покупатель|контрагент)\s*[:\-]\s*([^\n]{3,180})",
        r"((?:ООО|АО|ПАО|ЗАО)\s+[\"«][^\"»\n]{2,140}[\"»])",
        r"((?:ООО|АО|ПАО|ЗАО|ИП)\s+[А-ЯЁA-Z][^,\n;]{2,160})",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        value = re.sub(r"\s+(?:ИНН|КПП|ОГРН|адрес).*$", "", value, flags=re.IGNORECASE).strip(" ,;")
        if value:
            return value[:180]
    return ""


def _heuristic_extract(text):
    raw = text or ""
    compact = re.sub(r"\s+", " ", raw)
    fields = {key: "" for key in FIELD_KEYS}
    fields["docType"] = _detect_doc_type(raw)
    fields["documentTitle"] = _first_match(r"^\s*([^\n]{0,40}(?:договор|контракт|счет|счёт|акт|приложение|соглашение)[^\n]{0,120})", raw)
    fields["number"] = _first_match(r"(?:№\s*|N\s*|Nº\s*)([A-Za-zА-Яа-я0-9_./-]{1,50})", raw)
    fields["docDate"] = _normalize_date(_first_match(r"(?:от|дата)\s+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}[-./]\d{1,2}[-./]\d{1,2})", raw))
    if not fields["docDate"]:
        fields["docDate"] = _normalize_date(_first_match(r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}[-./]\d{1,2}[-./]\d{1,2})", raw))
    fields["counterpartyName"] = _extract_counterparty(raw)
    fields["inn"] = _digits(_first_match(r"\bИНН\b[^\d]{0,20}(\d{10,12})", raw))[:12]
    fields["kpp"] = _digits(_first_match(r"\bКПП\b[^\d]{0,20}(\d{9})", raw))[:9]
    fields["ogrn"] = _digits(_first_match(r"\bОГРН(?:ИП)?\b[^\d]{0,20}(\d{13,15})", raw))[:15]
    fields["bik"] = _digits(_first_match(r"\bБИК\b[^\d]{0,20}(\d{9})", raw))[:9]
    fields["bankAccount"] = _digits(_first_match(r"(?:р/с|расчетн(?:ый|ого|ом)?\s+счет|расч[её]тный\s+сч[её]т)[^\d]{0,30}(\d{20})", raw))[:20]
    fields["corrAccount"] = _digits(_first_match(r"(?:к/с|корр(?:еспондентский)?\.?\s+счет|корр\.?\s*сч[её]т)[^\d]{0,30}(\d{20})", raw))[:20]
    fields["bank"] = _first_match(r"(?:банк|наименование банка)\s*[:\-]?\s*([^\n]{3,180})", raw)
    fields["legalAddress"] = _first_match(r"(?:юридический адрес|юр\.?\s*адрес|адрес регистрации|адрес)\s*[:\-]?\s*([^\n]{8,220})", raw)
    passport = _first_match(r"(паспорт[^\n]{10,220})", raw)
    if not passport:
        passport = _first_match(r"(\b\d{4}\s+\d{6}\b[^\n]{0,160})", raw)
    fields["passportData"] = passport
    fields["signerName"] = _first_match(r"(?:в лице|директор[а]?|генеральн(?:ый|ого)\s+директор[а]?)\s+([А-ЯЁ][А-ЯЁа-яё-]+(?:\s+[А-ЯЁ][А-ЯЁа-яё.-]+){1,3})", raw)
    fields["signerBasis"] = _first_match(r"действующ\w*\s+на\s+основании\s+([^,\n;.]{3,120})", raw)
    fields["amount"] = _normalize_money(_first_match(r"(?:сумма|стоимость|цена|итого|всего\s+к\s+оплате)[^\d]{0,60}(\d[\d\s]*(?:[,.]\d{1,2})?)\s*(?:руб|₽)?", compact))
    fields["contractSubject"] = _extract_contract_subject(raw)
    if fields["contractSubject"]:
        fields["workType"] = fields["contractSubject"][:180]
    fields["legalForm"] = _detect_legal_form(fields)
    fields["notes"] = ""
    return fields


def _extract_json_object(text):
    raw = _text(text, 20000)
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    candidates = [raw]
    if start >= 0 and end > start:
        candidates.insert(0, raw[start:end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else {}
        except Exception:
            continue
    return {}


def _merge_fields(ai_fields, fallback_fields):
    merged = dict(fallback_fields)
    if isinstance(ai_fields, dict):
        for key in FIELD_KEYS:
            value = ai_fields.get(key)
            if value not in (None, ""):
                merged[key] = _text(value, 5000)
        if isinstance(ai_fields.get("warnings"), list):
            merged["_aiWarnings"] = [_text(x, 300) for x in ai_fields.get("warnings") if _text(x, 300)]
    merged["docDate"] = _normalize_date(merged.get("docDate")) or _text(merged.get("docDate"), 50)
    merged["amount"] = _normalize_money(merged.get("amount")) or _text(merged.get("amount"), 80)
    for key in ("inn", "kpp", "ogrn", "bik", "bankAccount", "corrAccount"):
        value = _digits(merged.get(key))
        if value:
            merged[key] = value
    if not merged.get("legalForm"):
        merged["legalForm"] = _detect_legal_form(merged)
    return merged


def _local_upload_path(file_url, upload_dir):
    raw = _text(file_url, 1000)
    if not raw.startswith("/uploads/") or not upload_dir:
        return ""
    rel = urllib.parse.unquote(raw[len("/uploads/"):])
    rel = os.path.normpath(rel).lstrip(os.sep)
    base = os.path.abspath(upload_dir)
    candidate = os.path.abspath(os.path.join(base, rel))
    if not candidate.startswith(base + os.sep):
        return ""
    return candidate if os.path.exists(candidate) else ""


def _read_txt(path):
    with open(path, "rb") as fh:
        raw = fh.read(40000)
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(encoding, errors="ignore")
        except Exception:
            continue
    return ""


def _read_docx(path):
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    parts = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            parts.append(node.text)
    return " ".join(parts)


def _read_pdf(path):
    reader_cls = None
    try:
        from pypdf import PdfReader
        reader_cls = PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
            reader_cls = PdfReader
        except Exception:
            reader_cls = None
    if not reader_cls:
        return "", "PDF загружен, но библиотека чтения PDF недоступна на сервере"
    reader = reader_cls(path)
    pages = []
    for page in reader.pages[:20]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(pages).strip(), ""


def _extract_file_text(file_url, upload_dir):
    path = _local_upload_path(file_url, upload_dir)
    if not path:
        return "", ""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            return _read_pdf(path)
        if ext == ".docx":
            return _read_docx(path), ""
        if ext in (".txt", ".csv", ".rtf"):
            return _read_txt(path), ""
    except Exception as exc:
        return "", "Не удалось извлечь текст из файла: " + str(exc)
    return "", "Файл прикреплен, но для этого формата нужен OCR или вставленный текст"


def _append_note(existing, line):
    current = _text(existing, 4000)
    addition = _text(line, 1200)
    if not addition:
        return current
    if addition in current:
        return current
    return (current + "\n" + addition).strip() if current else addition


def _build_lead_patch(fields, current_fields):
    current_fields = current_fields if isinstance(current_fields, dict) else {}
    patch = {}
    key_map = {
        "legalForm": "legalForm",
        "passportData": "passportData",
        "inn": "inn",
        "kpp": "kpp",
        "ogrn": "ogrn",
        "legalAddress": "legalAddress",
        "bank": "bank",
        "bik": "bik",
        "bankAccount": "bankAccount",
        "corrAccount": "corrAccount",
        "signerName": "signerName",
        "signerBasis": "signerBasis",
        "workType": "workType",
        "contractSubject": "contractSubject",
    }
    for src, dst in key_map.items():
        if fields.get(src):
            patch[dst] = fields.get(src)
    if fields.get("counterpartyName") and not _text(current_fields.get("name")):
        patch["name"] = fields["counterpartyName"]
    if fields.get("amount") and not _text(current_fields.get("budget")):
        patch["budget"] = fields["amount"]
    note_bits = []
    if fields.get("docType"):
        note_bits.append("тип: " + fields["docType"])
    if fields.get("number"):
        note_bits.append("номер: " + fields["number"])
    if fields.get("docDate"):
        note_bits.append("дата: " + fields["docDate"])
    if fields.get("contractSubject"):
        note_bits.append("предмет договора: " + fields["contractSubject"])
    if note_bits:
        patch["notes"] = _append_note(current_fields.get("notes"), "Распознано из документа: " + "; ".join(note_bits))
    patch["documentStatus"] = "На проверке"
    patch["reviewStatus"] = "Нужна проверка"
    return {k: v for k, v in patch.items() if v not in (None, "")}


def _build_project_document(fields, file_url, current_fields):
    current_fields = current_fields if isinstance(current_fields, dict) else {}
    notes = current_fields.get("notes") or ""
    if fields.get("contractSubject"):
        notes = _append_note(notes, "Предмет договора: " + fields["contractSubject"])
    if fields.get("notes"):
        notes = _append_note(notes, fields["notes"])
    patch = {
        "docType": fields.get("docType") or current_fields.get("docType") or "Другое",
        "number": fields.get("number") or current_fields.get("number") or "",
        "docDate": fields.get("docDate") or current_fields.get("docDate") or "",
        "counterparty": fields.get("counterpartyName") or current_fields.get("counterparty") or "",
        "amount": fields.get("amount") or current_fields.get("amount") or "",
        "notes": notes,
    }
    if file_url:
        patch["scanUrl"] = file_url
        patch["signStatus"] = current_fields.get("signStatus") or "На подписи"
    return {k: v for k, v in patch.items() if v not in (None, "")}


def _build_crm_document(fields, file_url):
    title = fields.get("documentTitle") or "Распознанный документ"
    if fields.get("counterpartyName"):
        title = (fields.get("docType") or "Документ") + " - " + fields["counterpartyName"]
    notes = fields.get("notes") or ""
    if fields.get("contractSubject"):
        notes = _append_note(notes, "Предмет договора: " + fields["contractSubject"])
    return {
        "docType": fields.get("docType") or "Прочее",
        "title": title[:255],
        "fileUrl": file_url or "",
        "status": "На проверке",
        "number": fields.get("number") or "",
        "docDate": fields.get("docDate") or "",
        "notes": notes,
    }


def _ai_extract(text, context, entity_type, project_name, current_fields, api_key, folder_id):
    if not (api_key and folder_id and text):
        return {}, ""
    try:
        import openai as oa
    except Exception as exc:
        return {}, "AI-клиент недоступен: " + str(exc)
    prompt = {
        "context": context,
        "entityType": entity_type,
        "projectName": project_name,
        "currentFields": current_fields if isinstance(current_fields, dict) else {},
        "documentText": text[:24000],
        "requiredJsonKeys": list(FIELD_KEYS) + ["confidence", "warnings"],
    }
    instructions = (
        "Ты извлекаешь данные из строительных договоров, приложений, реквизитов, паспортных данных и счетов. "
        "Верни только JSON без markdown. Не выдумывай значения: если поля нет в тексте, оставь пустую строку. "
        "docDate верни в ISO YYYY-MM-DD, amount только числом строкой, contractSubject - краткий предмет договора. "
        "Для CRM поставщиков и исполнителей особенно важны ИНН, КПП, ОГРН, банк, БИК, счета, подписант, основание подписи, паспортные данные."
    )
    try:
        client = oa.OpenAI(api_key=api_key, base_url="https://ai.api.cloud.yandex.net/v1", project=folder_id)
        response = client.responses.create(
            model=f"gpt://{folder_id}/yandexgpt-5.1/latest",
            temperature=0.1,
            instructions=instructions,
            input=json.dumps(prompt, ensure_ascii=False),
            max_output_tokens=2500,
        )
        return _extract_json_object(response.output_text or ""), ""
    except Exception as exc:
        return {}, "AI-распознавание недоступно: " + str(exc)


def register_document_recognition_module(app, deps):
    require_roles = deps["require_roles"]
    access_roles = tuple(dict.fromkeys(deps.get("access_roles") or ()))
    yandex_api_key = deps.get("yandex_api_key") or ""
    yandex_folder_id = deps.get("yandex_folder_id") or ""
    upload_dir = deps.get("upload_dir") or "uploads"
    log_audit = deps.get("log_audit")
    document_access = require_roles(*access_roles)

    @app.post("/document-recognition/analyze")
    def analyze_document(data: dict, current_user: dict = Depends(document_access)):
        data = data or {}
        context = _text(data.get("context"), 80) or "general"
        entity_type = _text(data.get("entityType"), 80)
        project_name = _text(data.get("projectName"), 255)
        file_url = _text(data.get("fileUrl"), 1000)
        current_fields = data.get("currentFields") if isinstance(data.get("currentFields"), dict) else {}
        warnings = []

        pasted_text = _text(data.get("text"), 32000)
        file_text, file_warning = _extract_file_text(file_url, upload_dir)
        if file_warning:
            warnings.append(file_warning)
        source_text = "\n\n".join(part for part in (pasted_text, file_text) if part).strip()

        if not source_text and file_url:
            warnings.append("Файл прикреплен, но текст не извлечен. Для точного заполнения добавьте OCR/текст документа.")
        if not source_text:
            fields = {key: "" for key in FIELD_KEYS}
            fields["docType"] = "Другое"
            source = "empty"
        else:
            heuristic = _heuristic_extract(source_text)
            ai_data, ai_warning = _ai_extract(source_text, context, entity_type, project_name, current_fields, yandex_api_key, yandex_folder_id)
            if ai_warning:
                warnings.append(ai_warning)
            fields = _merge_fields(ai_data, heuristic)
            source = "ai" if ai_data else "heuristic"

        warnings.extend(fields.pop("_aiWarnings", []) or [])
        lead_patch = _build_lead_patch(fields, current_fields)
        project_document = _build_project_document(fields, file_url, current_fields)
        crm_document = _build_crm_document(fields, file_url)

        if log_audit:
            try:
                log_audit(
                    current_user.get("name", ""),
                    current_user.get("role", ""),
                    "analyze",
                    "document_recognition",
                    None,
                    "Распознан документ: " + (fields.get("docType") or "Другое"),
                    project_name or entity_type or context,
                )
            except Exception:
                pass

        return {
            "ok": True,
            "source": source,
            "context": context,
            "entityType": entity_type,
            "fileUrl": file_url,
            "extracted": fields,
            "suggestedLeadPatch": lead_patch,
            "suggestedProjectDocument": project_document,
            "suggestedCrmDocument": crm_document,
            "warnings": list(dict.fromkeys([w for w in warnings if w])),
        }
