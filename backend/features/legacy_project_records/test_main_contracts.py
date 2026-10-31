"""Compile only selected pure handlers from main; never import/start the application."""
import ast
import json
from contextlib import contextmanager
from pathlib import Path
import unittest
from fastapi import Depends, HTTPException, Request
from .scope import owned_query, require_record

ROOT=Path(__file__).resolve().parents[3]
SOURCE=(ROOT/'backend/main.py').read_text()
TREE=ast.parse(SOURCE)

class Cursor:
    def __init__(self, ones=(), rows=()): self.ones=list(ones);self.rows=rows;self.calls=[]
    def execute(self,sql,params=()): self.calls.append((' '.join(sql.split()),params))
    def fetchone(self): return self.ones.pop(0) if self.ones else None
    def fetchall(self):
        if 'supplier_catalog' in self.calls[-1][0]: return []
        return self.rows

class Scope:
    def __init__(self,cur): self.cur=cur;self.committed=False
    @contextmanager
    def transaction(self,*args,write=False,**kwargs):
        yield self.cur,[{'id':1,'companyId':3,'role':'директор'}]
        self.committed=write
    def visible(self,*args): return 'p.company_id=%s',[3]
    def parent(self,*args): return {'companyId':3,'id':7,'name':'Учебный объект'}

def handlers(cur):
    scope=Scope(cur)
    ns={'Depends':Depends,'Request':Request,'HTTPException':HTTPException,'get_current_user':lambda:{},
        'MATERIAL_PRICE_HISTORY_ROLES':('директор',),'PROJECT_DOCUMENT_ROLES':('директор',),
        'JOURNAL_WRITE_ROLES':('директор',),'LEADERSHIP_ROLES':('директор',),
        'project_record_scope':scope,'visible_project_names':lambda actor:None,
        'package_access_filter':lambda actor,column:('',[]),'owned_project_query':owned_query,
        'require_owned_project_record':require_record,'DAILY_WORK_ACT_SOURCE_TYPE':'daily_work',
        'INTERIM_ACT_LOCKED_STATUSES':('Оплачен',),'json':json,
        'resolve_project_parent':lambda cur,actor,**kwargs:{'id':7,'companyId':actor['companyId'],'name':kwargs['project_name']},
        '_row_get':lambda row,key,index,default=None:row.get(key,default) if isinstance(row,dict) else row[index]}
    names={'material_price_history','list_tb_journal','create_tb_entry','delete_tb_entry','_room_work_duplicate','_sync_daily_interim_act_group'}
    for node in TREE.body:
        if isinstance(node,ast.FunctionDef) and node.name in names:
            import copy
            node=copy.deepcopy(node);node.decorator_list=[]
            exec(compile(ast.Module(body=[node],type_ignores=[]),'selected_main_handler','exec'),ns)
    return ns,scope

class MainContractTests(unittest.TestCase):
    def test_price_history_filters_before_statistics(self):
        cur=Cursor(rows=[('Кабель',101,'м',1,'Учебный объект','2026-01-01','Учебный поставщик')])
        ns,_=handlers(cur);result=ns['material_price_history']('Кабель',_current_user={})
        self.assertIn('WHERE ((h.company_id=%s))',cur.calls[0][0])
        self.assertEqual(cur.calls[0][1],[3,'%Кабель%'])
        self.assertEqual(result['stats']['avg'],101)
    def test_tb_create_writes_resolved_owner(self):
        cur=Cursor(ones=[(42,)]);ns,scope=handlers(cur)
        self.assertEqual(ns['create_tb_entry']({'projectName':'Учебный объект'},current_user={}),{'id':42,'ok':True})
        self.assertEqual(cur.calls[0][1][:3],(3,7,'Учебный объект'))
        self.assertTrue(scope.committed)
    def test_tb_missing_owner_stops_delete(self):
        cur=Cursor();ns,scope=handlers(cur)
        with self.assertRaises(HTTPException) as error: ns['delete_tb_entry'](42,current_user={})
        self.assertEqual(error.exception.status_code,404)
        self.assertFalse(scope.committed)
        self.assertEqual(len(cur.calls),1)
    def test_room_duplicate_never_matches_by_name_without_company(self):
        cur=Cursor();ns,_=handlers(cur)
        with self.assertRaises(HTTPException): ns['_room_work_duplicate'](cur,'Одинаковое имя',room_id=5,description='Работа')
        self.assertEqual(cur.calls,[])
        ns['_room_work_duplicate'](cur,'Одинаковое имя',room_id=5,description='Работа',company_id=3)
        self.assertIn('WHERE company_id=%s AND project=%s',cur.calls[0][0])
        self.assertEqual(cur.calls[0][1][:2],[3,'Одинаковое имя'])
    def test_daily_act_stores_source_owner_and_uses_company_filter(self):
        cur=Cursor(ones=[None,None,(77,)],rows=[{'id':11,'execution_total':50,'photo_url':''}]);ns,_=handlers(cur)
        result=ns['_sync_daily_interim_act_group'](cur,project='Учебный объект',company_id=3,master_id=5,work_date='2026-01-01')
        self.assertEqual(result,77)
        self.assertIn('WHERE company_id=%s AND project=%s',cur.calls[0][0])
        insert=next(call for call in cur.calls if call[0].startswith('INSERT'))
        self.assertEqual(insert[1][:2],(3,7))
    def test_bootstrap_creates_affected_tables_before_the_first_alter(self):
        for table in ('estimates','warehouse_main','work_journal','interim_acts','hidden_works_acts'):
            self.assertLess(SOURCE.index('CREATE TABLE IF NOT EXISTS '+table+' ('),SOURCE.index('ALTER TABLE '+table+' '),table)
    def test_record_scope_defined_before_registration_consumers(self):
        assignment=next(n for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='project_record_scope' for t in n.targets))
        for node in TREE.body:
            if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):
                for arg in node.value.args:
                    if isinstance(arg,ast.Dict) and any(isinstance(v,ast.Name) and v.id=='project_record_scope' for v in arg.values):
                        self.assertLess(assignment.lineno,node.lineno)
