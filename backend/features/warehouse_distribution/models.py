"""Strict request contract and conservative receipt evidence validation."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_ID = 2147483647
MAIN = 'Основной склад'
Id = Annotated[int, Field(strict=True, gt=0, le=MAX_ID)]
Quantity = Annotated[Decimal, Field(gt=0, lt=Decimal('100000000'), decimal_places=6, allow_inf_nan=False)]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RowInput(StrictInput):
    lotId: Id
    projectId: Id
    quantity: Quantity


class OperationInput(StrictInput):
    companyId: Id
    requestId: UUID
    reason: str = Field(strict=True, min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def nonempty_reason(cls, value):
        if not value.strip():
            raise ValueError('Укажите основание операции')
        return value.strip()


class DistributionInput(OperationInput):
    rows: list[RowInput] = Field(min_length=1, max_length=50)


class ReturnInput(OperationInput):
    quantity: Quantity


class TransferInput(OperationInput):
    allocationId: Annotated[int, Field(strict=True, gt=0, le=9223372036854775807)]
    toProjectId: Id
    quantity: Quantity


class TransferReceiptInput(OperationInput):
    quantity: Annotated[Decimal, Field(ge=0, lt=Decimal('100000000'), decimal_places=6, allow_inf_nan=False)]
    expectedQuantity: Quantity

    @model_validator(mode='after')
    def accepted_not_above_expected(self):
        if self.quantity > self.expectedQuantity:
            raise ValueError('Принятое количество превышает ожидаемое')
        return self


def decimal_text(value):
    return format(Decimal(value).normalize(), 'f')


def payload_hash(data, kind):
    def canonical(value):
        if isinstance(value, Decimal):
            return decimal_text(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {key: canonical(item) for key, item in value.items()}
        if isinstance(value, list):
            return [canonical(item) for item in value]
        return value
    raw = json.dumps({'kind': kind, 'payload': canonical(data.model_dump())},
                     sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def conflict(detail):
    raise HTTPException(409, detail)


def validate_source(lot, receipt):
    """Only identity conversion is supported initially; never infer package ratios."""
    if (lot['status'] != 'active' or lot['warehouse_target'] != 'main'
            or lot['warehouse_location'] != MAIN):
        conflict('Нужна активная партия основного склада')
    if receipt.get('status') == 'Аннулирована':
        conflict('Исходная накладная аннулирована')
    location = str(receipt.get('project') or '').strip() or str(receipt.get('location') or '').strip()
    if location != MAIN:
        conflict('Исходная накладная не относится к основному складу')
    try:
        items = receipt['items']
        if isinstance(items, str):
            items = json.loads(items, parse_float=Decimal)
        index = lot['invoice_line_index']
        if not isinstance(items, list) or not isinstance(index, int) or index < 0:
            raise ValueError()
        item = items[index]
        name = str(item.get('name') or item.get('materialName') or item.get('title') or '').strip()
        unit = str(item.get('unit') or 'шт').strip()
        qty = Decimal(str(item['quantity']))
        document_qty = Decimal(str(item.get('documentQuantity', item['quantity'])))
        document_unit = str(item.get('documentUnit') or unit).strip()
        received = Decimal(lot['received_quantity'])
        available = Decimal(lot['available_quantity'])
        if not all(x.is_finite() for x in (qty, document_qty, received, available)):
            raise ValueError()
        if (not name or name != lot['material_name'] or unit != lot['unit']
                or qty <= 0 or qty != received or not 0 <= available <= received
                or document_qty != lot['document_quantity'] or document_unit != lot['document_unit']
                or document_unit != unit or document_qty != qty):
            raise ValueError()
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, InvalidOperation):
        conflict('Строка накладной не подтверждает партию или преобразование единиц не поддерживается')
