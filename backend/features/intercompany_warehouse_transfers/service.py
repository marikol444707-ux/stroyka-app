import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from uuid import UUID

from psycopg2.extras import Json


READERS = ("директор", "зам_директора", "кладовщик", "снабженец", "бухгалтер")
WRITERS = ("директор", "зам_директора", "кладовщик", "снабженец")


def enabled():
    return os.getenv("INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED") == "1"


def _positive_int(value, label):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError("Укажите " + label)
    if parsed <= 0:
        raise ValueError("Укажите " + label)
    return parsed


def _quantity(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Укажите положительное количество")
    if not parsed.is_finite() or parsed <= 0 or parsed >= Decimal("100000000"):
        raise ValueError("Укажите положительное количество")
    return parsed


def parse_create(data, source_company_id):
    destination = _positive_int(data.get("destinationCompanyId"), "компанию-получателя")
    if destination == int(source_company_id):
        raise ValueError("Выберите другую компанию-получателя")
    stock_id = _positive_int(data.get("sourceStockId"), "материал основного склада")
    reason = str(data.get("reason") or "").strip()[:1000]
    if not reason:
        raise ValueError("Укажите основание передачи")
    quantity = _quantity(data.get("quantity"))
    try:
        request_id = str(UUID(str(data.get("requestId") or "")))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Некорректный номер запроса")
    return {
        "destinationCompanyId": destination,
        "sourceStockId": stock_id,
        "quantity": quantity,
        "reason": reason,
        "requestId": request_id,
    }


def _canonical_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dict(row):
    return dict(row or {})


def side_view(row, company_id):
    item = _dict(row)
    source_id = int(item.get("sourceCompanyId") or 0)
    destination_id = int(item.get("destinationCompanyId") or 0)
    if int(company_id) == source_id:
        side = "source"
        counterparty = {"companyId": destination_id, "name": item.get("destinationCompanyName") or ""}
        document = item.get("sourceDocument") or {}
    elif int(company_id) == destination_id:
        side = "destination"
        counterparty = {"companyId": source_id, "name": item.get("sourceCompanyName") or ""}
        document = item.get("destinationDocument") or {}
    else:
        raise ValueError("Передача не относится к выбранной компании")
    public = {key: value for key, value in item.items() if key not in (
        "sourceDocument", "destinationDocument", "sourceCompanyName", "destinationCompanyName",
        "unitPrice", "category",
    )}
    public.update(side=side, counterparty=counterparty, document=document)
    return public


SELECT = """SELECT t.id,t.request_id::text AS \"requestId\",
 t.source_company_id AS \"sourceCompanyId\",t.destination_company_id AS \"destinationCompanyId\",
 sc.name AS \"sourceCompanyName\",dc.name AS \"destinationCompanyName\",
 t.source_stock_id AS \"sourceStockId\",t.material_name AS \"materialName\",t.unit,t.quantity,
 t.unit_price AS \"unitPrice\",t.category,t.reason,t.status,t.created_by_name AS \"createdBy\",
 t.source_approved_at AS \"sourceApprovedAt\",t.decided_by_name AS \"decidedBy\",
 t.decided_at AS \"decidedAt\",t.decision_reason AS \"decisionReason\",
 t.source_movement_id AS \"sourceMovementId\",t.destination_movement_id AS \"destinationMovementId\",
 t.source_document_json AS \"sourceDocument\",t.destination_document_json AS \"destinationDocument\",
 t.version,t.created_at AS \"createdAt\",t.updated_at AS \"updatedAt\"
 FROM intercompany_warehouse_transfers t
 JOIN companies sc ON sc.id=t.source_company_id JOIN companies dc ON dc.id=t.destination_company_id"""


def load(cur, transfer_id, company_id, lock=False):
    cur.execute(SELECT + " WHERE t.id=%s AND (t.source_company_id=%s OR t.destination_company_id=%s)" +
                (" FOR UPDATE OF t" if lock else ""), (transfer_id, company_id, company_id))
    row = cur.fetchone()
    return side_view(row, company_id) if row else None


def listing(cur, company_id, limit=100):
    cur.execute(SELECT + " WHERE t.source_company_id=%s OR t.destination_company_id=%s ORDER BY t.id DESC LIMIT %s",
                (company_id, company_id, limit))
    return [side_view(row, company_id) for row in cur.fetchall()]


def _snapshot(transfer_id, kind, own_company, counterparty, stock, quantity, reason, actor):
    snapshot = {
        "schemaVersion": 1, "kind": kind, "transferId": transfer_id,
        "company": {"id": own_company["id"], "name": own_company["name"]},
        "counterparty": {"id": counterparty["id"], "name": counterparty["name"]},
        "material": {"name": stock["name"], "unit": stock["unit"], "quantity": str(quantity)},
        "location": "Основной склад", "reason": reason,
        "approvedBy": {"userId": actor["id"], "name": actor.get("name") or ""},
    }
    if kind == "intercompany_dispatch":
        snapshot["material"]["unitPrice"] = str(stock.get("price") or 0)
    return snapshot


def create(cur, actor, source_company_id, data):
    values = parse_create(data, source_company_id)
    cur.execute(SELECT + " WHERE t.source_company_id=%s AND t.request_id=%s",
                (source_company_id, values["requestId"]))
    replay = cur.fetchone()
    if replay:
        return side_view(replay, source_company_id)
    cur.execute("SELECT id,name,active FROM companies WHERE id IN (%s,%s) ORDER BY id FOR SHARE",
                (source_company_id, values["destinationCompanyId"]))
    companies = {int(row["id"]): row for row in cur.fetchall()}
    source_company = companies.get(int(source_company_id))
    destination_company = companies.get(values["destinationCompanyId"])
    if not source_company or source_company.get("active") is False:
        raise ValueError("Компания-отправитель недоступна")
    if not destination_company or destination_company.get("active") is False:
        raise ValueError("Компания-получатель не найдена или отключена")
    cur.execute("""SELECT id,name,unit,quantity,price,category FROM warehouse_main
        WHERE id=%s AND company_id=%s FOR UPDATE""", (values["sourceStockId"], source_company_id))
    stock = cur.fetchone()
    if not stock:
        raise ValueError("Материал не найден на основном складе выбранной компании")
    if Decimal(str(stock.get("quantity") or 0)) < values["quantity"]:
        raise ValueError("На основном складе недостаточно материала")
    cur.execute("SELECT nextval(pg_get_serial_sequence('intercompany_warehouse_transfers','id')) AS id")
    transfer_id = int(cur.fetchone()["id"])
    source_document = _snapshot(transfer_id, "intercompany_dispatch", source_company, destination_company,
                                stock, values["quantity"], values["reason"], actor)
    destination_document = _snapshot(transfer_id, "intercompany_receipt", destination_company, source_company,
                                     stock, values["quantity"], values["reason"], actor)
    cur.execute("""INSERT INTO intercompany_warehouse_transfers
        (id,request_id,source_company_id,destination_company_id,source_stock_id,material_name,unit,quantity,
         unit_price,category,reason,created_by_user_id,created_by_name,source_document_json,
         destination_document_json,source_document_hash,destination_document_hash)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (transfer_id, values["requestId"], source_company_id, values["destinationCompanyId"], stock["id"],
         stock["name"], stock.get("unit") or "шт", values["quantity"], stock.get("price") or 0,
         stock.get("category") or "", values["reason"], actor["id"], actor.get("name") or "",
         Json(source_document), Json(destination_document), _canonical_hash(source_document),
         _canonical_hash(destination_document)))
    cur.execute("""INSERT INTO intercompany_warehouse_transfer_events
        (transfer_id,company_id,actor_id,actor_name,action,details)
        VALUES(%s,%s,%s,%s,'source_approved',%s)""",
        (transfer_id, source_company_id, actor["id"], actor.get("name") or "",
         Json({"destinationCompanyId": values["destinationCompanyId"]})))
    return load(cur, transfer_id, source_company_id)


def _insert_movement(cur, company_id, material, quantity, unit, from_location, to_location, actor, reason):
    cur.execute("""INSERT INTO warehouse_movements
        (company_id,material_name,from_location,to_location,quantity,unit,work_package,date,created_by,notes)
        VALUES(%s,%s,%s,%s,%s,%s,'Основная',%s,%s,%s) RETURNING id""",
        (company_id, material, from_location, to_location, quantity, unit,
         dt.date.today().isoformat(), actor.get("name") or "", reason))
    return int(cur.fetchone()["id"])


def decide(cur, actor, company_id, transfer_id, action, reason=""):
    cur.execute(SELECT + " WHERE t.id=%s AND (t.source_company_id=%s OR t.destination_company_id=%s) FOR UPDATE OF t",
                (transfer_id, company_id, company_id))
    row = cur.fetchone()
    if not row:
        raise LookupError("Межфирменное перемещение не найдено")
    item = _dict(row)
    expected_side = "source" if action == "cancel" else "destination"
    actual_side = "source" if int(item["sourceCompanyId"]) == int(company_id) else "destination"
    if actual_side != expected_side:
        raise PermissionError("Действие должна выполнить " + ("компания-отправитель" if expected_side == "source" else "компания-получатель"))
    target_status = {"accept": "accepted", "reject": "rejected", "cancel": "cancelled"}.get(action)
    if not target_status:
        raise ValueError("Неизвестное действие")
    if item["status"] == target_status:
        return side_view(item, company_id)
    if item["status"] != "pending":
        raise ValueError("По перемещению уже принято окончательное решение")
    decision_reason = str(reason or "").strip()[:1000]
    if action in ("reject", "cancel") and not decision_reason:
        raise ValueError("Укажите причину")
    source_movement_id = destination_movement_id = None
    if action == "accept":
        for locked_company in sorted((int(item["sourceCompanyId"]), int(item["destinationCompanyId"]))):
            cur.execute("SELECT pg_advisory_xact_lock(872341,%s)", (locked_company,))
        cur.execute("""SELECT id,name,unit,quantity,price,category FROM warehouse_main
            WHERE id=%s AND company_id=%s FOR UPDATE""", (item["sourceStockId"], item["sourceCompanyId"]))
        stock = cur.fetchone()
        quantity = Decimal(str(item["quantity"]))
        if not stock or stock["name"] != item["materialName"] or (stock.get("unit") or "шт") != item["unit"]:
            raise ValueError("Исходная складская позиция изменилась; создайте новое перемещение")
        if Decimal(str(stock.get("quantity") or 0)) < quantity:
            raise ValueError("На складе отправителя недостаточно материала")
        cur.execute("UPDATE warehouse_main SET quantity=quantity-%s WHERE id=%s AND company_id=%s",
                    (quantity, stock["id"], item["sourceCompanyId"]))
        cur.execute("""SELECT id FROM warehouse_main WHERE company_id=%s AND lower(name)=lower(%s)
            AND lower(COALESCE(NULLIF(unit,''),'шт'))=lower(%s) ORDER BY id LIMIT 1 FOR UPDATE""",
            (item["destinationCompanyId"], item["materialName"], item["unit"]))
        destination = cur.fetchone()
        if destination:
            cur.execute("""UPDATE warehouse_main SET quantity=quantity+%s,
                price=CASE WHEN %s>0 THEN %s ELSE price END,
                category=COALESCE(NULLIF(%s,''),category) WHERE id=%s AND company_id=%s""",
                (quantity, item["unitPrice"], item["unitPrice"], item.get("category") or "",
                 destination["id"], item["destinationCompanyId"]))
        else:
            cur.execute("""INSERT INTO warehouse_main(name,unit,quantity,price,min_quantity,category,company_id)
                VALUES(%s,%s,%s,%s,0,%s,%s)""", (item["materialName"], item["unit"], quantity,
                item["unitPrice"], item.get("category") or "", item["destinationCompanyId"]))
        transit = "Межфирменная передача #" + str(item["id"])
        source_movement_id = _insert_movement(cur, item["sourceCompanyId"], item["materialName"], quantity,
            item["unit"], "Основной склад", transit, actor, item["reason"])
        destination_movement_id = _insert_movement(cur, item["destinationCompanyId"], item["materialName"], quantity,
            item["unit"], transit, "Основной склад", actor, item["reason"])
        now_text = dt.datetime.now().strftime("%d.%m.%Y, %H:%M")
        for owner, kind, project, counterpart, movement_id in (
            (item["sourceCompanyId"], "межфирменная передача: списание", "Основной склад", item["destinationCompanyName"], source_movement_id),
            (item["destinationCompanyId"], "межфирменная передача: приход", "Основной склад", item["sourceCompanyName"], destination_movement_id),
        ):
            cur.execute("""INSERT INTO warehouse_history(company_id,material,type,quantity,unit,date,project,
                issued_to,issued_by,work_package,date_time,source_type,source_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'Основная',%s,'intercompany_warehouse_transfer',%s)""",
                (owner, item["materialName"], kind, quantity, item["unit"], dt.date.today().isoformat(),
                 project, counterpart, actor.get("name") or "", now_text, item["id"]))
    event_action = {"accept": "destination_accepted", "reject": "destination_rejected", "cancel": "source_cancelled"}[action]
    cur.execute("""UPDATE intercompany_warehouse_transfers SET status=%s,decided_by_user_id=%s,
        decided_by_name=%s,decided_at=now(),decision_reason=%s,source_movement_id=%s,
        destination_movement_id=%s,version=version+1,updated_at=now() WHERE id=%s""",
        (target_status, actor["id"], actor.get("name") or "", decision_reason or None,
         source_movement_id, destination_movement_id, item["id"]))
    cur.execute("""INSERT INTO intercompany_warehouse_transfer_events
        (transfer_id,company_id,actor_id,actor_name,action,details) VALUES(%s,%s,%s,%s,%s,%s)""",
        (item["id"], company_id, actor["id"], actor.get("name") or "", event_action,
         Json({"reason": decision_reason} if decision_reason else {})))
    return load(cur, item["id"], company_id)
