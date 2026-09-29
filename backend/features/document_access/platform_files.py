"""Platform staff may read exact financial attachments, not arbitrary tenant files."""
from fastapi import HTTPException

_CONTRACT_READ_ROLES = frozenset(('system_owner', 'platform_admin', 'platform_support', 'billing_admin'))
_BILLING_READ_ROLES = frozenset(('system_owner', 'platform_admin', 'billing_admin'))


def authorize_platform_document(cur, user, row, action):
    context = row.get('context')
    if context not in ('platform-client-contract', 'platform-billing-document'):
        return False
    if action != 'read':
        raise HTTPException(409, 'Финансовый документ хранится вместе с историей договора и оплаты')
    allowed = _CONTRACT_READ_ROLES if context == 'platform-client-contract' else _BILLING_READ_ROLES
    if user.get('role') not in allowed:
        return False
    if row.get('project_id') is not None:
        raise HTTPException(403, 'Файл не является документом платформы')
    protected_url = '/tenant-files/{}/content'.format(row['id'])
    if context == 'platform-client-contract':
        cur.execute('''SELECT pc.id FROM platform_client_contracts pc
            JOIN companies c ON c.id=pc.company_id AND c.platform_account_id=pc.platform_account_id
            WHERE pc.company_id=%s AND (pc.generated_file_url=%s OR pc.signed_file_url=%s) LIMIT 1''',
            (row['company_id'], protected_url, protected_url))
    else:
        cur.execute('''SELECT d.id FROM platform_billing_documents d
            JOIN companies c ON c.id=d.company_id AND c.platform_account_id=d.platform_account_id
            WHERE d.company_id=%s AND d.file_url=%s LIMIT 1''', (row['company_id'], protected_url))
    if not cur.fetchone():
        raise HTTPException(403, 'Файл не связан с финансовым документом платформы')
    return True
