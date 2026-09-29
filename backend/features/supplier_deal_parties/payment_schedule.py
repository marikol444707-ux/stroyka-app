"""Reviewed percentages, never inferred from free text or bank transactions."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaymentStage(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    percentBasisPoints: int = Field(strict=True, gt=0, le=10000)
    event: Literal['invoice_issued', 'before_shipment', 'after_acceptance']
    daysAfter: int = Field(strict=True, ge=0, le=3650)


class PaymentSchedule(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schemaVersion: int = Field(strict=True, ge=1, le=1)
    stages: list[PaymentStage] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def coherent_stages(self):
        if sum(stage.percentBasisPoints for stage in self.stages) != 10000:
            raise ValueError('Сумма этапов должна быть ровно 100%')
        rank = {'invoice_issued': 0, 'before_shipment': 1, 'after_acceptance': 2}
        keys = [(rank[s.event], s.daysAfter) for s in self.stages]
        if keys != sorted(keys):
            raise ValueError('Этапы должны идти в порядке событий и сроков')
        if any(s.event == 'before_shipment' and s.daysAfter != 0 for s in self.stages):
            raise ValueError('До отгрузки — условие, а не дата: daysAfter должен быть 0')
        return self


def schedule_amounts(schedule, amount):
    try:
        total = Decimal(str(amount))
        if not total.is_finite() or total <= 0 or total > Decimal('999999999999.99') or total != total.quantize(Decimal('.01')):
            raise ValueError('Некорректная сумма счёта для графика')
    except (InvalidOperation, ValueError) as error:
        raise ValueError('Сумма графика должна быть положительной и точной до копейки') from error
    amounts, cumulative, previous = [], 0, Decimal('0')
    for stage in schedule.stages:
        cumulative += stage.percentBasisPoints
        rounded = (total * cumulative / 10000).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        amounts.append(rounded - previous)
        previous = rounded
    return amounts


def advance_amount(snapshot, amount):
    if snapshot.get('paymentSchedule') is None:
        return None
    schedule = PaymentSchedule.model_validate(snapshot['paymentSchedule'])
    return sum((value for stage, value in zip(schedule.stages, schedule_amounts(schedule, amount))
                if stage.event != 'after_acceptance'), Decimal('0'))


def schedule_paid_amount(value):
    try:
        paid = Decimal(str(value))
        if not paid.is_finite() or paid < 0 or paid > Decimal('999999999999.99') or paid != paid.quantize(Decimal('.01')):
            raise ValueError('Некорректная оплаченная сумма')
        return paid
    except (InvalidOperation, ValueError) as error:
        raise ValueError('Оплата должна быть неотрицательной и точной до копейки') from error


def schedule_projection(snapshot, amount, invoice_date=None, acceptance_date=None):
    """Planned amounts only: no invented receipt dates or per-stage paid status."""
    if snapshot.get('paymentSchedule') is None:
        return None
    schedule = PaymentSchedule.model_validate(snapshot['paymentSchedule'])
    stages = []
    for stage, value in zip(schedule.stages, schedule_amounts(schedule, amount)):
        base = invoice_date if stage.event == 'invoice_issued' else acceptance_date if stage.event == 'after_acceptance' else None
        try:
            due_date = (dt.date.fromisoformat(str(base)[:10]) + dt.timedelta(days=stage.daysAfter)).isoformat() if base else None
        except (ValueError, OverflowError) as error:
            raise ValueError('Дата этапа выходит за допустимый календарный диапазон') from error
        stages.append({**stage.model_dump(), 'amount': format(value, '.2f'), 'dueDate': due_date})
    return {'schemaVersion': 1, 'currency': 'RUB', 'paymentAllocationStatus': 'not_allocated', 'stages': stages}


def invoice_advance_amount(cur, invoice_id, company_id, amount):
    # JSON lookup remains compatible with installations predating migration 0011.
    cur.execute("SELECT to_jsonb(si)->>'contract_version_id' FROM supplier_invoices si WHERE id=%s AND company_id=%s",
                (invoice_id, company_id))
    row = cur.fetchone()
    if not row or not row[0]:
        return None
    cur.execute('SELECT snapshot_json FROM supplier_contract_versions WHERE id=%s AND company_id=%s', (int(row[0]), company_id))
    contract = cur.fetchone()
    if not contract:
        raise ValueError('Договор счёта не найден')
    return advance_amount(contract[0], amount)
