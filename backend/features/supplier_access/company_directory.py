"""Company-owned supplier relationships; legal identity grants no portal access."""
import math
from contextlib import contextmanager
from datetime import date

import psycopg2.extras
from fastapi import HTTPException

from ..company_context.service import effective_company_user, resolve_request_company_context


PUBLIC_FIELDS = {
    'name': 'name', 'inn': 'inn', 'kpp': 'kpp', 'ogrn': 'ogrn',
    'legalAddress': 'legal_address', 'actualAddress': 'actual_address',
    'bank': 'bank', 'bik': 'bik', 'account': 'account', 'korAccount': 'kor_account',
    'directorName': 'director_name', 'directorPosition': 'director_position', 'website': 'website',
}
PRIVATE_FIELDS = ('phone', 'email', 'specialization', 'notes', 'licenseUrl', 'priceUrl',
                  'paymentTerms', 'deliveryTerms')
# Supplier-owned public contact/marketing fields have separate meaning. These
# company overrides are never populated by fallback to the public self-profile.
LINK_FIELDS = {'category': 'local_category', 'sourceType': 'source_type',
               'sourceDetail': 'source_detail', 'contractUrl': 'contract_url',
               'contractNumber': 'contract_number', 'contractDate': 'contract_date',
               'rating': 'rating', 'status': 'status'}
PUBLIC_SELECT = ','.join('s.' + value for value in PUBLIC_FIELDS.values())
PUBLIC_LIMITS = {key: (4000 if key in ('legalAddress', 'actualAddress') else
                      50 if key in ('inn', 'kpp', 'ogrn', 'bik', 'account', 'korAccount') else 255)
                 for key in PUBLIC_FIELDS}


def relationship_values(data, previous=None):
    previous = previous or {}
    values = {}
    for key, column in LINK_FIELDS.items():
        value = data.get(key, data.get(column, previous.get(column)))
        if key == 'rating':
            try:
                if isinstance(value, bool):
                    raise ValueError()
                value = None if value in (None, '') else float(value)
            except (ValueError, TypeError):
                raise HTTPException(422, 'Рейтинг должен быть числом от 0 до 5')
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 5):
                raise HTTPException(422, 'Рейтинг должен быть числом от 0 до 5')
        elif key == 'contractDate':
            try:
                value = date.fromisoformat(str(value)) if value else None
            except ValueError:
                raise HTTPException(422, 'Дата договора должна быть в формате ГГГГ-ММ-ДД')
        else:
            value = str(value or ('Активный' if key == 'status' else '')).strip()
            limit = 100 if key in ('category', 'sourceType', 'contractNumber') else 500 if key == 'contractUrl' else 4000
            if len(value) > limit:
                raise HTTPException(422, 'Слишком длинное поле: ' + key)
            if key == 'status' and value not in ('Активный', 'Неактивный', 'Заблокирован', 'На проверке', 'Нужно уточнение'):
                raise HTTPException(422, 'Некорректный статус отношений с поставщиком')
        values[column] = value
    profile = dict(previous.get('profile') or {})
    for key in PRIVATE_FIELDS:
        if key in data:
            value = str(data[key] or '').strip()
            if len(value) > 4000:
                raise HTTPException(422, 'Слишком длинное поле: ' + key)
            profile[key] = value
    values['profile'] = profile
    return values


def serialize_relationship(row):
    result = {column: row.get(column) for column in PUBLIC_FIELDS.values()}
    result.update({key: row.get(column) for key, column in LINK_FIELDS.items()})
    result.update({key: (row.get('profile') or {}).get(key, '') for key in PRIVATE_FIELDS})
    result.update(id=row['supplier_id'], companyId=row['company_id'],
                  companySupplierLinkId=row['id'], relationshipVersion=row['version'],
                  identityReadOnly=True)
    return result


