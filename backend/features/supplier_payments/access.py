"""Current financial actor authorization only; not a document/payment resolver.

Call in the engine transaction before replay. The caller retains all locks until
commit/rollback. Session authentication, canonical document/payer discovery and
new-payment policy remain separate runtime gates; no routes register this helper.
"""
from collections.abc import Mapping

from fastapi import HTTPException

from .commands import positive_id


def _row(cur, row):
    return dict(row) if isinstance(row, Mapping) else dict(zip((c[0] for c in cur.description), row))


def build_payment_access(deps, *, operation='update'):
    """Build an actor resolver using the existing company and scope policies.

    Returns the owning-company actor, never user credentials. A distinct payer
    needs its own current financial membership, not ownership of the buyer's
    project. Project/package scope is checked on the document's owning actor.
    All arguments must come from authenticated identity / canonical documents.
    Read callers must explicitly request operation='read'; engine callers keep
    the default update authority. Subscription write gating remains middleware.
    """
    if operation not in ('read', 'update'):
        raise ValueError('Payment access operation must be read or update')
    resolve_actor = deps['resolve_resource_company_actor']
    finance_roles = tuple(deps['finance_roles'])
    platform_roles = tuple(deps['platform_staff_roles'])
    account_roles = tuple(deps['client_account_roles'])
    require_project_access = deps['require_project_access']
    has_package_access = deps['has_package_access']

    def authorize(cur, actor_id, company_id, project, work_package, payer_company_id=None):
        positive_id(actor_id)
        positive_id(company_id)
        if payer_company_id is not None:
            positive_id(payer_company_id)
        if cur.connection.autocommit:
            raise RuntimeError('Payment authorization requires an explicit transaction')
        cur.execute('''SELECT id,name,email,role,company_id,platform_account_id,
                              project_name,assigned_projects,assigned_packages,active
                       FROM users WHERE id=%s AND active=TRUE FOR SHARE''', (actor_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(403, 'Пользователь отключён или не найден')
        user = _row(cur, row)
        if user['role'] == 'поставщик' or user['role'] in platform_roles:
            raise HTTPException(403, 'Нет финансовых полномочий компании')

        company_ids = sorted({company_id, payer_company_id if payer_company_id is not None else company_id})
        cur.execute('SELECT id FROM companies WHERE id=ANY(%s) ORDER BY id FOR SHARE', (company_ids,))
        locked_companies = {_row(cur, row)['id'] for row in cur.fetchall()}
        if locked_companies != set(company_ids):
            raise HTTPException(403, 'Компания не найдена')
        # Lock inactive rows too: a revocation already in flight must finish
        # before the context is resolved. An unlocked newly inserted membership
        # must never become a fallback authority during the subsequent lookup.
        cur.execute('''SELECT id,company_id FROM user_company_roles
                       WHERE user_id=%s AND company_id=ANY(%s)
                       ORDER BY company_id,id FOR SHARE''', (actor_id, company_ids))
        locked_memberships = {(r['id'], r['company_id']) for r in
                              (_row(cur, row) for row in cur.fetchall())}
        actors = {}
        for target_id in company_ids:
            context, actor = resolve_actor(
                cur, user, target_id, operation, allowed_roles=finance_roles,
                platform_staff_roles=platform_roles, client_account_roles=account_roles)
            if (context.get('mode') != 'company' or context.get('companyId') != target_id
                    or context.get('source') != 'membership'
                    or (operation != 'read' and context.get('readOnly'))
                    or not context.get('active') or not context.get('companyActive')
                    or context.get('role') not in finance_roles
                    or (context.get('membershipId'), target_id) not in locked_memberships):
                raise HTTPException(403, 'Требуется активное финансовое членство в компании')
            actors[target_id] = actor
        actor = actors[company_id]
        require_project_access(actor, project)
        if not has_package_access(actor, work_package or 'Основная'):
            raise HTTPException(403, 'Нет доступа к пакету документа')
        return actor

    return authorize
