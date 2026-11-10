"""Finance-only tool purchase review, allocation and confirmed cash refunds."""
from typing import Optional

from fastapi import Depends, Header
import psycopg2.extras

from ..accountable_payments.advances import lock_ledger
from . import service


def register_tool_deductions(app, deps, company_actor):
    get_user = deps['get_current_user']
    roles = tuple(deps['finance_roles'])

    def run(user, company, mode, callback, write=False):
        conn = deps['get_db']()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if write:
                lock_ledger(cur)
            company_id, actor = company_actor(cur, user, 'write' if write else 'read', company, mode, roles)
            result = callback(cur, company_id, actor)
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get('/tool-deductions')
    def get_deductions(current_user: dict = Depends(get_user),
        x_company_id: Optional[str] = Header(default=None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(default=None, alias='X-Company-Mode')):
        def read(cur, company, actor):
            sources = service.candidates(cur, company)
            cur.execute('''SELECT d.*,s.name AS staff_name,p.name AS project_name,COALESCE(d.snapshot->>'name',t.name) AS tool_name
                FROM tool_deduction_sources d JOIN staff s ON s.id=d.staff_id AND s.company_id=d.company_id
                JOIN projects p ON p.id=d.project_id AND p.company_id=d.company_id
                JOIN tools t ON t.id=d.tool_id AND t.company_id=d.company_id
                WHERE d.company_id=%s ORDER BY d.id DESC''', (company,))
            reviewed = [dict(r) for r in cur.fetchall()]
            for row in reviewed:
                cur.execute('SELECT * FROM tool_deduction_allocations WHERE source_id=%s AND company_id=%s ORDER BY id', (row['id'], company))
                row['allocations'] = [dict(r) for r in cur.fetchall()]
                cur.execute('SELECT revision,actor,change,created_at FROM tool_deduction_events WHERE source_id=%s AND company_id=%s ORDER BY revision DESC', (row['id'], company))
                row['events'] = [dict(r) for r in cur.fetchall()]
            keys = {r['source_key'] for r in reviewed}
            cur.execute('SELECT id,name FROM staff WHERE company_id=%s AND company_scope_verified IS TRUE ORDER BY name,id', (company,))
            staff = [dict(r) for r in cur.fetchall()]
            cur.execute('SELECT id,name FROM projects WHERE company_id=%s ORDER BY name,id', (company,))
            projects = [dict(r) for r in cur.fetchall()]
            return {'companyId': company, 'sources': [r for r in sources if r['sourceKey'] not in keys],
                    'reviewed': reviewed, 'staff': staff, 'projects': projects}
        return run(current_user, x_company_id, x_company_mode, read)

    @app.post('/tool-deductions/review')
    def review(data: dict, current_user: dict = Depends(get_user),
        x_company_id: Optional[str] = Header(default=None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(default=None, alias='X-Company-Mode')):
        return run(current_user, x_company_id, x_company_mode,
                   lambda cur, company, actor: service.review_source(cur, company, data, actor), True)

    @app.put('/tool-deductions/{source_id}/allocations')
    def allocate(source_id: int, data: dict, current_user: dict = Depends(get_user),
        x_company_id: Optional[str] = Header(default=None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(default=None, alias='X-Company-Mode')):
        def change(cur, company, actor):
            if deps.get('lock_settlement'):
                deps['lock_settlement'](cur)
            if data.get('actId'):
                deps['require_row_project_access'](cur, 'interim_acts', data['actId'], actor, 'project')
            return service.allocate(cur, company, source_id, data, actor,
                                    deps['require_legacy_interim'], deps['has_package_access'])
        return run(current_user, x_company_id, x_company_mode, change, True)

    @app.post('/tool-deductions/{source_id}/refunds')
    def refund(source_id: int, data: dict, current_user: dict = Depends(get_user),
        x_company_id: Optional[str] = Header(default=None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(default=None, alias='X-Company-Mode')):
        return run(current_user, x_company_id, x_company_mode,
            lambda cur, company, actor: service.refund(cur, company, source_id, data, actor, deps['has_package_access']), True)

    @app.get('/salary-tool-deductions')
    def salary(month: str, current_user: dict = Depends(get_user),
        x_company_id: Optional[str] = Header(default=None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(default=None, alias='X-Company-Mode')):
        def read(cur, company, actor):
            cur.execute('SELECT id FROM staff WHERE company_id=%s AND company_scope_verified IS TRUE', (company,))
            staff_ids = [r['id'] for r in cur.fetchall()]
            return {'companyId': company, 'month': month,
                    'rows': [service.salary_state(cur, company, staff_id, month) for staff_id in staff_ids]}
        return run(current_user, x_company_id, x_company_mode, read)
