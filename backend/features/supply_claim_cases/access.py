"""One coherent claim/delivery/offer/request boundary for both portals."""
from fastapi import HTTPException

from ..supplier_access.service import supplier_delivery_visibility_filter
from ..work_material_accounting.access import lock_actor

CHAIN = ''' FROM supply_claims c
    JOIN supply_deliveries d ON d.id=c.delivery_id AND d.request_id=c.request_id
      AND d.offer_id=c.offer_id AND d.supplier_id=c.supplier_id AND d.project=c.project
      AND COALESCE(d.work_package,'')=COALESCE(c.work_package,'')
    JOIN supplier_offers o ON o.id=d.offer_id AND o.request_id=d.request_id
      AND o.company_id=d.company_id AND o.supplier_id=d.supplier_id
    JOIN supply_requests r ON r.id=o.request_id AND r.company_id=d.company_id AND r.project=d.project
    JOIN companies company ON company.id=d.company_id AND COALESCE(company.active,TRUE)'''
COLUMNS = '''c.id,c.delivery_id AS "deliveryId",c.request_id AS "requestId",c.offer_id AS "offerId",
    c.supplier_id AS "supplierId",d.company_id AS "companyId",d.supplier_name AS "supplierName",
    c.project,c.material_name AS "materialName",c.claim_type AS "claimType",c.description,
    c.expected_quantity AS "expectedQuantity",c.received_quantity AS "receivedQuantity",
    c.shortage_quantity AS "shortageQuantity",COALESCE(c.work_package,'') AS "workPackage",
    c.photo_url AS "photoUrl",c.status,c.created_by AS "createdBy",c.created_at AS "createdAt",
    c.resolved_at AS "resolvedAt",c.resolution'''


def visibility(cur, user, company, mode, deps):
    if user.get('role') == 'поставщик':
        return supplier_delivery_visibility_filter(deps['current_supplier_ids'](cur, user), user['id'])
    scope, params = deps['fulfilment_visibility'](cur, user, 'd.company_id', 'c.project', 'c.work_package',
        company, mode, 'c.request_id IN (SELECT id FROM supply_requests WHERE requested_by_id=%s OR created_by=%s)')
    return '(' + scope + ''') AND EXISTS(SELECT 1 FROM user_company_roles membership
        WHERE membership.user_id=%s AND membership.company_id=d.company_id AND COALESCE(membership.active,TRUE))''', list(params)+[user['id']]


def visible_rows(cur, user, company, mode, deps, claim_id=None, ready=True, limit=None):
    scope, params = visibility(cur, user, company, mode, deps)
    query = 'SELECT ' + COLUMNS + (',c.version' if ready else ',1 AS version') + CHAIN + ' WHERE ' + scope
    if claim_id is not None:
        query += ' AND c.id=%s'
        params = list(params) + [claim_id]
    query += ' ORDER BY c.id DESC'
    if limit:
        query += ' LIMIT %s'
        params = list(params) + [limit]
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def selected_actor(cur, user, company, mode, deps, write=False):
    if user.get('role') == 'поставщик':
        return dict(user)
    context = deps['resolve_work_company_context'](cur, user, None, 'write' if write else 'read',
                                                  x_company_id=company, x_company_mode=mode)
    actors = deps['effective_company_actors'](user, context)
    if context.get('mode') != 'company' or len(actors) != 1:
        raise HTTPException(409, 'Выберите компанию для работы с претензиями')
    if not (actors[0].get('membershipId') or actors[0].get('membership_id')):
        raise HTTPException(403, 'Нужно действующее членство в выбранной компании')
    return {**actors[0], 'companyId': context['companyId']}


def pin(cur, actor, claim):
    if actor['role'] != 'поставщик':
        lock_actor(cur, actor)
        return
    from ..supplier_team.policy import enabled, lock_offer_access
    if enabled():
        # Same supplier → actor → membership → assignment order as team changes.
        lock_offer_access(cur, claim['offerId'], actor['id'])
    else:
        cur.execute("SELECT id FROM users WHERE id=%s AND role='поставщик' AND COALESCE(active,TRUE) FOR SHARE", (actor['id'],))
        if not cur.fetchone():
            raise HTTPException(403, 'Кабинет поставщика отключён')
        cur.execute('SELECT id FROM suppliers WHERE id=%s AND user_id=%s FOR SHARE', (claim['supplierId'], actor['id']))
        if not cur.fetchone():
            raise HTTPException(403, 'Нет доступа к поставщику претензии')
    cur.execute('SELECT id FROM companies WHERE id=%s AND COALESCE(active,TRUE) FOR SHARE', (claim['companyId'],))
    if not cur.fetchone():
        raise HTTPException(403, 'Компания отключена')


def lock_chain(cur, claim):
    # Receipt writers start with the delivery as well. Recheck visibility after
    # waiting for every mutable link, including existing recipient decisions.
    cur.execute('SELECT id FROM supply_deliveries WHERE id=%s FOR UPDATE', (claim['deliveryId'],))
    cur.fetchone()
    cur.execute('SELECT id FROM supplier_offers WHERE id=%s FOR SHARE', (claim['offerId'],))
    cur.fetchone()
    cur.execute('SELECT id FROM supply_requests WHERE id=%s FOR UPDATE', (claim['requestId'],))
    cur.fetchone()
    cur.execute('SELECT id FROM supply_request_recipients WHERE request_id=%s ORDER BY id FOR SHARE', (claim['requestId'],))
    cur.fetchall()
    cur.execute('SELECT id FROM supply_claims WHERE id=%s FOR UPDATE', (claim['id'],))
    cur.fetchone()
