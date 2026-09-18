"""Tenant-aware visibility for fulfilment rows; SQL identifiers are code-owned."""
from fastapi import HTTPException
import psycopg2.extras




def assert_delivery_chain(cur, delivery):
    cur.execute('''SELECT o.id FROM supplier_offers o JOIN supply_requests r
                    ON r.id=o.request_id AND r.company_id=o.company_id
                   WHERE o.id=%s AND r.id=%s AND o.company_id=%s
                     AND o.supplier_id=%s AND r.project=%s FOR SHARE OF o,r''',
                (delivery.get('offer_id'), delivery.get('request_id'), delivery.get('company_id'),
                 delivery.get('supplier_id'), delivery.get('project')))
    if not cur.fetchone():
        raise HTTPException(409, 'Нарушена связь поставки с компанией, заявкой или поставщиком')


def save_delivery_check_result(get_db, snapshot, result, authorize):
    """Recheck current ownership after model latency, outside any financial writer."""
    conn = get_db()
    cur = None
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute('SELECT * FROM supply_deliveries WHERE id=%s FOR UPDATE', (snapshot['id'],))
        current = cur.fetchone()
        authorize(cur, current)
        assert_delivery_chain(cur, current)
        fields = ('company_id', 'request_id', 'offer_id', 'supplier_id', 'project',
                  'work_package', 'material_name', 'planned_quantity', 'unit')
        if any(current.get(key) != snapshot.get(key) for key in fields):
            raise HTTPException(409, 'Поставка изменилась во время проверки. Повторите сверку')
        cur.execute('UPDATE supply_deliveries SET ai_check_result=%s WHERE id=%s', (result, snapshot['id']))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def internal_fulfilment_filter(actors, *, company_column, project_column,
                                package_column, deps, worker_condition=None, full_view_roles=None):
    clauses, params = [], []
    for actor in actors:
        role = actor.get('role') or ''
        condition, values = '', []
        if deps['can_see_all_company_data'](actor):
            if full_view_roles is not None and role not in full_view_roles:
                continue
        elif role in ('снабженец', 'кладовщик', 'прораб'):
            condition, values = deps['scoped_project_filter'](actor, project_column)
        elif role in deps['worker_execution_roles'] and worker_condition:
            condition = ' AND ' + worker_condition
            values = [actor.get('id'), actor.get('name') or '']
        else:
            continue
        package_sql, package_params = deps['package_access_filter'](actor, package_column)
        clauses.append('(' + company_column + '=%s' + condition + package_sql + ')')
        params.extend([actor['company_id']] + list(values) + list(package_params))
    return '(' + ' OR '.join(clauses) + ')' if clauses else 'FALSE', params
