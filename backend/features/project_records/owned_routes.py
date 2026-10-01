"""Owned documents and correspondence; measurement routes remain separate."""
import json

from fastapi import Depends, HTTPException, Request

from ..customer_contract_parties.storage import freeze_customer_contract_if_ready
from ..customer_contract_parties.customer_act_storage import (
    freeze_customer_act_if_ready,
    is_customer_work_act,
)
from ..customer_contract_parties.snapshot import is_customer_contract


DOCUMENT_FIELDS = {
    'side':'side','docType':'doc_type','number':'number','docDate':'doc_date',
    'counterparty':'counterparty','signStatus':'sign_status','scanUrl':'scan_url',
    'amount':'amount','notes':'notes','basisContractDocumentId':'basis_contract_document_id',
}
LETTER_FIELDS = {
    'side':'side','direction':'direction','subject':'subject','body':'body',
    'counterparty':'counterparty','letterDate':'letter_date','fileUrl':'file_url',
}


def register_owned_record_routes(app, deps):
    read_roles = tuple(deps['read_roles'])
    write_roles = tuple(deps['write_roles'])
    workers = tuple(deps['worker_execution_roles'])
    authenticated = deps['get_current_user']

    def normalized_basis(data, side, document_type):
        value = data.get('basisContractDocumentId')
        if value in (None, ''):
            return None
        if not is_customer_work_act(side, document_type):
            raise HTTPException(422, 'Договор-основание можно выбрать только для КС-2 или КС-3 заказчика')
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise HTTPException(422, 'Некорректный договор-основание')
        if value <= 0:
            raise HTTPException(422, 'Некорректный договор-основание')
        return value

    def register_kind(path, table, fields, actor_key, actor_column, defaults, void_column, void_value):
        @app.get(path)
        def list_records(project_name: str = None, _current_user: dict = Depends(authenticated), request: Request = None):
            scope = deps['record_scope']
            with scope.transaction(_current_user, request, read_roles) as (cur, actors):
                clauses, params = [], []
                customer_companies = set()
                for actor in actors:
                    where, values = scope.visible([actor], read_roles)
                    role = actor.get('role')
                    if role == 'заказчик':
                        where += " AND r.side='customer'"
                        if table == 'project_letters':
                            where += " AND r.published_at IS NOT NULL AND r.delivery_status IN ('sent','received')"
                        customer_companies.add(int(actor.get('companyId') or actor.get('company_id')))
                    elif role in workers:
                        where += " AND r.side='contractor'"
                        if table == 'project_documents':
                            where += ' AND (r.counterparty=%s OR r.created_by_user_id=%s)'
                            values.extend([actor.get('name') or '',actor.get('id')])
                    clauses.append('(' + where + ')'); params.extend(values)
                where = '(' + (' OR '.join(clauses) or 'FALSE') + ')'
                if project_name:
                    where += ' AND p.name=%s'; params.append(project_name)
                where += f' AND COALESCE(r.{void_column},\'\')<>%s'; params.append(void_value)
                columns = ','.join('r.'+column for column in fields.values())
                correction_columns = ''
                correction_keys = []
                snapshot_columns = ''
                snapshot_keys = []
                if table == 'project_documents':
                    snapshot_columns = (',r.party_snapshot_json,r.party_snapshot_hash,'
                        'r.party_snapshot_frozen_at,r.customer_client_id,'
                        'r.contract_version,r.revises_document_id')
                    snapshot_keys = ['partySnapshot','partySnapshotHash',
                        'partySnapshotFrozenAt','customerClientId',
                        'contractVersion','revisesDocumentId']
                if table == 'project_letters':
                    snapshot_columns = (',r.party_snapshot_json,r.party_snapshot_hash,'
                        'r.party_snapshot_frozen_at,r.customer_client_id')
                    snapshot_keys = ['partySnapshot','partySnapshotHash',
                        'partySnapshotFrozenAt','customerClientId']
                    correction_columns = (',r.correction_reason,r.correction_requested_at,'
                        'r.corrected_by_letter_id,r.replaces_letter_id,r.delivery_status,'
                        'r.published_at,r.published_by_name')
                    correction_keys = ['correctionReason','correctionRequestedAt',
                        'correctedByLetterId','replacesLetterId','deliveryStatus',
                        'publishedAt','publishedByName']
                cur.execute('SELECT r.id,p.name,' + columns + f',r.{actor_column},r.created_at,r.company_id,r.project_id '
                            + snapshot_columns + correction_columns + ' '
                            f'FROM {table} r JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id '
                            'WHERE ' + where + ' ORDER BY r.id DESC', params)
                rows = cur.fetchall()
            keys = ['id','projectName',*fields,actor_key,'createdAt','companyId','projectId',
                    *snapshot_keys,*correction_keys]
            result = []
            for row in rows:
                record = dict(zip(keys,row))
                for key in ('docDate','letterDate','createdAt','correctionRequestedAt','publishedAt'):
                    if key in record:
                        record[key] = str(record[key]) if record[key] else ''
                if 'partySnapshotFrozenAt' in record:
                    record['partySnapshotFrozenAt'] = str(record['partySnapshotFrozenAt']) if record['partySnapshotFrozenAt'] else ''
                if isinstance(record.get('partySnapshot'), str):
                    try:
                        record['partySnapshot'] = json.loads(record['partySnapshot'])
                    except (TypeError, ValueError):
                        record['partySnapshot'] = None
                if 'amount' in record:
                    record['amount'] = float(record['amount'] or 0)
                for key in (*fields,actor_key):
                    if record.get(key) is None:
                        record[key] = ''
                if record['companyId'] in customer_companies:
                    record.pop('notes',None)
                result.append(record)
            return result

        @app.post(path)
        def create_record(data: dict, _current_user: dict = Depends(authenticated), request: Request = None):
            scope = deps['record_scope']
            with scope.transaction(_current_user, request, write_roles, write=True) as (cur, actors):
                actor = actors[0]
                parent = scope.parent(cur, actor, data, write_roles)
                if table == 'project_letters' and data.get('side', defaults.get('side')) == 'customer':
                    raise HTTPException(409, 'Для заказчика используйте адресную отправку по объекту')
                contract_version = None
                revises_document_id = data.get('revisesDocumentId') if table == 'project_documents' else None
                if table == 'project_documents' and revises_document_id not in (None, ''):
                    try:
                        revises_document_id = int(revises_document_id)
                    except (TypeError, ValueError):
                        raise HTTPException(422, 'Некорректная исходная версия договора')
                    scope.record(cur, actor, table, revises_document_id, write_roles)
                    cur.execute('''SELECT d.project_id,d.company_id,d.side,d.doc_type,d.number,d.counterparty,
                                          COALESCE(d.contract_version,1),d.party_snapshot_json,d.customer_client_id,
                                          p.client_id AS project_client_id
                                     FROM project_documents d
                                     JOIN projects p ON p.id=d.project_id AND p.company_id=d.company_id
                                    WHERE d.id=%s''', (revises_document_id,))
                    source = cur.fetchone()
                    if not source:
                        raise HTTPException(404, 'Исходная версия договора не найдена')
                    source = dict(source) if isinstance(source, dict) else dict(zip(
                        ('project_id','company_id','side','doc_type','number','counterparty',
                         'contract_version','party_snapshot_json','customer_client_id','project_client_id'), source))
                    if (source['project_id'] != parent['id'] or source['company_id'] != parent['companyId']
                            or source['party_snapshot_json'] is None
                            or source['customer_client_id'] != source['project_client_id']
                            or not is_customer_contract(source['side'], source['doc_type'])):
                        raise HTTPException(409, 'Новая версия должна продолжать зафиксированный договор этого объекта')
                    data = {**data, 'side': source['side'], 'docType': source['doc_type'],
                            'number': source['number'], 'counterparty': source['counterparty']}
                    contract_version = int(source['contract_version']) + 1
                elif table == 'project_documents' and is_customer_contract(
                        data.get('side', defaults.get('side')), data.get('docType', '')):
                    contract_version = 1
                if table == 'project_documents':
                    side = data.get('side', defaults.get('side'))
                    document_type = data.get('docType', '')
                    data = {**data, 'basisContractDocumentId': normalized_basis(data, side, document_type)}
                values = [data.get(key, defaults.get(key,'')) for key in fields]
                for index,key in enumerate(fields):
                    if key in ('docDate','letterDate'):
                        values[index] = values[index] or None
                    if key == 'basisContractDocumentId':
                        values[index] = values[index] or None
                    if key == 'amount':
                        values[index] = values[index] or 0
                columns = ['project_name',*fields.values(),actor_column,'company_id','project_id','created_by_user_id']
                values = [parent['name'],*values,actor.get('name',''),parent['companyId'],parent['id'],actor['id']]
                if table == 'project_documents':
                    columns.extend(('contract_version','revises_document_id'))
                    values.extend((contract_version,revises_document_id))
                cur.execute(f'INSERT INTO {table} (' + ','.join(columns) + ') VALUES ('
                            + ','.join(['%s']*len(values)) + ') RETURNING id',values)
                record_id = cur.fetchone()[0]
                if table == 'project_documents':
                    side = data.get('side', defaults.get('side'))
                    document_type = data.get('docType', '')
                    if is_customer_contract(side, document_type):
                        freeze_customer_contract_if_ready(cur, record_id, actor)
                    elif is_customer_work_act(side, document_type):
                        freeze_customer_act_if_ready(cur, record_id, actor)
            return {'ok':True,'id':record_id}

        if table == 'project_documents':
            @app.put(path+'/{id}')
            def update_record(id: int, data: dict, _current_user: dict = Depends(authenticated), request: Request = None):
                scope = deps['record_scope']
                with scope.transaction(_current_user, request, write_roles, write=True) as (cur, actors):
                    scope.record(cur, actors[0], table, id, write_roles)
                    cur.execute('SELECT party_snapshot_json,side,doc_type,basis_contract_document_id FROM project_documents WHERE id=%s', (id,))
                    frozen = cur.fetchone()
                    if isinstance(frozen, dict):
                        frozen_snapshot = frozen.get('party_snapshot_json')
                        saved_side, saved_type = frozen.get('side'), frozen.get('doc_type')
                        saved_basis = frozen.get('basis_contract_document_id')
                    else:
                        frozen_snapshot = frozen[0] if frozen else None
                        saved_side = frozen[1] if frozen and len(frozen) > 1 else None
                        saved_type = frozen[2] if frozen and len(frozen) > 2 else None
                        saved_basis = frozen[3] if frozen and len(frozen) > 3 else None
                    protected = set(fields) - {'notes'}
                    if frozen_snapshot is not None and any(key in data for key in protected):
                        legacy_contract_snapshot = (not saved_side and isinstance(frozen_snapshot, dict)
                                                    and frozen_snapshot.get('documentKind') != 'customerWorkAct')
                        detail = ('Стороны подписанного договора уже зафиксированы. Создайте новую версию документа'
                                  if is_customer_contract(saved_side, saved_type) or legacy_contract_snapshot
                                  else 'Подписанный документ и его стороны уже зафиксированы')
                        raise HTTPException(409, detail)
                    target_side = data.get('side', saved_side)
                    target_type = data.get('docType', saved_type)
                    if 'basisContractDocumentId' in data:
                        data = {**data, 'basisContractDocumentId': normalized_basis(data, target_side, target_type)}
                    elif saved_basis is not None and not is_customer_work_act(target_side, target_type):
                        data = {**data, 'basisContractDocumentId': None}
                    selected = [(column,(data[key] or None) if key in ('docDate','basisContractDocumentId') else data[key])
                                for key,column in fields.items() if key in data]
                    if selected:
                        cur.execute(f'UPDATE {table} SET '+','.join(column+'=%s' for column,_ in selected)
                                    +' WHERE id=%s',[value for _,value in selected]+[id])
                    side = data.get('side', saved_side)
                    document_type = data.get('docType', saved_type)
                    if is_customer_contract(side, document_type):
                        freeze_customer_contract_if_ready(cur, id, actors[0])
                    elif is_customer_work_act(side, document_type):
                        freeze_customer_act_if_ready(cur, id, actors[0])
                return {'ok':True}

        @app.delete(path+'/{id}')
        def delete_record(id: int, _current_user: dict = Depends(authenticated), request: Request = None):
            scope = deps['record_scope']
            with scope.transaction(_current_user, request, write_roles, write=True) as (cur, actors):
                scope.record(cur, actors[0], table, id, write_roles)
                if table == 'project_documents':
                    cur.execute('SELECT party_snapshot_json FROM project_documents WHERE id=%s', (id,))
                    frozen = cur.fetchone()
                    frozen_snapshot = frozen.get('party_snapshot_json') if isinstance(frozen, dict) else (frozen[0] if frozen else None)
                    if frozen_snapshot is not None:
                        raise HTTPException(409, 'Подписанный документ хранится в истории и не удаляется')
                if table == 'project_letters':
                    cur.execute('''SELECT correction_requested_at,corrected_by_letter_id,replaces_letter_id,
                                          delivery_status,published_at
                        FROM project_letters WHERE id=%s FOR UPDATE''',(id,))
                    history = cur.fetchone()
                    if history and (any(history[:3]) or history[4] is not None):
                        raise HTTPException(409, 'Отправленная версия должна храниться в истории переписки')
                cur.execute(f'UPDATE {table} SET {void_column}=%s WHERE id=%s',(void_value,id))
            return {'ok':True}

    register_kind('/project-documents','project_documents',DOCUMENT_FIELDS,'uploadedBy','uploaded_by',
                  {'side':'customer','signStatus':'Не подписан'},'sign_status','Аннулирован')
    register_kind('/project-letters','project_letters',LETTER_FIELDS,'author','author',
                  {'side':'customer','direction':'outgoing'},'status','Аннулировано')
