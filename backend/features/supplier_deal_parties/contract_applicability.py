"""Explicit reviewed contract scope and term; missing legacy data is unknown."""
import datetime as dt
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationError


class ContractApplicability(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['company', 'project']
    projectId: Optional[int] = Field(default=None, strict=True, gt=0, le=2147483647)
    term: Literal['open_ended', 'fixed']
    startsOn: dt.date
    endsOn: Optional[dt.date] = None

    @model_validator(mode='after')
    def coherent(self):
        if (self.scope == 'project') != (self.projectId is not None):
            raise ValueError('Для договора объекта укажите объект')
        if (self.term == 'fixed') != (self.endsOn is not None):
            raise ValueError('Укажите срок договора или выберите бессрочный')
        if self.endsOn is not None and self.endsOn < self.startsOn:
            raise ValueError('Окончание договора раньше начала')
        return self


def offer_project(cur, offer):
    # The offer already has an authorized company. Ambiguous legacy names cannot
    # establish an exact project scope, even within that company.
    cur.execute('SELECT id,name FROM projects WHERE company_id=%s AND name=%s LIMIT 2',
                (offer['company_id'], offer.get('project') or ''))
    rows = cur.fetchall()
    return dict(rows[0]) if len(rows) == 1 else None


def eligible_applicability(snapshot, project_id=None, today=None):
    try:
        value = ContractApplicability.model_validate(snapshot.get('applicability'))
    except (ValidationError, TypeError):
        return False
    today = today or dt.datetime.now(ZoneInfo('Europe/Moscow')).date()
    return (value.startsOn <= today and (value.endsOn is None or today <= value.endsOn)
            and (value.scope == 'company' or value.projectId == project_id))
