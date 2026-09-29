"""Resolve legacy AOSR access through the current company membership."""
import psycopg2.extras
from fastapi import HTTPException


def internal_actor(cur, scope, user, request, act_id, roles):
    with cur.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as context_cur:
        headers=request.headers if request else {}
        context=scope.resolve_context(context_cur,user,None,'write',
            x_company_id=headers.get('x-company-id'),x_company_mode=headers.get('x-company-mode'))
        actors=[a for a in scope.effective_actors(user,context) if a.get('role') in roles]
    if len(actors)!=1:
        raise HTTPException(403,'Нет прав на изменение акта в выбранной компании')
    actor=actors[0]
    where,params=scope.visible([actor],roles)
    cur.execute('SELECT h.id FROM hidden_works_acts h JOIN projects p '
                'ON p.company_id=h.company_id AND p.name=h.project_name '
                'WHERE h.id=%s AND '+where+
                ' AND NOT EXISTS (SELECT 1 FROM projects other WHERE other.company_id=p.company_id '
                'AND other.name=p.name AND other.id<>p.id) FOR UPDATE OF h,p',(act_id,*params))
    if not cur.fetchone():
        raise HTTPException(404,'Акт не найден в доступном объекте выбранной компании')
    return actor
