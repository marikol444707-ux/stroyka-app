"""Choose an existing checked contract without repeating its review."""
from typing import Annotated, Optional
import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field
from .automatic_reuse import build_automatic_reuse

class ContractSelection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    contractId:int=Field(strict=True,gt=0,le=2147483647)


def register_reuse_routes(app,deps):
    reuse=build_automatic_reuse(deps)

    def execute(id,user,company,mode,selection=None):
        conn=deps['get_db']();conn.autocommit=False
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result=reuse(cur,id,user,company,mode,selected_id=selection,list_only=selection is None)
            if selection is None:
                return {'items':result or []}
            if not result:
                raise HTTPException(409,'Договор больше не подходит или уже выбран другой. Обновите список.')
            cur.execute('SELECT company_id FROM supplier_contract_versions WHERE id=%s',(result,))
            company_id=cur.fetchone()['company_id']
            conn.commit()
            return {'id':result,'offerId':id,'companyId':company_id,'sourceContractId':selection}
        except Exception:
            conn.rollback();raise
        finally:
            if selection is None:conn.rollback()
            cur.close();conn.close()

    @app.get('/supplier-offers/{id}/saved-contracts')
    def options(id:Annotated[int,Path(gt=0,le=2147483647)],
                user:dict=Depends(deps['get_current_user']),
                company:Optional[str]=Header(None,alias='X-Company-Id'),
                mode:Optional[str]=Header(None,alias='X-Company-Mode')):
        return execute(id,user,company,mode)

    @app.post('/supplier-offers/{id}/saved-contracts')
    def select(id:Annotated[int,Path(gt=0,le=2147483647)],data:ContractSelection,
               user:dict=Depends(deps['get_current_user']),
               company:Optional[str]=Header(None,alias='X-Company-Id'),
               mode:Optional[str]=Header(None,alias='X-Company-Mode')):
        return execute(id,user,company,mode,data.contractId)
