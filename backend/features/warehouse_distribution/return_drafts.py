"""Personal return draft CAS, consumed in the existing physical-return transaction."""
from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, Query
from pydantic import Field, field_validator, model_validator
from psycopg2.extras import Json
from .models import StrictInput, ReturnInput, MAX_ID
from .drafts import DraftSave
from .service import allocation_view

EMPTY=dict(allocationId=None,quantity='',reason='')

class ReturnDraftDocument(StrictInput):
    allocationId: Optional[Annotated[int,Field(strict=True,gt=0,le=9007199254740991)]]=None
    quantity: str=Field(strict=True,max_length=100)
    reason: str=Field(strict=True,max_length=1000)
    @field_validator('quantity','reason')
    @classmethod
    def text_only(cls,value):
        if '\x00' in value:raise ValueError('Недопустимый символ')
        return value
    @model_validator(mode='after')
    def closed_is_empty(self):
        if self.allocationId is None and (self.quantity or self.reason):
            raise ValueError('Для возврата выберите исходное распределение')
        return self

class ReturnDraftSave(DraftSave):
    document: ReturnDraftDocument

def require_schema(cur):
    cur.execute("SELECT to_regclass('warehouse_return_drafts') AS relation")
    if not cur.fetchone()['relation']:
        raise HTTPException(503,'Серверные черновики возвратов ещё не установлены. Не закрывайте страницу с правками.')

def conflict():
    raise HTTPException(409,dict(code='warehouse_return_draft_conflict',message='Черновик возврата изменён в другой вкладке или уже проведён. Правки остаются в форме; автоматической перезаписи нет.'))

def read(cur,company_id,user_id,lock=False):
    cur.execute('SELECT * FROM warehouse_return_drafts WHERE company_id=%s AND user_id=%s'+(' FOR UPDATE' if lock else ''),(company_id,user_id))
    return cur.fetchone()

def source(cur,company_id,allocation_id):
    cur.execute('SELECT * FROM warehouse_distribution_allocations WHERE company_id=%s AND id=%s',(company_id,allocation_id))
    return cur.fetchone()

def view(cur,company_id,user_id,row):
    document=row['document'] if row else EMPTY
    allocation=source(cur,company_id,document['allocationId']) if document['allocationId'] else None
    return dict(companyId=company_id,userId=user_id,revision=row['revision'] if row else 0,document=document,
        source=allocation_view(cur,allocation) if allocation else None,
        lastOperation=dict(operationId=row['last_operation_id'],requestId=str(row['last_return_request_id'])) if row and row['last_operation_id'] else None)

def save(cur,data,user_id):
    require_schema(cur);document=data.document.model_dump()
    if document['allocationId'] and not source(cur,data.companyId,document['allocationId']):
        raise HTTPException(404,'Распределение возврата недоступно в выбранной компании')
    cur.execute('''INSERT INTO warehouse_return_drafts(company_id,user_id,document) VALUES(%s,%s,%s)
        ON CONFLICT(company_id,user_id) DO NOTHING''',(data.companyId,user_id,Json(EMPTY)))
    row=read(cur,data.companyId,user_id,True)
    if str(row['last_save_request_id'])==str(data.requestId):
        if row['revision']!=data.expectedRevision+1 or row['document']!=document:conflict()
        return view(cur,data.companyId,user_id,row)
    if row['revision']!=data.expectedRevision:conflict()
    cur.execute('''UPDATE warehouse_return_drafts SET document=%s,revision=revision+1,last_save_request_id=%s,
        updated_at=now() WHERE company_id=%s AND user_id=%s RETURNING *''',
        (Json(document),str(data.requestId),data.companyId,user_id))
    return view(cur,data.companyId,user_id,cur.fetchone())

def return_saved(cur,data,actor,allocation_id,revision,execute):
    require_schema(cur)
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(1464095564,data.companyId))
    cur.execute('SELECT id FROM warehouse_distribution_operations WHERE company_id=%s AND request_id=%s',(data.companyId,str(data.requestId)))
    if cur.fetchone():return execute() # Existing writer validates kind, allocation and payload; do not clear a newer draft.
    row=read(cur,data.companyId,actor['id'],True)
    if not row or row['revision']!=revision or row['document']['allocationId']!=allocation_id:conflict()
    try:
        saved=ReturnInput(companyId=data.companyId,requestId=data.requestId,quantity=row['document']['quantity'],reason=row['document']['reason'])
    except ValueError:conflict()
    if saved.model_dump()!=data.model_dump():conflict()
    result=execute()
    cur.execute('''UPDATE warehouse_return_drafts SET document=%s,revision=revision+1,last_save_request_id=NULL,
        last_operation_id=%s,last_return_request_id=%s,updated_at=now() WHERE company_id=%s AND user_id=%s''',
        (Json(EMPTY),result['operationId'],str(data.requestId),data.companyId,actor['id']))
    return result

def register_routes(router,deps,transaction,authorize):
    @router.get('/return-draft')
    def get_draft(companyId: Annotated[Optional[int],Query(gt=0,le=MAX_ID)]=None,
        user: dict=Depends(deps['get_current_user']),
        header_id: Annotated[Optional[str],Header(alias='X-Company-Id')]=None,
        header_mode: Annotated[Optional[str],Header(alias='X-Company-Mode')]=None):
        with transaction(write=True) as cur:
            company_id,actor=authorize(cur,user,companyId,True,header_id,header_mode)
            require_schema(cur)
            return view(cur,company_id,actor['id'],read(cur,company_id,actor['id']))
    @router.put('/return-draft')
    def put_draft(data: ReturnDraftSave,user: dict=Depends(deps['get_current_user']),
        header_id: Annotated[Optional[str],Header(alias='X-Company-Id')]=None,
        header_mode: Annotated[Optional[str],Header(alias='X-Company-Mode')]=None):
        with transaction(write=True) as cur:
            _,actor=authorize(cur,user,data.companyId,True,header_id,header_mode)
            return save(cur,data,actor['id'])
