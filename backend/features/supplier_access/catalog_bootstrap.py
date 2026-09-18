"""Explicit, reviewed ownership transfer of legacy cards; never infer a tenant."""
import hashlib
import json

import psycopg2.extras

from .company_directory import LINK_FIELDS, relationship_values


LEGACY_PROFILE = {'phone': 'phone', 'email': 'email', 'specialization': 'specialization',
                  'notes': 'notes', 'licenseUrl': 'license_url', 'priceUrl': 'price_url'}
LEGACY_LINK = {**LINK_FIELDS, 'category': 'category'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    default=str, separators=(',', ':')).encode()).hexdigest()


def company_row(cur, company_id, lock=False):
    cur.execute('SELECT id,name,platform_account_id FROM companies WHERE id=%s' + (' FOR UPDATE' if lock else ''), (company_id,))
    company = cur.fetchone()
    if not company or not company['platform_account_id']:
        raise ValueError('Company must exist and belong to a platform account')
    return dict(company)


def supplier_rows(cur, supplier_ids, lock=False):
    # Pin the complete source, including legal identity and portal binding.
    cur.execute('SELECT * FROM suppliers WHERE id=ANY(%s) ORDER BY id'
                + (' FOR SHARE' if lock else ''), (supplier_ids,))
    rows = cur.fetchall()
    if [r['id'] for r in rows] != supplier_ids:
        raise ValueError('Every explicitly selected supplier must exist')
    return rows


def make_plan(cur, company_id, supplier_ids):
    if type(company_id) is not int or company_id < 1 or not supplier_ids or len(supplier_ids) > 1000:
        raise ValueError('Explicit company and 1..1000 supplier IDs required')
    if any(type(sid) is not int or sid < 1 for sid in supplier_ids) or len(set(supplier_ids)) != len(supplier_ids):
        raise ValueError('Supplier IDs must be unique positive integers')
    supplier_ids = sorted(supplier_ids)
    return {'format': 1, 'company': company_row(cur, company_id),
            'suppliers': [{'id': r['id'], 'name': r['name'], 'sourceHash': digest(dict(r))}
                          for r in supplier_rows(cur, supplier_ids)]}


def apply_plan(cur, plan, expected_digest):
    if plan.get('format') != 1 or digest(plan) != expected_digest:
        raise ValueError('Reviewed plan digest mismatch')
    company = company_row(cur, plan['company']['id'], lock=True)
    if company != plan['company']:
        raise ValueError('Company ownership changed after review')
    ids = [item['id'] for item in plan['suppliers']]
    if not ids or ids != sorted(set(ids)) or len(ids) > 1000:
        raise ValueError('Invalid reviewed supplier set')
    rows = supplier_rows(cur, ids, lock=True)
    created, existing = [], []
    for source, planned in zip(rows, plan['suppliers']):
        if digest(dict(source)) != planned['sourceHash']:
            raise ValueError('Legacy supplier changed after review: ' + str(source['id']))
        values = relationship_values({key: source[column] for key, column in {**LEGACY_PROFILE, **LEGACY_LINK}.items()})
        values['profile']['_legacySourceHash'] = planned['sourceHash']
        cur.execute('SELECT * FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s FOR UPDATE',
                    (company['id'], source['id']))
        link = cur.fetchone()
        if link:
            if link['platform_account_id'] != company['platform_account_id'] or any(link[key] != value for key, value in values.items()):
                raise ValueError('Existing company relationship must not be overwritten: ' + str(source['id']))
            existing.append(source['id'])
            continue
        columns = list(LINK_FIELDS.values())
        cur.execute('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id,'
                    + ','.join(columns) + ',profile) VALUES (' + ','.join(['%s'] * (len(columns) + 4)) + ') RETURNING id',
                    [company['id'], source['id'], company['platform_account_id']]
                    + [values[key] for key in columns] + [psycopg2.extras.Json(values['profile'])])
        link_id = cur.fetchone()['id']
        cur.execute('''INSERT INTO audit_log(user_name,user_role,action,entity_type,entity_id,description,owner_scope,company_id)
            VALUES('catalog-migration','system','supplier_catalog_bootstrap','company_supplier_link',%s,%s,'company',%s)''',
            (link_id, 'Explicit ownership plan SHA256 ' + expected_digest, company['id']))
        created.append(source['id'])
    return {'created': created, 'alreadyApplied': existing, 'companyId': company['id'], 'planDigest': expected_digest}
