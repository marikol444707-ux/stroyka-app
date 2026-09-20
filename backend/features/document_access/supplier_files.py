"""Supplier files follow an addressed offer, never buyer workforce membership."""
import json
import re
from fastapi import HTTPException
from ..supplier_access.service import supplier_offer_visibility_filter, supplier_invoice_visibility_filter
from ..supplier_team.policy import access_ids, enabled, lock_offer_access


def supplier_ids(cur, user):
    if enabled():
        return access_ids(cur, user)
    cur.execute('SELECT id FROM suppliers WHERE user_id=%s', (user['id'],))
    return [row['id'] for row in cur.fetchall()]


def offer_scope(cur, user, offer_id, lock=False):
    if user.get('role') != 'поставщик' or type(offer_id) is not int or offer_id <= 0:
        raise HTTPException(403, 'Нет доступа к файлам КП')
    if lock and enabled():
        lock_offer_access(cur, offer_id, user['id'])
    sql, params = supplier_offer_visibility_filter(supplier_ids(cur, user), user['id'])
    cur.execute('''SELECT supplier_offers.id,supplier_offers.company_id,r.project
        FROM supplier_offers JOIN supply_requests r ON r.id=supplier_offers.request_id
        JOIN companies c ON c.id=supplier_offers.company_id AND COALESCE(c.active,TRUE)
        WHERE supplier_offers.id=%s''' + sql, [offer_id] + params)
    row = cur.fetchone()
    if not row:
        raise HTTPException(403, 'Нет доступа к файлам КП')
    return dict(row)


def upload_scope(cur, user, offer_id):
    offer = offer_scope(cur, user, offer_id, lock=True)
    project = None
    if offer.get('project'):
        cur.execute('SELECT id,name FROM projects WHERE company_id=%s AND name=%s',
                    (offer['company_id'], offer['project']))
        projects = cur.fetchall()
        if len(projects) != 1:
            raise HTTPException(409, 'Объект КП не определён однозначно')
        project = dict(projects[0])
    return offer['company_id'], 'supplier-offer-' + str(offer_id), project


def validate_attachment(cur, user, offer_id, url):
    if not url:
        return
    match = re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content', str(url))
    if not match and not str(url).startswith('/uploads/'):
        raise HTTPException(400, 'Прикрепите файл через загрузку в карточке КП')
    offer = offer_scope(cur, user, offer_id)
    cur.execute("""SELECT f.id FROM file_ownership f WHERE
        (f.id=%s OR f.file_url=%s) AND f.company_id=%s
        AND COALESCE(f.deletion_status,'active')='active'
        AND (f.context=%s OR EXISTS(SELECT 1 FROM supplier_offers o
            WHERE o.id=%s AND o.company_id=f.company_id AND o.pdf_url=%s)) FOR SHARE OF f""",
        (int(match[1]) if match else None, str(url), offer['company_id'],
         'supplier-offer-' + str(offer_id), offer_id, str(url)))
    if not cur.fetchone():
        raise HTTPException(403, 'Файл не относится к этому КП или удалён')



