"""One personal transfer form; saving never posts stock, completion consumes it atomically."""
from typing import Annotated, Literal, Optional
from fastapi import Depends, Header, HTTPException, Query
from pydantic import Field, field_validator, model_validator
from psycopg2.extras import Json
from .models import StrictInput, Id, MAX_ID, TransferInput, TransferReceiptInput
from .drafts import DraftSave
from .service import allocation_view
from . import transfers

SafeId = Annotated[int, Field(strict=True, gt=0, le=9007199254740991)]
EMPTY = dict(kind=None, allocationId=None, transferId=None, toProjectId=None,
             quantity='', expectedQuantity='', reason='')

class TransferDraftDocument(StrictInput):
    kind: Optional[Literal['dispatch', 'receipt']] = None
    allocationId: Optional[SafeId] = None
    transferId: Optional[SafeId] = None
    toProjectId: Optional[Id] = None
    quantity: str = Field(strict=True, max_length=100)
    expectedQuantity: str = Field(strict=True, max_length=100)
    reason: str = Field(strict=True, max_length=1000)

    @field_validator('quantity', 'expectedQuantity', 'reason')
    @classmethod
    def text_only(cls, value):
        if '\x00' in value:
            raise ValueError('Недопустимый символ')
        return value

    @model_validator(mode='after')
    def coherent_form(self):
        if self.kind is None:
            if self.model_dump() != EMPTY:
                raise ValueError('Закрытый черновик должен быть пустым')
        elif self.kind == 'dispatch':
            if not self.allocationId or self.transferId or self.expectedQuantity:
                raise ValueError('Для отправки выберите исходное распределение')
        elif not self.transferId or self.allocationId or self.toProjectId:
            raise ValueError('Для приёмки выберите перемещение')
        return self

class TransferDraftSave(DraftSave):
    document: TransferDraftDocument

def require_schema(cur):
    cur.execute("SELECT to_regclass('warehouse_transfer_drafts') AS relation")
    if not cur.fetchone()['relation']:
        raise HTTPException(503, 'Серверные черновики перемещений ещё не установлены. Не закрывайте страницу с правками.')

def conflict():
    raise HTTPException(409, dict(code='warehouse_transfer_draft_conflict', message='Черновик перемещения изменён в другой вкладке или уже проведён. Правки остаются в форме; автоматической перезаписи нет.'))

def read(cur, company_id, user_id, lock=False):
    cur.execute('SELECT * FROM warehouse_transfer_drafts WHERE company_id=%s AND user_id=%s'
                + (' FOR UPDATE' if lock else ''), (company_id, user_id))
    return cur.fetchone()

def source(cur, company_id, document):
    if document['kind'] is None:
        return None
    table, key = ('warehouse_distribution_allocations', 'allocationId') if document['kind'] == 'dispatch' else ('warehouse_distribution_transfers', 'transferId')
    cur.execute('SELECT * FROM ' + table + ' WHERE company_id=%s AND id=%s', (company_id, document[key]))
    return cur.fetchone()

def view(cur, company_id, user_id, row):
    document = row['document'] if row else EMPTY
    entity = source(cur, company_id, document)
    entity_view = (allocation_view(cur, entity) if document['kind'] == 'dispatch' else transfers.views(cur, [entity])[0]) if entity else None
    return dict(companyId=company_id, userId=user_id, revision=row['revision'] if row else 0,
                document=document, source=entity_view,
                lastOperation=dict(operationId=row['last_operation_id'], requestId=str(row['last_transfer_request_id'])) if row and row['last_operation_id'] else None)

def save(cur, data, user_id):
    require_schema(cur)
    document = data.document.model_dump()
    if document['kind'] and not source(cur, data.companyId, document):
        raise HTTPException(404, 'Источник перемещения недоступен в выбранной компании')
    if document['toProjectId']:
        cur.execute('SELECT id FROM projects WHERE company_id=%s AND id=%s', (data.companyId, document['toProjectId']))
        if not cur.fetchone():
            raise HTTPException(404, 'Объект назначения недоступен в выбранной компании')
    cur.execute('''INSERT INTO warehouse_transfer_drafts(company_id,user_id,document) VALUES(%s,%s,%s)
        ON CONFLICT(company_id,user_id) DO NOTHING''', (data.companyId, user_id, Json(EMPTY)))
    row = read(cur, data.companyId, user_id, True)
    if str(row['last_save_request_id']) == str(data.requestId):
        if row['revision'] != data.expectedRevision + 1 or row['document'] != document:
            conflict()
        return view(cur, data.companyId, user_id, row)
    if row['revision'] != data.expectedRevision:
        conflict()
    cur.execute('''UPDATE warehouse_transfer_drafts SET document=%s,revision=revision+1,
        last_save_request_id=%s,updated_at=now() WHERE company_id=%s AND user_id=%s RETURNING *''',
        (Json(document), str(data.requestId), data.companyId, user_id))
    return view(cur, data.companyId, user_id, cur.fetchone())

def perform_saved(cur, data, actor, revision, kind, transfer_id, execute):
    require_schema(cur)
    # Same lock order as stock writers. Replays verify their original payload and
    # preserve a draft created after a committed operation whose reply was lost.
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1464095564, data.companyId))
    cur.execute('SELECT id FROM warehouse_distribution_operations WHERE company_id=%s AND request_id=%s', (data.companyId, str(data.requestId)))
    if cur.fetchone():
        return execute()
    row = read(cur, data.companyId, actor['id'], True)
    if not row or row['revision'] != revision or row['document']['kind'] != kind:
        conflict()
    document = row['document']
    try:
        values = dict(companyId=data.companyId, requestId=data.requestId, quantity=document['quantity'], reason=document['reason'])
        if kind == 'dispatch':
            saved = TransferInput(**values, allocationId=document['allocationId'], toProjectId=document['toProjectId'])
        else:
            if document['transferId'] != transfer_id:
                conflict()
            saved = TransferReceiptInput(**values, expectedQuantity=document['expectedQuantity'])
    except ValueError:
        conflict()
    if saved.model_dump() != data.model_dump():
        conflict()
    result = execute()
    cur.execute('SELECT id FROM warehouse_distribution_operations WHERE company_id=%s AND request_id=%s', (data.companyId, str(data.requestId)))
    operation_id = cur.fetchone()['id']
    cur.execute('''UPDATE warehouse_transfer_drafts SET document=%s,revision=revision+1,last_save_request_id=NULL,
        last_operation_id=%s,last_transfer_request_id=%s,updated_at=now() WHERE company_id=%s AND user_id=%s''',
        (Json(EMPTY), operation_id, str(data.requestId), data.companyId, actor['id']))
    return result

def register_routes(router, deps, transaction, authorize, require_enabled):
    @router.get('/transfer-draft', dependencies=[Depends(require_enabled)])
    def get_draft(companyId: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
                  user: dict = Depends(deps['get_current_user']),
                  header_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
                  header_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None):
        with transaction(write=True) as cur:
            company_id, actor = authorize(cur, user, companyId, True, header_id, header_mode)
            require_schema(cur)
            return view(cur, company_id, actor['id'], read(cur, company_id, actor['id']))

    @router.put('/transfer-draft', dependencies=[Depends(require_enabled)])
    def put_draft(data: TransferDraftSave, user: dict = Depends(deps['get_current_user']),
                  header_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
                  header_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None):
        with transaction(write=True) as cur:
            _, actor = authorize(cur, user, data.companyId, True, header_id, header_mode)
            return save(cur, data, actor['id'])
