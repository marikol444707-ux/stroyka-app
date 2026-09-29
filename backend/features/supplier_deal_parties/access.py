"""Shared offer/company authorization for deal metadata and contract snapshots."""
from fastapi import HTTPException

from ..supplier_access.service import supplier_offer_visibility_filter

READ_ROLES = ('директор', 'зам_директора', 'снабженец', 'бухгалтер', 'кладовщик', 'прораб')
WRITE_ROLES = ('директор', 'зам_директора', 'снабженец', 'бухгалтер')


def build_deal_access(deps):
    resolve_actor = deps['resolve_resource_company_actor']
    def supplier_visibility(cur, offer_id, user):
        supplier_ids = deps['current_supplier_ids'](cur, user)
        sql, params = supplier_offer_visibility_filter(supplier_ids, user.get('id'))
        cur.execute('SELECT id FROM supplier_offers WHERE id=%s' + sql, [offer_id] + params)
        if not cur.fetchone():
            raise HTTPException(403, 'Нет доступа к сторонам этой сделки')

    def company_actor(cur, user, company_id, action, x_company_id=None, x_company_mode=None):
        _, actor = resolve_actor(
            cur, user, company_id, action,
            x_company_id=x_company_id, x_company_mode=x_company_mode,
            allowed_roles=READ_ROLES if action == 'read' else WRITE_ROLES,
            platform_staff_roles=deps['platform_staff_roles'],
            client_account_roles=deps['client_account_roles'],
        )
        return actor

    def load_authorized_offer(cur, offer_id, user, action, header_id, header_mode):
        if user.get('role') == 'поставщик':
            if action != 'read':
                raise HTTPException(403, 'Стороны сделки выбирает уполномоченный сотрудник заказчика')
            supplier_visibility(cur, offer_id, user)
        lock = ' FOR UPDATE OF o,r' if action != 'read' else ''
        cur.execute('''SELECT o.id,o.company_id,o.request_id,o.supplier_id,o.status,
                              r.project,COALESCE(r.work_package,'Основная') AS work_package
                       FROM supplier_offers o JOIN supply_requests r
                         ON r.id=o.request_id AND r.company_id=o.company_id
                       WHERE o.id=%s AND o.company_id > 0 AND o.supplier_id > 0''' + lock, (offer_id,))
        offer = cur.fetchone()
        if not offer:
            raise HTTPException(404, 'КП с корректной компанией и заявкой не найдено')
        actor = user
        if user.get('role') != 'поставщик':
            actor = company_actor(cur, user, offer['company_id'], action, header_id, header_mode)
            deps['require_project_access'](actor, offer.get('project') or '')
            if not deps['has_package_access'](actor, offer['work_package']):
                raise HTTPException(403, 'Нет доступа к пакету заявки')
        return offer, actor

    return company_actor, load_authorized_offer
