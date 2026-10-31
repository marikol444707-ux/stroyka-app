"""In-memory fixture for route unit tests. Never opens a database."""
from contextlib import contextmanager
from fastapi import HTTPException
from ..customer_cabinet.record_scope import project_visibility

class FakeScope:
    def __init__(self, cursor, connection):
        self.cursor, self.connection = cursor, connection
        self.visible_project_names = lambda actor: None
    def resolve_context(self,*args,**kwargs): return {'companyId':3}
    def effective_actors(self,user,context): return [{**user,'role':user.get('role','директор'),'companyId':3}]
    def visible(self,actors,roles): return project_visibility(actors,roles,self.visible_project_names)
    def parent(self,cur,actor,data,roles):
        if data.get('projectName')=='чужой': raise HTTPException(403,'Нет доступа')
        return {'id':7,'companyId':3,'name':data.get('projectName','Объект')}
    @contextmanager
    def transaction(self,user,request,roles,write=False):
        yield self.cursor,self.effective_actors(user,{})
        if write: self.connection.commit()
        self.connection.close()


def fixture_scope(cursor, connection):
    # Existing fixtures explicitly model successful owner lookups. Negative
    # ownership cases use their own cursor and never this convenience fixture.
    old_fetchone=cursor.fetchone
    def fetchone():
        sql=cursor.calls[-1][0] if cursor.calls else ''
        if sql.startswith('SELECT r.id FROM '): return (7,)
        return old_fetchone()
    cursor.fetchone=fetchone
    type(cursor).__enter__=lambda self:self
    type(cursor).__exit__=lambda *args:False
    if not hasattr(connection,'commit'): connection.commit=lambda:None
    if not hasattr(connection,'rollback'): connection.rollback=lambda:None
    if not hasattr(connection,'closed'): connection.closed=False
    return FakeScope(cursor,connection)
