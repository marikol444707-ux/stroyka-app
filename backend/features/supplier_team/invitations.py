"""Single-use manager invitations; the binding is recognized even with rollout off."""
from datetime import datetime,timedelta
import secrets
from fastapi import HTTPException
from .service import require_enabled,lock_leader,replay,record,integer


def binding_for(cur,invite_id):
    # Registration must also work before migration rollout, but never ignore an
    # existing binding when the feature flag is disabled.
    cur.execute("SELECT to_regclass('public.supplier_team_invites') AS relation")
    if not cur.fetchone()['relation']:return None
    cur.execute('SELECT * FROM supplier_team_invites WHERE invite_id=%s',(invite_id,))
    return cur.fetchone()


def validate_binding(cur,invite,lock=False):
    binding=binding_for(cur,invite['id'])
    if not binding:return None
    require_enabled()
    if binding['revoked_at'] or invite.get('used') or invite['role']!='поставщик':
        raise HTTPException(400,'Приглашение недействительно')
    if not invite.get('expires_at') or invite['expires_at']<datetime.now():
        raise HTTPException(400,'Срок приглашения истёк')
    if lock:
        supplier=lock_leader(cur,binding['supplier_id'],binding['created_by_user_id'])
    else:
        from .policy import leader_policy
        sql,params=leader_policy(binding['created_by_user_id'],'s.id')
        cur.execute('SELECT s.id,s.name,s.user_id FROM suppliers s WHERE s.id=%s AND '+sql,[binding['supplier_id']]+params)
        supplier=cur.fetchone()
        if not supplier:raise HTTPException(400,'Приглашение больше не действует')
    cur.execute('SELECT supplier_team_epoch FROM users WHERE id=%s', (binding['created_by_user_id'],))
    issuer = cur.fetchone()
    if not issuer or issuer['supplier_team_epoch'] != binding['issuer_user_epoch']:
        raise HTTPException(400,'Запросите новое приглашение у руководителя')
    if binding['issuer_member_id'] is None:
        if supplier['user_id']!=binding['created_by_user_id']:
            raise HTTPException(400,'Приглашение больше не действует')
    else:
        cur.execute('''SELECT id FROM supplier_team_members WHERE id=%s AND supplier_id=%s AND user_id=%s
            AND active AND role='leader' AND version=%s''',
            (binding['issuer_member_id'],binding['supplier_id'],binding['created_by_user_id'],binding['issuer_member_version']))
        if not cur.fetchone():raise HTTPException(400,'Запросите новое приглашение у руководителя')
    return {**dict(binding),'supplierName':supplier['name']}


def create_invite(cur,supplier_id,user_id,data):
    supplier=lock_leader(cur,supplier_id,user_id)
    days=integer(data.get('expiresInDays',14))
    if days>90:raise HTTPException(422,'Срок приглашения не более 90 дней')
    operation=replay(cur,supplier_id,user_id,data,'invite_manager')
    if operation[3] is not None:
        invite_id=operation[3]['inviteId']
    else:
        member_id=version=None
        if supplier['user_id']!=user_id:
            cur.execute("SELECT id,version FROM supplier_team_members WHERE supplier_id=%s AND user_id=%s AND active AND role='leader'",(supplier_id,user_id))
            member=cur.fetchone();member_id=member['id'];version=member['version']
        cur.execute('''INSERT INTO invite_codes(code,role,supplier_id,preset_name,expires_at)
            VALUES(%s,'поставщик',%s,%s,%s) RETURNING id''',
            (secrets.token_hex(10).upper(),supplier_id,supplier['name'],datetime.now()+timedelta(days=days)))
        invite_id=cur.fetchone()['id']
        cur.execute('SELECT supplier_team_epoch FROM users WHERE id=%s',(user_id,))
        epoch=cur.fetchone()['supplier_team_epoch']
        cur.execute('''INSERT INTO supplier_team_invites(invite_id,supplier_id,created_by_user_id,issuer_member_id,issuer_member_version,issuer_user_epoch)
            VALUES(%s,%s,%s,%s,%s,%s)''',(invite_id,supplier_id,user_id,member_id,version,epoch))
        record(cur,supplier_id,user_id,operation,'invite_manager',{'inviteId':invite_id})
    cur.execute('''SELECT i.id,i.code,i.expires_at AS "expiresAt",i.used,b.revoked_at AS "revokedAt"
        FROM invite_codes i JOIN supplier_team_invites b ON b.invite_id=i.id WHERE i.id=%s''',(invite_id,))
    return dict(cur.fetchone())


def revoke_invite(cur,supplier_id,user_id,data):
    invite_id=integer(data.get('inviteId'))
    # Match registration's invite -> supplier order; do not lock invite in other commands.
    cur.execute('SELECT id FROM invite_codes WHERE id=%s FOR UPDATE',(invite_id,));cur.fetchone()
    lock_leader(cur,supplier_id,user_id)
    operation=replay(cur,supplier_id,user_id,data,'revoke_invite')
    if operation[3] is not None:return operation[3]
    cur.execute('UPDATE supplier_team_invites SET revoked_at=COALESCE(revoked_at,NOW()) WHERE invite_id=%s AND supplier_id=%s RETURNING invite_id',(invite_id,supplier_id))
    if not cur.fetchone():raise HTTPException(404,'Приглашение не найдено')
    return record(cur,supplier_id,user_id,operation,'revoke_invite',{'inviteId':invite_id,'revoked':True})
