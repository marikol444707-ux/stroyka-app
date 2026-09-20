"""Read-only receipts; legacy project names must resolve uniquely within a company."""
from fastapi import Depends, HTTPException, Request


def register_customer_payments(app, scope, authenticated):
    @app.get('/project-payments/customer-visible')
    def receipts(current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, ('заказчик',)) as (cur, actors):
            for actor in actors:
                names = scope.visible_project_names(actor) or []
                cur.execute('SELECT name FROM projects WHERE company_id=%s AND name=ANY(%s) '
                            'GROUP BY name HAVING COUNT(*)>1',
                            (actor.get('companyId') or actor.get('company_id'), names))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail='Объект старых платежей неоднозначен. Подрядчику нужно уточнить привязку.')
            where, params = scope.visible(actors, ('заказчик',))
            cur.execute('SELECT p.id,p.company_id,p.name FROM projects p WHERE ' + where, params)
            projects = cur.fetchall()
            result = []
            for project_id, company_id, name in projects:
                cur.execute("""SELECT p.id,p.amount,p.date FROM project_payments p
                    WHERE p.company_id=%s AND p.project_name=%s
                      AND p.company_scope_verified=TRUE AND p.amount>0
                      AND NOT EXISTS (
                        SELECT 1 FROM project_payments r
                        WHERE r.company_id=p.company_id AND r.project_name=p.project_name
                          AND r.company_scope_verified=TRUE
                          AND COALESCE(r.work_package,'')=COALESCE(p.work_package,'')
                          AND r.amount=-p.amount
                          AND COALESCE(r.note,'')='Сторно платежа #' || p.id::text ||
                            CASE WHEN COALESCE(p.note,'')='' THEN '' ELSE ': ' || p.note END
                      ) ORDER BY p.date DESC NULLS LAST,p.id DESC""", (company_id,name))
                for row_id, amount, date in cur.fetchall():
                    result.append({'id': row_id, 'companyId': company_id, 'projectId': project_id,
                                   'amount': amount, 'date': str(date) if date else ''})
            return result