def authorize_read(cur, user, row):
    sql, params = supplier_offer_visibility_filter(supplier_ids(cur, user), user['id'])
    urls = [f"/tenant-files/{row['id']}/content", row['file_url']]
    # Old registered files remain readable only through an actual visible
    # document reference. New draft files have a server-created offer context.
    cur.execute('''SELECT supplier_offers.id FROM supplier_offers
        JOIN supply_requests r ON r.id=supplier_offers.request_id
        JOIN companies c ON c.id=supplier_offers.company_id AND COALESCE(c.active,TRUE)
        WHERE supplier_offers.company_id=%s
          AND (%s IS NULL OR EXISTS(SELECT 1 FROM projects p WHERE p.id=%s
               AND p.company_id=supplier_offers.company_id AND p.name=r.project))
          AND (%s='supplier-offer-' || supplier_offers.id::text
            OR supplier_offers.pdf_url=ANY(%s)
            OR EXISTS(SELECT 1 FROM supplier_invoices si
                WHERE si.offer_id=supplier_offers.id AND si.company_id=supplier_offers.company_id
                AND si.supplier_id=supplier_offers.supplier_id
                AND (si.request_id IS NULL OR si.request_id=supplier_offers.request_id)
                AND (si.file_url=ANY(%s) OR si.photo_url=ANY(%s)))
            OR EXISTS(SELECT 1 FROM supply_deliveries d
                WHERE d.offer_id=supplier_offers.id AND d.company_id=supplier_offers.company_id
                AND d.supplier_id=supplier_offers.supplier_id AND d.request_id=supplier_offers.request_id
                AND d.project=r.project AND (d.document_url=ANY(%s) OR d.photo_url=ANY(%s)
                    OR EXISTS(SELECT 1 FROM supply_claims claim WHERE claim.delivery_id=d.id
                        AND claim.offer_id=d.offer_id AND claim.request_id=d.request_id
                        AND claim.supplier_id=d.supplier_id AND claim.project=d.project
                        AND COALESCE(claim.work_package,'')=COALESCE(d.work_package,'')
                        AND claim.photo_url=ANY(%s)))))''' + sql + ' LIMIT 1',
        [row['company_id'], row.get('project_id'), row.get('project_id'), row.get('context'),
         urls, urls, urls, urls, urls, urls] + params)
    if cur.fetchone():
        return dict(user)
    invoice_sql, invoice_params = supplier_invoice_visibility_filter(supplier_ids(cur, user), user['id'])
    cur.execute("""SELECT si.id FROM supplier_invoices si
        JOIN companies c ON c.id=si.company_id AND COALESCE(c.active,TRUE)
        WHERE si.offer_id IS NULL AND si.company_id=%s
        AND (si.file_url=ANY(%s) OR si.photo_url=ANY(%s))
        AND (%s IS NULL OR EXISTS(SELECT 1 FROM projects p WHERE p.id=%s
            AND p.company_id=si.company_id AND p.name=si.project_name))""" + invoice_sql + ' LIMIT 1',
        [row['company_id'],urls,urls,row.get('project_id'),row.get('project_id')]+invoice_params)
    if cur.fetchone():
        return dict(user)
    cur.execute("""SELECT wi.photo_url,wi.photo_urls FROM supplier_invoices si
        JOIN companies c ON c.id=si.company_id AND COALESCE(c.active,TRUE)
        JOIN warehouse_invoices wi ON wi.company_id=si.company_id
            AND (wi.supplier_id IS NULL OR wi.supplier_id=si.supplier_id)
            AND (wi.id=si.warehouse_invoice_id OR wi.supplier_invoice_id=si.id
                OR EXISTS(SELECT 1 FROM supply_deliveries d WHERE d.id=wi.supply_delivery_id
                    AND d.company_id=si.company_id AND d.supplier_id=si.supplier_id
                    AND d.offer_id=si.offer_id AND (si.request_id IS NULL OR d.request_id=si.request_id))
                OR (wi.supply_request_id=si.request_id AND wi.supplier_id=si.supplier_id))
        WHERE si.company_id=%s
        AND (%s IS NULL OR EXISTS(SELECT 1 FROM projects p WHERE p.id=%s
            AND p.company_id=si.company_id AND p.name=si.project_name))
        AND (wi.photo_url=ANY(%s) OR POSITION(%s IN COALESCE(wi.photo_urls,''))>0
            OR POSITION(%s IN COALESCE(wi.photo_urls,''))>0)""" + invoice_sql,
        [row['company_id'],row.get('project_id'),row.get('project_id'),urls,*urls]+invoice_params)
    for invoice in cur.fetchall():
        try:
            photos = json.loads(invoice.get('photo_urls') or '[]')
        except (ValueError, TypeError):
            photos = []
        if invoice.get('photo_url') in urls or (isinstance(photos,list) and any(url in photos for url in urls)):
            return dict(user)
    raise HTTPException(403, 'Нет доступа к файлу поставки')
