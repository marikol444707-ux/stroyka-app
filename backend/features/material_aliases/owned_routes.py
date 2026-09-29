"""Explicit owned editor namespace; never interprets legacy numeric mutation IDs."""
from datetime import datetime
import hashlib
import re
from typing import Optional, List

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, conint, constr, field_validator

from .runtime import owned_aliases_enabled
from .scoped import require_alias_actor, list_aliases, save_alias, deactivate_alias


def parse_alias_ref(value):
    if not isinstance(value, str) or not re.fullmatch(r'cma:[1-9][0-9]{0,18}', value):
        raise ValueError('Требуется идентификатор нового справочника cma:…')
    number = int(value[4:])
    if number > 9223372036854775807:
        raise ValueError('Идентификатор вне допустимого диапазона')
    return number


class AliasInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    companyId: conint(strict=True, gt=0, le=2147483647)
    projectId: Optional[conint(strict=True, gt=0, le=2147483647)] = None
    aliasName: constr(strict=True, strip_whitespace=True, min_length=1, max_length=500)
    canonicalName: constr(strict=True, strip_whitespace=True, min_length=1, max_length=500)
    canonicalUnit: constr(strict=True, strip_whitespace=True, max_length=50) = ''
    expectedAliasId: Optional[str] = Field(...)

    @field_validator('expectedAliasId')
    @classmethod
    def valid_ref(cls, value):
        if value is not None:
            parse_alias_ref(value)
        return value

class AliasOutput(BaseModel):
    id: str
    companyId: int
    projectId: Optional[int]
    aliasName: str
    canonicalName: str
    canonicalUnit: str
    previousId: Optional[str]
    createdById: int
    createdAt: datetime
    active: bool


class AliasPage(BaseModel):
    items: List[AliasOutput]
    limit: int
    offset: int
    revision: str


class AliasDeleted(BaseModel):
    ok: bool


def alias_output(row):
    return AliasOutput(id='cma:'+str(row['id']), companyId=row['company_id'], projectId=row['project_id'],
        aliasName=row['alias_name'], canonicalName=row['canonical_name'], canonicalUnit=row['canonical_unit'],
        previousId='cma:'+str(row['previous_id']) if row['previous_id'] else None,
        createdById=row['created_by_id'], createdAt=row['created_at'], active=row['active'])


def alias_page(cur, access, project_id, limit, offset):
    company_id = access.actor['companyId']
    # One read page and its revision must observe the same writer boundary.
    cur.execute('SELECT pg_advisory_xact_lock_shared(%s,%s)', (913041, company_id))
    rows = list_aliases(cur, access, project_id=project_id, limit=limit, offset=offset)
    cur.execute('''SELECT COALESCE(MAX(id),0) AS latest, COUNT(*) FILTER (WHERE active) AS active_count
        FROM company_material_aliases WHERE company_id=%s''', (company_id,))
    version = cur.fetchone()
    revision = hashlib.sha256(f"{company_id}:{version['latest']}:{version['active_count']}".encode()).hexdigest()
    return AliasPage(items=[alias_output(row) for row in rows], limit=limit, offset=offset, revision=revision)


def register_owned_aliases(app, deps):
    def execute(user, company_id, header_id, header_mode, write, operation):
        if not owned_aliases_enabled():
            raise HTTPException(404, 'Справочник компаний не включён')
        if str(header_mode or '').strip().lower() == 'all_companies':
            raise HTTPException(400, 'Для справочника выберите одну компанию')
        conn = deps['get_db']()
        try:
            conn.set_session(isolation_level='READ COMMITTED', autocommit=False)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SET LOCAL lock_timeout='3s'")
                cur.execute("SET LOCAL statement_timeout='15s'")
                access = require_alias_actor(cur, user, company_id=company_id,
                    x_company_id=header_id, x_company_mode=header_mode, write=write,
                    allowed_roles=tuple(deps['write_roles' if write else 'read_roles']),
                    full_project_roles=tuple(deps.get('full_project_roles', ())),
                    platform_staff_roles=tuple(deps.get('platform_staff_roles', ())),
                    client_account_roles=tuple(deps.get('client_account_roles', ())))
                result = operation(cur, access)
            if write:
                conn.commit()
            else:
                conn.rollback()
            return result
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise HTTPException(503, 'Не удалось выполнить операцию со справочником') from None
        finally:
            conn.close()

    @app.get('/company-material-aliases', response_model=AliasPage)
    def read(response: Response, companyId: int = Query(..., gt=0, le=2147483647),
             projectId: Optional[int] = Query(None, gt=0, le=2147483647),
             limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=2147483647),
             current_user: dict = Depends(deps['get_current_user']),
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        response.headers['Cache-Control'] = 'private, no-store'
        return execute(current_user, companyId, x_company_id, x_company_mode, False,
            lambda cur, access: alias_page(cur, access, projectId, limit, offset))

    @app.post('/company-material-aliases', response_model=AliasOutput, status_code=201)
    def save(data: AliasInput, response: Response, current_user: dict = Depends(deps['get_current_user']),
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        response.headers['Cache-Control'] = 'private, no-store'
        return execute(current_user, data.companyId, x_company_id, x_company_mode, True,
            lambda cur, access: alias_output(save_alias(cur, access, alias_name=data.aliasName,
                canonical_name=data.canonicalName, canonical_unit=data.canonicalUnit, project_id=data.projectId,
                expected_previous_id=parse_alias_ref(data.expectedAliasId) if data.expectedAliasId else None)))

    @app.delete('/company-material-aliases/{alias_ref}', response_model=AliasDeleted)
    def deactivate(alias_ref: str, response: Response, companyId: int = Query(..., gt=0, le=2147483647),
                   current_user: dict = Depends(deps['get_current_user']),
                   x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                   x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        response.headers['Cache-Control'] = 'private, no-store'
        try:
            alias_id = parse_alias_ref(alias_ref)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

        def operation(cur, access):
            deactivate_alias(cur, access, alias_id)
            return AliasDeleted(ok=True)

        return execute(current_user, companyId, x_company_id, x_company_mode, True, operation)
