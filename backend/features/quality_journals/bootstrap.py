"""Operator-only historical ownership plan, explicitly confirmed by the owner.

No runtime route, default tenant, document reconstruction or auth impersonation.
The caller supplies the exact reviewed IDs and owns a READ COMMITTED transaction.
Only ownership columns change; defects in historical contents stay untouched.
"""
import hashlib
import json

from psycopg2.extras import Json

from .ownership import JOURNALS, positive_id

TABLES = ('warehouse_invoices', *JOURNALS)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        default=str, separators=(',', ':')).encode()).hexdigest()


def _target(cur, company_id, project_id):
    cur.execute('''SELECT p.id,p.company_id,p.name,c.platform_account_id
        FROM projects p JOIN companies c ON c.id=p.company_id
        WHERE p.id=%s AND p.company_id=%s''', (project_id,company_id))
    row = cur.fetchone()
    if not row or not row['platform_account_id']:
        raise ValueError('Explicit project and company must exist')
    return dict(row)


def _rows(cur, table, ids):
    if table not in TABLES or not ids or len(ids)>1000 or any(not positive_id(i) for i in ids) or ids!=sorted(set(ids)):
        raise ValueError('Exact unique positive historical IDs required')
    cur.execute('SELECT * FROM '+table+' WHERE id=ANY(%s) ORDER BY id', (ids,))
    rows = [dict(row) for row in cur.fetchall()]
    if [r['id'] for r in rows]!=ids:
        raise ValueError('Historical inventory changed')
    return rows


def make_plan(cur, *, company_id, project_id, journal_ids, confirmation):
    if not positive_id(company_id) or not positive_id(project_id) or set(journal_ids)!=set(JOURNALS):
        raise ValueError('Company, project and both journal inventories required')
    if type(confirmation) is not str or not 10<=len(confirmation)<=2000:
        raise ValueError('Explicit owner confirmation required')
    target = _target(cur,company_id,project_id)
    rows, invoice_ids = {}, set()
    for table in JOURNALS:
        rows[table] = _rows(cur,table,journal_ids[table])
        for row in rows[table]:
            if row.get('company_id') is not None or row.get('project_id') is not None:
                raise ValueError('Already owned historical record requires its original plan')
            if row['project_name']!=target['name']:
                raise ValueError('Historical project differs from confirmed inventory')
            # This release supports the actual invoice/stock inventory reviewed
            # by the owner. Other provenance requires a separate explicit plan.
            if row['delivery_id'] is not None or row['warehouse_history_id'] is not None:
                raise ValueError('Additional source ownership requires review')
            invoice_id=row['invoice_id']
            if invoice_id is not None:
                if (not positive_id(invoice_id) or row['source_type'] not in (None,'','warehouse_invoice','scan_project_invoice')
                        or row['source_id'] not in (None,invoice_id)):
                    raise ValueError('Contradictory primary document references')
                invoice_ids.add(invoice_id)
            elif row['source_type']!='project_stock' or row['source_id'] is not None:
                raise ValueError('Unreviewed source type')
    rows['warehouse_invoices']=_rows(cur,'warehouse_invoices',sorted(invoice_ids)) if invoice_ids else []
    for row in rows['warehouse_invoices']:
        if (row['company_id']!=company_id or row.get('project_id') not in (None,project_id)
                or row['project']!=target['name'] or row['location']!=target['name'] or row['warehouse_target']!='object'):
            raise ValueError('Referenced document belongs to a different owner or location')
    entries = {}
    for table in TABLES:
        entries[table]=[dict(id=r['id'],beforeHash=digest(r),
            afterHash=digest(dict(r,company_id=company_id,project_id=project_id))) for r in rows[table]]
    return dict(format=1,target=target,confirmation=confirmation,entries=entries)


def apply_plan(cur, plan, expected_digest):
    if cur.connection.autocommit:
        raise ValueError('Ownership bootstrap requires an explicit transaction')
    cur.execute('SHOW transaction_isolation')
    if cur.fetchone()['transaction_isolation']!='read committed':
        raise ValueError('Ownership bootstrap requires READ COMMITTED')
    if plan.get('format')!=1 or digest(plan)!=expected_digest or set(plan.get('entries',{}))!=set(TABLES):
        raise ValueError('Confirmed plan digest mismatch')
    # One lock order serializes retries and prevents insert phantoms while the
    # pinned source inventory is checked. Deployment pauses application writers.
    cur.execute('LOCK TABLE quality_owner_bootstraps,companies,projects,'+','.join(TABLES)+' IN SHARE ROW EXCLUSIVE MODE')
    target=plan['target'];company_id=target['company_id'];project_id=target['id']
    if _target(cur,company_id,project_id)!=target:
        raise ValueError('Target ownership changed after review')
    cur.execute('SELECT plan,result FROM quality_owner_bootstraps WHERE plan_digest=%s', (expected_digest,))
    saved=cur.fetchone()
    if saved:
        if saved['plan']!=plan:
            raise ValueError('Conflicting saved ownership plan')
        for table in TABLES:
            entries=plan['entries'][table]
            if entries:
                for row in _rows(cur,table,[r['id'] for r in entries]):
                    if (row['company_id'],row['project_id'])!=(company_id,project_id):
                        raise ValueError('Previously applied ownership changed')
        return dict(saved['result'],alreadyApplied=True)
    for table in TABLES:
        entries=plan['entries'][table]
        if not entries:
            continue
        for row,expected in zip(_rows(cur,table,[e['id'] for e in entries]),entries):
            if digest(row)!=expected['beforeHash']:
                raise ValueError('Historical row changed after review: '+table+':'+str(row['id']))
    for table in TABLES:
        for entry in plan['entries'][table]:
            cur.execute('UPDATE '+table+' SET company_id=%s,project_id=%s WHERE id=%s RETURNING *',
                        (company_id,project_id,entry['id']))
            if digest(dict(cur.fetchone()))!=entry['afterHash']:
                raise ValueError('Historical content changed during ownership assignment')
    result=dict(companyId=company_id,projectId=project_id,planDigest=expected_digest,
                counts={t:len(v) for t,v in plan['entries'].items()})
    cur.execute('''INSERT INTO quality_owner_bootstraps(plan_digest,company_id,project_id,plan,result)
        VALUES(%s,%s,%s,%s,%s)''', (expected_digest,company_id,project_id,Json(plan),Json(result)))
    return dict(result,alreadyApplied=False)
