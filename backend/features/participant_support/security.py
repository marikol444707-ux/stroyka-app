"""No credentials, request bodies, raw URLs or client-assigned ownership in audit."""
import logging
import os

from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def validate_storage_configuration(public_mount, storage_backend, s3_acl):
    if os.getenv('PARTICIPANT_SUPPORT_ACCESS_ENABLED', '0') != '1':
        return
    if public_mount or (storage_backend == 's3' and str(s3_acl or '').strip().lower() not in ('', 'private', 'bucket-owner-full-control')):
        raise RuntimeError('Support access requires private storage and PUBLIC_UPLOADS_MOUNT_ENABLED=false')


def record_denial(get_db, user, *, surface, method='GET', status=403, access_id=None):
    if user.get('role') != 'platform_support' or os.getenv('PARTICIPANT_SUPPORT_ACCESS_ENABLED', '0') != '1':
        return
    conn = None
    try:
        conn = get_db()
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='1s'; SET LOCAL lock_timeout='1s'")
            # Resolve ownership from a grant assigned to this actor only. A copied UUID
            # and X-Company-Id never attribute a probe to another buyer's history.
            grant = None
            if access_id:
                cur.execute('SELECT id,company_id,platform_account_id,ticket_id FROM participant_support_access WHERE id=%s AND assignee_id=%s',
                            (str(access_id), user['id']))
                grant = cur.fetchone()
            method = method if method in ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS') else 'OTHER'
            cur.execute('''INSERT INTO participant_support_denials(actor_id,surface,method,status_code,access_id,company_id,platform_account_id,ticket_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',
                (user['id'], surface, method, status, str(grant['id']) if grant else None,
                 grant['company_id'] if grant else None, grant['platform_account_id'] if grant else None, grant['ticket_id'] if grant else None))
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        # Denial remains final even if audit storage is unavailable. No exception
        # text is logged: a database error may contain sensitive SQL parameters.
        logger.error('SUPPORT_DENIAL_AUDIT_UNAVAILABLE')
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def surface_for_path(path):
    if path.startswith(('/tenant-files/', '/uploads/')):
        return 'file'
    if path.startswith(('/agent-jobs', '/ai-control/')):
        return 'job'
    return 'business'
