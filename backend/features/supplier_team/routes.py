"""Same-cabinet supplier team API; buyer roles grant no supplier authority."""
from fastapi import Depends
from .policy import access_ids,leader_ids
from .service import transaction,require_enabled,customers,assign,set_member_active,lock_leader
from .invitations import create_invite,revoke_invite


def register_supplier_team_module(app,deps):
    auth=deps['require_roles']('поставщик')
    get_db=deps['get_db']

    @app.get('/supplier-team')
    def context(user:dict=Depends(auth)):
        require_enabled()
        with transaction(get_db) as cur:
            ids=access_ids(cur,user);leaders=set(leader_ids(cur,user))
            cur.execute('SELECT id,name FROM suppliers WHERE id=ANY(%s::int[]) ORDER BY id',(ids,))
            return [{'id':r['id'],'name':r['name'],'role':'leader' if r['id'] in leaders else 'manager'} for r in cur.fetchall()]

    @app.get('/supplier-team/customers')
    def assigned_customers(user:dict=Depends(auth)):
        require_enabled()
        with transaction(get_db) as cur:
            cur.execute('''SELECT DISTINCT c.id,c.name FROM supplier_customer_assignments a
                JOIN supplier_team_members m ON m.id=a.member_id AND m.supplier_id=a.supplier_id
                JOIN users u ON u.id=m.user_id
                JOIN companies c ON c.id=a.company_id
                WHERE m.user_id=%s AND m.active AND m.role='manager'
                  AND u.role='поставщик' AND COALESCE(u.active,TRUE) ORDER BY c.name,c.id''',(user['id'],))
            return [dict(r) for r in cur.fetchall()]

    @app.get('/supplier-team/{supplier_id}')
    def team(supplier_id:int,user:dict=Depends(auth)):
        require_enabled()
        with transaction(get_db) as cur:
            lock_leader(cur,supplier_id,user['id'])
            customer_rows=customers(cur,supplier_id,user['id'])
            cur.execute('''SELECT m.id,m.role,m.active,m.version,u.name,u.email,COALESCE(u.active,TRUE) AS "userActive"
                FROM supplier_team_members m JOIN users u ON u.id=m.user_id WHERE m.supplier_id=%s ORDER BY u.name,m.id''',(supplier_id,))
            members=[dict(r) for r in cur.fetchall()]
            cur.execute('''SELECT i.id,i.code,i.used,i.expires_at AS "expiresAt",b.revoked_at AS "revokedAt",
                (NOT i.used AND b.revoked_at IS NULL AND i.expires_at>NOW()
                 AND COALESCE(u.active,TRUE) AND u.role='поставщик' AND u.supplier_team_epoch=b.issuer_user_epoch
                 AND ((b.issuer_member_id IS NULL AND s.user_id=u.id)
                      OR (m.active AND m.role='leader' AND m.user_id=u.id AND m.supplier_id=s.id
                          AND m.version=b.issuer_member_version))) IS TRUE AS valid
                FROM supplier_team_invites b JOIN invite_codes i ON i.id=b.invite_id
                JOIN suppliers s ON s.id=b.supplier_id JOIN users u ON u.id=b.created_by_user_id
                LEFT JOIN supplier_team_members m ON m.id=b.issuer_member_id
                WHERE b.supplier_id=%s ORDER BY i.id DESC LIMIT 100''',(supplier_id,))
            invites=[dict(r) for r in cur.fetchall()]
            cur.execute('''SELECT o.id,o.action,o.details,o.result,o.created_at AS "createdAt",u.name AS "actorName"
                FROM supplier_team_operations o JOIN users u ON u.id=o.actor_id
                WHERE o.supplier_id=%s ORDER BY o.id DESC LIMIT 100''',(supplier_id,))
            return {'customers':customer_rows,'members':members,'invites':invites,'history':[dict(r) for r in cur.fetchall()]}

    @app.post('/supplier-team/{supplier_id}/commands')
    def command(supplier_id:int,data:dict,user:dict=Depends(auth)):
        require_enabled()
        from fastapi import HTTPException
        handlers={'assign_customer':assign,'member_active':set_member_active,'invite_manager':create_invite,'revoke_invite':revoke_invite}
        handler=handlers.get(data.get('action'))
        if not handler:raise HTTPException(422,'Неизвестное действие')
        # Reject extra fields so audit never stores untrusted credentials or secrets.
        fields={'assign_customer':{'companyId','memberId','version'},'member_active':{'memberId','active','version','reason'},
                'invite_manager':{'expiresInDays'},'revoke_invite':{'inviteId'}}
        if set(data)-fields[data['action']]-{'action','requestId'}:raise HTTPException(422,'Лишние поля операции')
        with transaction(get_db) as cur:
            return handler(cur,supplier_id,user['id'],data)
