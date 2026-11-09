"""Personal draft CAS; completion shares the existing stock transaction."""
from typing import Annotated, Optional
from uuid import UUID
from fastapi import Depends, Header, HTTPException, Query
from psycopg2.extras import Json
from pydantic import Field, field_validator
from .models import StrictInput, Id, MAX_ID, DistributionInput

EMPTY={'rows':[{'lotId':None,'projectId':None,'quantity':''}],'reason':''}

class DraftRow(StrictInput):
    lotId: Optional[Id]=None
    projectId: Optional[Id]=None
    quantity: str=Field(strict=True,max_length=100)
    @field_validator('quantity')
    @classmethod
    def text_only(cls,value):
        if '\x00' in value:raise ValueError('Недопустимый символ')
        return value

class DraftDocument(StrictInput):
    rows: list[DraftRow]=Field(min_length=1,max_length=50)
    reason: str=Field(strict=True,max_length=1000)
    @field_validator('reason')
    @classmethod
    def text_only(cls,value):
        if '\x00' in value:raise ValueError('Недопустимый символ')
        return value

class DraftSave(StrictInput):
    companyId: Id
    expectedRevision: int=Field(strict=True,ge=0,le=9007199254740990)
    requestId: UUID
    document: DraftDocument


def require_schema(cur):
    cur.execute("SELECT to_regclass('warehouse_batch_drafts') AS relation")
    if not cur.fetchone()['relation']:
        raise HTTPException(503,'Серверные черновики ещё не установлены. Не закрывайте страницу с правками.')


def conflict():
    raise HTTPException(409,dict(code='warehouse_draft_conflict',message='Черновик изменён в другой вкладке или уже проведён. Ваши правки сохранены в форме; автоматической перезаписи нет.'))


def read(cur,company_id,user_id,lock=False):
    cur.execute('SELECT * FROM warehouse_batch_drafts WHERE company_id=%s AND user_id=%s'+(' FOR UPDATE' if lock else ''),(company_id,user_id))
    return cur.fetchone()


def view(cur,company_id,user_id,row):
    document=row['document'] if row else EMPTY
    ids=sorted({r['lotId'] for r in document['rows'] if r['lotId']})
    cur.execute('''SELECT l.id,l.warehouse_invoice_id,l.invoice_line_index,l.material_name,l.unit,i.number
       FROM warehouse_receipt_lots l JOIN warehouse_invoices i ON i.id=l.warehouse_invoice_id AND i.company_id=l.company_id
       WHERE l.company_id=%s AND l.id=ANY(%s) ORDER BY l.id''',(company_id,ids))
    sources=[dict(lotId=r['id'],warehouseInvoiceId=r['warehouse_invoice_id'],invoiceLineIndex=r['invoice_line_index'],
        materialName=r['material_name'],unit=r['unit'],invoiceNumber=str(r['number'] or ''),availabilityUnknown=True) for r in cur.fetchall()]
    return dict(companyId=company_id,userId=user_id,revision=row['revision'] if row else 0,document=document,sources=sources,
        lastOperation=dict(operationId=row['last_operation_id'],requestId=str(row['last_issue_request_id'])) if row and row['last_operation_id'] else None)


def save(cur,data,user_id):
    require_schema(cur)
    document=data.document.model_dump()
    # Values identify exact entities. Names and cached balances are never trusted.
    for table,key in (('warehouse_receipt_lots','lotId'),('projects','projectId')):
        ids=sorted({r[key] for r in document['rows'] if r[key]})
        cur.execute('SELECT id FROM '+table+' WHERE company_id=%s AND id=ANY(%s)',(data.companyId,ids))
        if {r['id'] for r in cur.fetchall()}!=set(ids):
            raise HTTPException(404,'Партия или объект черновика недоступны в выбранной компании')
    cur.execute('''INSERT INTO warehouse_batch_drafts(company_id,user_id,document) VALUES(%s,%s,%s)
        ON CONFLICT(company_id,user_id) DO NOTHING''',(data.companyId,user_id,Json(EMPTY)))
    row=read(cur,data.companyId,user_id,True)
    if str(row['last_save_request_id'])==str(data.requestId):
        if row['revision']!=data.expectedRevision+1 or row['document']!=document:conflict()
        return view(cur,data.companyId,user_id,row)
    if row['revision']!=data.expectedRevision:conflict()
    cur.execute('''UPDATE warehouse_batch_drafts SET document=%s,revision=revision+1,last_save_request_id=%s,
        updated_at=now() WHERE company_id=%s AND user_id=%s RETURNING *''',
        (Json(document),str(data.requestId),data.companyId,user_id))
    return view(cur,data.companyId,user_id,cur.fetchone())


def issue_saved(cur,data,actor,revision,execute):
    require_schema(cur)
    # Same order as the warehouse writer, before the per-user row lock.
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(1464095564,data.companyId))
    cur.execute('SELECT id FROM warehouse_distribution_operations WHERE company_id=%s AND request_id=%s',
        (data.companyId,str(data.requestId)))
    if cur.fetchone():
        # Existing writer verifies payload hash/quality/rights; never clears a newer draft.
        return execute()
    row=read(cur,data.companyId,actor['id'],True)
    if not row or row['revision']!=revision:conflict()
    try:
        saved=DistributionInput(companyId=data.companyId,requestId=data.requestId,**row['document'])
    except ValueError:conflict()
    if saved.model_dump()!=data.model_dump():conflict()
    result=execute()
    cur.execute('''UPDATE warehouse_batch_drafts SET document=%s,revision=revision+1,last_save_request_id=NULL,
        last_operation_id=%s,last_issue_request_id=%s,updated_at=now() WHERE company_id=%s AND user_id=%s''',
        (Json(EMPTY),result['operationId'],str(data.requestId),data.companyId,actor['id']))
    return result


def register_routes(router,deps,transaction,authorize):
    @router.get('/draft')
    def get_draft(companyId: Annotated[Optional[int],Query(gt=0,le=MAX_ID)]=None,
        user: dict=Depends(deps['get_current_user']),
        header_id: Annotated[Optional[str],Header(alias='X-Company-Id')]=None,
        header_mode: Annotated[Optional[str],Header(alias='X-Company-Mode')]=None):
        with transaction(write=True) as cur:
            company_id,actor=authorize(cur,user,companyId,True,header_id,header_mode)
            require_schema(cur)
            return view(cur,company_id,actor['id'],read(cur,company_id,actor['id']))

    @router.put('/draft')
    def put_draft(data: DraftSave,user: dict=Depends(deps['get_current_user']),
        header_id: Annotated[Optional[str],Header(alias='X-Company-Id')]=None,
        header_mode: Annotated[Optional[str],Header(alias='X-Company-Mode')]=None):
        with transaction(write=True) as cur:
            _,actor=authorize(cur,user,data.companyId,True,header_id,header_mode)
            return save(cur,data,actor['id'])
