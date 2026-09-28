"""Leadership can retire a contract without changing issued documents."""
from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field

class ArchiveDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    archived: bool = Field(strict=True)
    expectedVersion: int = Field(strict=True, ge=0, lt=2147483647)

def register_contract_archive(app, deps):
    @app.put('/supplier-contract-registry/{id}/archive')
    def decide(id: Annotated[int, Path(gt=0, le=2147483647)], data: ArchiveDecision,
               current_user: dict = Depends(deps['get_current_user']),
               x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        conn = deps['get_db']()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            context = deps['resolve_work_company_context'](cur, current_user, None, 'update',
                x_company_id=x_company_id, x_company_mode=x_company_mode)
            actors = deps['effective_company_actors'](current_user, context)
            if context.get('mode') != 'company' or len(actors) != 1:
                raise HTTPException(403, 'Выберите одну компанию')
            actor = actors[0]
            company = actor.get('companyId')
            if not company or company != context.get('companyId') or actor.get('role') not in ('директор','зам_директора'):
                raise HTTPException(403, 'Архивировать договоры может руководство компании')
            # Same serialization order as contract review; never lock an offer here.
            cur.execute('SELECT pg_advisory_xact_lock(73164,%s)', (company,))
            cur.execute('SELECT archived,state_version FROM supplier_contract_registry WHERE id=%s AND company_id=%s FOR UPDATE', (id,company))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, 'Договор не найден в выбранной компании')
            archived, version = row
            if version != data.expectedVersion:
                raise HTTPException(409, 'Статус договора уже изменён. Обновите список')
            if archived != data.archived:
                version += 1
                cur.execute('UPDATE supplier_contract_registry SET archived=%s,state_version=%s WHERE id=%s AND company_id=%s', (data.archived,version,id,company))
                cur.execute('INSERT INTO supplier_contract_registry_events (registry_id,company_id,version,archived,actor_id,actor_name) VALUES (%s,%s,%s,%s,%s,%s)',
                    (id,company,version,data.archived,current_user['id'],str(actor.get('name') or current_user.get('name') or '')))
            conn.commit()
            return {'registryId':id,'companyId':company,'archived':data.archived,'stateVersion':version}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
