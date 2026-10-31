"""Timesheets inherit staff ownership and effective company membership."""
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel


class TimesheetModel(BaseModel):
    staffId: int
    day: str


def staff_visibility(actors, roles, visible_project_names):
    clauses, params = [], []
    for actor in actors:
        company = actor.get('companyId') or actor.get('company_id')
        if not company or actor.get('role') not in roles:
            continue
        names = visible_project_names(actor)
        if names == []:
            continue
        clause = 's.company_id=%s'
        values = [company]
        if names is not None:
            clause += ' AND s.project=ANY(%s)'
            values.append(names)
        clauses.append('(' + clause + ')')
        params.extend(values)
    return ('(' + ' OR '.join(clauses) + ')', params) if clauses else ('FALSE', [])


def register_timesheet_module(app, deps):
    scope = deps['record_scope']
    authenticated = deps['get_current_user']
    read_roles = tuple(deps['staff_view_roles'])
    write_roles = (*deps['staff_manage_roles'], 'прораб', 'главный_инженер')

    def visibility(actors, roles):
        return staff_visibility(actors, roles, scope.visible_project_names)

    @app.get('/timesheet/{staff_id}')
    def get_timesheet(staff_id: int, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = visibility(actors, read_roles)
            cur.execute('SELECT s.id FROM staff s WHERE s.id=%s AND ' + where, (staff_id,*params))
            if not cur.fetchone():
                raise HTTPException(404, 'Сотрудник не найден в выбранной компании')
            cur.execute('SELECT day FROM timesheet WHERE staff_id=%s', (staff_id,))
            days = [row[0] for row in cur.fetchall()]
        return {'days': days}

    @app.post('/timesheet')
    def toggle_timesheet(data: TimesheetModel, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            where, params = visibility(actors, write_roles)
            cur.execute("SELECT s.name,COALESCE(s.project,'') FROM staff s WHERE s.id=%s AND " + where +
                        ' FOR UPDATE OF s', (data.staffId,*params))
            staff = cur.fetchone()
            if not staff:
                raise HTTPException(404, 'Сотрудник не найден в выбранной компании')
            cur.execute('SELECT id FROM timesheet WHERE staff_id=%s AND day=%s', (data.staffId,data.day))
            if cur.fetchone():
                cur.execute('DELETE FROM timesheet WHERE staff_id=%s AND day=%s', (data.staffId,data.day))
                action = 'timesheet_remove'
            else:
                cur.execute('INSERT INTO timesheet (staff_id,day) VALUES (%s,%s)', (data.staffId,data.day))
                action = 'timesheet_add'
            actor = actors[0]
        deps['log_audit'](actor.get('name',''),actor.get('role',''),action,'timesheet',data.staffId,
                          ('Табель: ' + str(staff[0]) + ', день ' + str(data.day))[:250],staff[1])
        return {'ok': True}

    @app.get('/timesheet')
    def get_timesheet_all(request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = visibility(actors, read_roles)
            cur.execute('SELECT t.staff_id,t.day FROM timesheet t JOIN staff s ON s.id=t.staff_id WHERE ' + where, params)
            rows = cur.fetchall()
        return [{'staffId': row[0], 'day': row[1]} for row in rows]