class CompanySupplierDirectory:
    def __init__(self, deps):
        self.deps = deps
        self.read_roles = set(deps.get('supply_roles', ())) | set(deps.get('warehouse_roles', ())) | set(deps.get('finance_roles', ()))
        self.write_roles = {'директор', 'зам_директора', 'снабженец', 'кладовщик', 'бухгалтер'}

    @contextmanager
    def transaction(self, user, headers, *, write=False, claimed_company_id=None):
        conn = self.deps['get_db']()
        cur = None
        try:
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SET LOCAL statement_timeout='15s'")
            options = dict(x_company_id=headers[0], x_company_mode=headers[1],
                           platform_staff_roles=self.deps.get('platform_staff_roles', ()),
                           client_account_roles=self.deps.get('client_account_roles', ()))
            context = resolve_request_company_context(cur, user, claimed_company_id,
                                                      'update' if write else 'read', **options)
            if context.get('mode') != 'company':
                raise HTTPException(400, 'Для каталога поставщиков выберите одну компанию')
            actor = effective_company_user(user, context)
            if actor.get('role') not in (self.write_roles if write else self.read_roles):
                raise HTTPException(403, 'Роль в компании не позволяет работать с каталогом поставщиков')
            cid = context['companyId']
            # Serialize relationship changes and pin current membership through commit.
            if write:
                cur.execute('SELECT id FROM user_company_roles WHERE user_id=%s AND company_id=%s FOR SHARE',
                            (user['id'], cid))
                cur.fetchall()
                context = resolve_request_company_context(cur, user, cid, 'update', **options)
                actor = effective_company_user(user, context)
                if actor.get('role') not in self.write_roles:
                    raise HTTPException(403, 'Полномочия в компании изменились')
            cur.execute('SELECT id,platform_account_id FROM companies WHERE id=%s' + (' FOR UPDATE' if write else ''), (cid,))
            company = cur.fetchone()
            if not company or not company.get('platform_account_id'):
                raise HTTPException(409, 'Компания не привязана к аккаунту платформы')
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='company_supplier_links' AND column_name IN ('profile','version')")
            if {row['column_name'] for row in cur.fetchall()} != {'profile', 'version'}:
                raise HTTPException(503, 'Каталог поставщиков обновляется. Повторите позже')
            yield cur, company, actor
            if write:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if not write:
                conn.rollback()
            if cur is not None:
                cur.close()
            conn.close()

    def rows(self, cur, company, supplier_id=None):
        cur.execute(f'''SELECT link.*, {PUBLIC_SELECT} FROM company_supplier_links link
                        JOIN suppliers s ON s.id=link.supplier_id
                        WHERE link.company_id=%s AND link.platform_account_id=%s'''
                    + (' AND link.supplier_id=%s' if supplier_id else '') + ' ORDER BY s.name,s.id LIMIT 1001',
                    (company['id'], company['platform_account_id']) + ((supplier_id,) if supplier_id else ()))
        rows = cur.fetchall()
        if len(rows) > 1000:
            raise HTTPException(409, 'Каталог превышает 1000 поставщиков; требуется постраничный просмотр')
        return [serialize_relationship(row) for row in rows]

    def list(self, user, headers):
        with self.transaction(user, headers) as (cur, company, actor):
            return self.rows(cur, company)

    def audit(self, cur, actor, company, link_id, action):
        cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,
                       entity_id,description,owner_scope,company_id)
                       VALUES(%s,%s,%s,%s,'company_supplier_link',%s,%s,'company',%s)''',
                    (actor['id'], actor.get('name', ''), actor['role'], action, link_id,
                     'Изменены отношения компании с поставщиком', company['id']))

    def create(self, data, user, headers):
        if not str(data.get('name') or '').strip():
            raise HTTPException(422, 'Укажите название поставщика')
        inn, ogrn = str(data.get('inn') or '').strip(), str(data.get('ogrn') or '').strip()
        if (not inn and not ogrn) or any(value and (not value.isascii() or not value.isdecimal() or len(value) not in lengths)
                                       for value, lengths in ((inn, (10, 12)), (ogrn, (13, 15)))):
            raise HTTPException(422, 'Укажите ИНН (10 или 12 цифр) либо ОГРН/ОГРНИП (13 или 15 цифр)')
        values = relationship_values(data)
        with self.transaction(user, headers, write=True, claimed_company_id=data.get('companyId')) as (cur, company, actor):
            # Exact legal keys only. A contact/name/alias never links identity or access.
            for identity in sorted(filter(None, (inn, ogrn))):
                cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('supplier-legal:' + identity,))
            cur.execute("SELECT * FROM suppliers WHERE (%s<>'' AND inn=%s) OR (%s<>'' AND ogrn=%s) ORDER BY id FOR SHARE", (inn, inn, ogrn, ogrn))
            matches = cur.fetchall()
            if len(matches) > 1:
                raise HTTPException(409, 'Найдено несколько карточек с этими реквизитами. Нужна проверка платформы')
            if matches:
                supplier = matches[0]
                if any(value and supplier.get(key) and value != str(supplier[key]).strip()
                       for key, value in (('inn', inn), ('ogrn', ogrn))):
                    raise HTTPException(409, 'ИНН и ОГРН относятся к разным карточкам')
                supplier_id = supplier['id']
            else:
                columns = list(PUBLIC_FIELDS.values())
                payload = [str(data.get(key) or '').strip() for key in PUBLIC_FIELDS]
                if any(len(value) > PUBLIC_LIMITS[key] for key, value in zip(PUBLIC_FIELDS, payload)):
                    raise HTTPException(422, 'Реквизиты поставщика слишком длинные')
                cur.execute('INSERT INTO suppliers (' + ','.join(columns) + ') VALUES (' + ','.join(['%s'] * len(columns)) + ') RETURNING id', payload)
                supplier_id = cur.fetchone()['id']
            cur.execute('SELECT id FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s', (company['id'], supplier_id))
            if cur.fetchone():
                raise HTTPException(409, 'Поставщик уже есть в каталоге компании. Обновите его карточку')
            columns = list(LINK_FIELDS.values())
            cur.execute('INSERT INTO company_supplier_links (company_id,supplier_id,platform_account_id,'
                        + ','.join(columns) + ',profile) VALUES (' + ','.join(['%s'] * (len(columns) + 4)) + ') RETURNING id',
                        [company['id'], supplier_id, company['platform_account_id']] + [values[c] for c in columns]
                        + [psycopg2.extras.Json(values['profile'])])
            link_id = cur.fetchone()['id']
            self.audit(cur, actor, company, link_id, 'supplier_relationship_created')
            return self.rows(cur, company, supplier_id)[0]

    def update(self, supplier_id, data, user, headers):
        expected = data.get('relationshipVersion')
        if type(expected) is not int or expected < 1:
            raise HTTPException(422, 'Обновите карточку поставщика перед сохранением')
        with self.transaction(user, headers, write=True, claimed_company_id=data.get('companyId')) as (cur, company, actor):
            cur.execute('SELECT * FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s AND platform_account_id=%s FOR UPDATE',
                        (company['id'], supplier_id, company['platform_account_id']))
            link = cur.fetchone()
            if not link:
                raise HTTPException(404, 'Поставщик не добавлен в каталог этой компании')
            if link['version'] != expected:
                raise HTTPException(409, 'Карточка уже изменена. Обновите список перед сохранением')
            cur.execute('SELECT * FROM suppliers WHERE id=%s FOR SHARE', (supplier_id,))
            supplier = cur.fetchone()
            if not supplier:
                raise HTTPException(409, 'Общая карточка поставщика отсутствует')
            for key, column in PUBLIC_FIELDS.items():
                value = data.get(key, data.get(column))
                if value is not None and str(value or '').strip() != str(supplier.get(column) or '').strip():
                    raise HTTPException(409, 'Общие реквизиты меняет поставщик или администратор платформы')
            values = relationship_values(data, link)
            columns = list(LINK_FIELDS.values())
            cur.execute('UPDATE company_supplier_links SET ' + ','.join(c + '=%s' for c in columns)
                        + ',profile=%s,version=version+1 WHERE id=%s',
                        [values[c] for c in columns] + [psycopg2.extras.Json(values['profile']), link['id']])
            self.audit(cur, actor, company, link['id'], 'supplier_relationship_updated')
            return self.rows(cur, company, supplier_id)[0]
