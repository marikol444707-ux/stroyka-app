from datetime import datetime


class WarehouseReceiptPolicyError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _text(payload: dict, *keys: str) -> str:
    for key in keys:
        value = (payload or {}).get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _positive_id(payload: dict, *keys: str):
    value = _text(payload, *keys)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "да"}


def supplier_identity_present(payload: dict) -> bool:
    return bool(
        _positive_id(payload, "supplierId", "supplier_id")
        or _text(payload, "supplierName", "supplier_name", "supplier", "newSupplierName")
    )


def resolve_warehouse_receipt_policy(payload: dict, *, target_project: str, role: str) -> dict:
    payload = payload or {}
    target_project = str(target_project or "").strip()
    warehouse_target = _text(payload, "warehouseTarget", "warehouse_target").lower()
    is_main_warehouse = not target_project and warehouse_target in {"", "main"}
    has_supplier = supplier_identity_present(payload)
    has_supplier_invoice = bool(_positive_id(payload, "supplierInvoiceId", "supplier_invoice_id"))
    has_accounting_supplier = has_supplier or has_supplier_invoice
    inventory_only = (
        _bool_value(payload.get("inventoryOnly") if "inventoryOnly" in payload else payload.get("inventory_only"))
        or _text(payload, "selectedAction", "selected_action") == "receive_stock_without_supplier"
    )

    if inventory_only and not is_main_warehouse:
        raise WarehouseReceiptPolicyError("Приход без поставщика доступен только для основного склада")
    if inventory_only and (has_supplier or has_supplier_invoice):
        raise WarehouseReceiptPolicyError(
            "В режиме «Без поставщика и оплаты» нельзя указывать поставщика или документ к оплате"
        )
    if inventory_only and role not in {"директор", "зам_директора"}:
        raise WarehouseReceiptPolicyError(
            "Приход без поставщика на основной склад доступен только директору или заместителю",
            status_code=403,
        )
    if is_main_warehouse and not has_accounting_supplier and not inventory_only:
        raise WarehouseReceiptPolicyError(
            "Выберите поставщика или включите режим «Без поставщика и оплаты»",
        )

    return {
        "inventoryOnly": inventory_only,
        "accountingRequired": not inventory_only,
        "hasSupplier": has_accounting_supplier,
        "selectedAction": "receive_stock_without_supplier" if inventory_only else "receive_to_warehouse",
    }


def warehouse_invoice_accounting_required(invoice: dict) -> bool:
    invoice = invoice or {}
    if _text(invoice, "selectedAction", "selected_action") == "receive_stock_without_supplier":
        return False
    explicit = invoice.get("accountingRequired")
    if explicit is None:
        explicit = invoice.get("accounting_required")
    if explicit is False:
        return False

    target = _text(invoice, "warehouseTarget", "warehouse_target")
    project = _text(invoice, "project")
    location = _text(invoice, "location")
    is_main_warehouse = target == "main" or (not project and location == "Основной склад")
    return not (is_main_warehouse and not supplier_identity_present(invoice))


def build_internal_receipt_number(now: datetime = None) -> str:
    value = now or datetime.now()
    return "ПРИХОД-" + value.strftime("%Y%m%d-%H%M%S-%f")
