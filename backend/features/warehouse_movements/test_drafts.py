"""Real AST-extracted routes and SQL helpers, no application startup/live DB config."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
import psycopg2
from fastapi import HTTPException
from . import drafts

ROUTES = ('prepare_warehouse_movement_draft', 'get_warehouse_movement_drafts',
          'cancel_warehouse_movement_draft', 'create_warehouse_movement')


def load_routes(namespace):
    tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
    names = set(ROUTES) | {'_movement_draft_company', '_authorize_movement_draft_command',
                          '_movement_draft_restricted', '_movement_draft_recovery_response'}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            node.returns = None
            for arg in node.args.args:
                arg.annotation = None
            node.args.defaults = [ast.Constant(None)] * len(node.args.defaults)
            nodes.append(node)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<routes>', 'exec'), namespace)
    return namespace


class Store:
    def __init__(self):
        self.state = {'drafts': {}, 'bindings': {}, 'ledger': {}}
        self.projects_available = True
        self.connections = []

    def connect(self):
        conn = Connection(self)
        self.connections.append(conn)
        return conn


class Connection:
    def __init__(self, store):
        self.store = store
        self.state = copy.deepcopy(store.state)
        self.commits = self.rollbacks = 0

    def cursor(self, **kwargs):
        return Cursor(self)

    def commit(self):
        self.store.state = copy.deepcopy(self.state)
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class Cursor:
    def __init__(self, conn):
        self.connection = conn
        self.row, self.rows = None, []

    def execute(self, sql, args=()):
        state = self.connection.state
        self.row, self.rows = None, []
        if sql.startswith('SELECT pg_advisory_xact_lock'):
            return
        if sql.startswith('SELECT id FROM projects'):
            self.rows = [{'id': 1}] if self.connection.store.projects_available and args[1] == f'Project {args[0]}' else []
        elif sql.startswith('SELECT draft_id,commands,complete'):
            if len(args) == 3:
                self.row = state['drafts'].get(tuple(args))
            else:
                self.rows = [v for k, v in state['drafts'].items() if k[:2] == tuple(args) and not v['complete']]
        elif sql.startswith('SELECT 1 FROM warehouse_movement_draft_commands'):
            self.row = state['bindings'].get(tuple(args[:2])) or state['ledger'].get(tuple(args[:2]))
        elif sql.startswith('INSERT INTO warehouse_movement_drafts('):
            company, actor, draft, commands = args
            state['drafts'][(company, actor, draft)] = {'draft_id': draft, 'commands': commands.adapted, 'complete': False}
        elif sql.startswith('INSERT INTO warehouse_movement_draft_commands('):
            company, actor, draft, command, digest = args
            state['bindings'][(company, command)] = {'actor': actor, 'draft': draft, 'payload_hash': digest, 'cancelled': False}
        elif sql.startswith('SELECT payload_hash,cancelled FROM warehouse_movement_draft_commands'):
            company, actor, draft, command = args
            binding = state['bindings'].get((company, command))
            if binding and binding['actor'] == actor and binding['draft'] == draft:
                self.row = binding
        elif sql.startswith('SELECT c.payload_hash,c.response'):
            company, actor, draft, command = args
            binding = state['bindings'].get((company, command))
            if binding and binding['actor'] == actor and binding['draft'] == draft:
                ledger = state['ledger'].get((company, command), {})
                self.row = {'expected_hash': binding['payload_hash'], 'payload_hash': ledger.get('payload_hash'),
                            'response': ledger.get('response'), 'cancelled': binding['cancelled']}
        elif sql.startswith('UPDATE warehouse_movement_draft_commands SET cancelled'):
            company, actor, draft, command = args
            binding = state['bindings'][(company, command)]
            assert binding['actor'] == actor and binding['draft'] == draft
            binding['cancelled'] = True
        elif sql.startswith('UPDATE warehouse_movement_drafts SET'):
            state['drafts'][tuple(args)]['complete'] = True
        elif sql.startswith('SELECT payload_hash,response'):
            self.row = state['ledger'].get(tuple(args))
        elif sql.startswith('INSERT INTO warehouse_movement_commands'):
            company, command, digest, response = args
            state['ledger'][(company, command)] = {'payload_hash': digest, 'response': response.adapted}
        elif sql.startswith('SELECT to_regclass('):
            self.row = {'present': False}
        else:
            raise AssertionError(f'Unexpected SQL: {sql}')

    def fetchone(self):
        return copy.deepcopy(self.row)

    def fetchall(self):
        return copy.deepcopy(self.rows)

    def close(self):
        pass


class DurableDraftTests(TestCase):
    def setUp(self):
        self.store = Store()
        self.user = {'id': 12, 'role': 'директор'}
        self.company = 2
        self.selected_role, self.selected_projects, self.selected_packages = 'директор', [], []
        self.access = Mock()
        self.worker = Mock(return_value={'id': 77})
        self.namespace = load_routes(dict(get_db=self.store.connect, psycopg2=psycopg2,
            os=SimpleNamespace(getenv=lambda *a: None), HTTPException=HTTPException,
            WarehouseMovementModel=lambda **kw: SimpleNamespace(**kw),
            WAREHOUSE_ROLES=('директор', 'зам_директора', 'кладовщик', 'снабженец', 'прораб'),
            PACKAGE_LIMIT_ROLES=('прораб',), MAIN_WAREHOUSE_WRITE_ROLES=('директор',),
            has_package_access=Mock(return_value=True), require_project_or_warehouse_access=self.access,
            _positive_int_or_none=lambda value: int(value) if value else None,
            _resolve_work_company_context=Mock(side_effect=lambda *a, **kw: self.company_context(kw['x_company_id'])),
            _apply_warehouse_movement=self.worker, _create_warehouse_movement_review_task_safely=Mock(),
            _run_project_ai_control_safely=Mock()))
        self.model = self.command()

    def company_context(self, company):
        return {'mode': 'company', 'companyId': int(company), 'companyIds': [int(company)],
                'effectiveRole': self.selected_role, 'assignedProjects': self.selected_projects,
                'assignedPackages': self.selected_packages, 'active': True, 'companyActive': True}

    def command(self):
        return SimpleNamespace(commandId=str(uuid4()), draftId=str(uuid4()), expectedActorUserId=12,
            materialName='Cable', fromLocation='Основной склад', toLocation='Project 2', quantity=2.0,
            unit='m', workPackage='', date='2026-10-18', createdBy='', notes='', invoiceId=None, invoiceLineIndex=None)

    def kwargs(self):
        return dict(x_company_id=str(self.company), x_company_mode='company', _current_user=self.user)

    def prepare(self, commands=None):
        commands = commands or [self.model]
        return self.namespace[ROUTES[0]](SimpleNamespace(draftId=commands[0].draftId, expectedActorUserId=12, commands=commands), **self.kwargs())

    def recover(self):
        return self.namespace[ROUTES[1]](expectedActorUserId=self.user['id'], **self.kwargs())

    def cancel(self):
        return self.namespace[ROUTES[2]](self.model.draftId, SimpleNamespace(expectedActorUserId=self.user['id']), **self.kwargs())

    def execute(self):
        return self.namespace[ROUTES[3]](self.model, **self.kwargs())

    def test_lost_prepare_response_recovers_exact_commands(self):
        first = self.prepare()
        self.assertEqual(self.recover()['drafts'], [first])
        self.assertEqual(self.prepare(), first)
        self.worker.assert_not_called()

    def test_lost_commit_response_recovers_retained_result_and_replays_once(self):
        self.prepare(); self.execute()
        result = self.recover()['drafts'][0]
        self.assertTrue(result['complete'])
        self.assertEqual(result['commands'][0]['response'], {'id':77})
        self.assertEqual(self.recover()['drafts'], [])
        self.assertEqual(self.prepare(), result)
        self.assertEqual(self.execute(), {'id':77})
        self.worker.assert_called_once()

    def test_missing_prepare_cannot_write(self):
        with self.assertRaises(HTTPException): self.execute()
        self.worker.assert_not_called()

    def test_pending_blocks_new_draft_and_payload_mutation(self):
        self.prepare()
        original = self.model
        self.model = self.command()
        with self.assertRaises(HTTPException): self.prepare()
        self.model = original
        for field, value in [('quantity',3), ('invoiceId',7), ('notes','changed')]:
            old = getattr(self.model,field); setattr(self.model,field,value)
            for action in (self.prepare,self.execute):
                with self.assertRaises(HTTPException) as error: action()
                self.assertEqual(error.exception.status_code,409)
            setattr(self.model,field,old)
        self.worker.assert_not_called()

    def test_partial_failure_retains_pending_then_retries(self):
        second = self.command(); second.draftId = self.model.draftId
        self.prepare([self.model,second]); self.execute(); self.model = second
        self.worker.side_effect = ValueError('stock rejected')
        with self.assertRaises(ValueError): self.execute()
        self.assertEqual([c['status'] for c in self.recover()['drafts'][0]['commands']], ['committed','pending'])
        self.worker.side_effect = None; self.execute()
        self.assertTrue(self.recover()['drafts'][0]['complete'])

    def test_actor_company_isolation_and_session_fence(self):
        self.prepare(); self.user['id'] = 13
        self.assertEqual(self.recover()['drafts'], [])
        with self.assertRaises(HTTPException): self.execute()
        self.model.expectedActorUserId = 13
        with self.assertRaises(HTTPException): self.execute()
        with self.assertRaises(HTTPException): self.cancel()
        self.user['id'] = 12; self.model.expectedActorUserId = 12
        self.company = 3; self.model.toLocation = 'Project 3'
        self.assertEqual(self.recover()['drafts'], [])
        with self.assertRaises(HTTPException): self.execute()
        with self.assertRaises(HTTPException): self.cancel()
        self.worker.assert_not_called()

    def test_bounds_and_no_name_fallback(self):
        for user in ({}, {'name':'12'}, {'id':13}):
            with self.assertRaises(HTTPException): drafts.actor_identity(user,12)
        with self.assertRaises(HTTPException): self.prepare([self.model]*101)
        self.model.notes = 'x'*262145
        with self.assertRaises(HTTPException): self.prepare()
        self.assertEqual(self.store.state['drafts'],{})

    def test_cross_company_project_and_all_company_rejected(self):
        self.model.toLocation = 'Project 3'
        with self.assertRaises(HTTPException): self.prepare()
        kwargs=self.kwargs(); kwargs.update(x_company_id=None,x_company_mode='all_companies')
        with self.assertRaises(HTTPException): self.namespace[ROUTES[1]](expectedActorUserId=12,**kwargs)

    def test_cancel_keeps_committed_tombstones_unexecuted_and_allows_new(self):
        second=self.command(); second.draftId=self.model.draftId
        self.prepare([self.model,second]); self.execute()
        result=self.cancel()
        self.assertEqual([c['status'] for c in result['commands']],['committed','cancelled'])
        self.assertTrue(result['complete'])
        self.assertEqual(self.prepare([self.model,second]),result)
        self.assertEqual(self.cancel(),result)
        self.assertEqual(self.recover()['drafts'],[])
        self.model=second
        with self.assertRaises(HTTPException): self.execute()
        self.worker.assert_called_once()
        self.model=self.command(); self.prepare()
        self.assertEqual(len(self.store.state['drafts']),2)

    def test_restricted_permission_recovery_cancel_never_exposes_payload(self):
        self.prepare(); self.access.side_effect=HTTPException(403,'revoked')
        result=self.recover()['drafts'][0]
        self.assertEqual(set(result),{'draftId','companyId','actorUserId','complete','restricted','commands'})
        self.assertTrue(result['restricted']); self.assertEqual(result['commands'],[])
        self.assertNotIn('Cable',str(result))
        for action in (self.prepare,self.execute):
            with self.assertRaises(HTTPException): action()
        self.assertTrue(self.cancel()['complete'])
        self.assertEqual(self.recover()['drafts'],[])

    def test_project_deleted_recovery_is_metadata_only(self):
        self.prepare(); self.store.projects_available=False
        result=self.recover()['drafts'][0]
        self.assertTrue(result['restricted']); self.assertEqual(result['commands'],[])
        self.assertTrue(self.cancel()['complete'])

    def test_company_membership_revocation_denies_metadata_and_cancel(self):
        self.prepare()
        self.namespace['_resolve_work_company_context'].side_effect=HTTPException(403,'membership revoked')
        for action in (self.recover,self.cancel):
            with self.assertRaises(HTTPException): action()
        self.assertFalse(next(iter(self.store.state['bindings'].values()))['cancelled'])

    def test_unexpected_database_error_never_becomes_cancellation(self):
        self.prepare(); self.access.side_effect=RuntimeError('database error')
        for action in (self.recover,self.cancel):
            with self.assertRaises(RuntimeError): action()
        self.assertFalse(next(iter(self.store.state['bindings'].values()))['cancelled'])

    def test_feature_and_package_guards_on_recovery(self):
        self.prepare(); self.selected_role='прораб'
        self.namespace['has_package_access'].return_value=False
        self.assertTrue(self.recover()['drafts'][0]['restricted'])
        self.selected_role='директор'; self.namespace['os'].getenv=lambda *a:'1'
        self.assertTrue(self.recover()['drafts'][0]['restricted'])
        with self.assertRaises(HTTPException): self.execute()

    def test_default_director_selected_master_denied_all_four(self):
        self.prepare(); self.selected_role='мастер'
        for action in (self.prepare,self.recover,self.cancel,self.execute):
            with self.assertRaises(HTTPException) as error: action()
            self.assertEqual(error.exception.status_code,403)
        self.worker.assert_not_called()

    def test_default_worker_selected_director_valid_all_four(self):
        self.user['role']='мастер'; self.selected_projects=['Project 2']; self.selected_packages=['Electrical']
        first=self.prepare(); self.assertEqual(self.recover()['drafts'],[first]); self.execute()
        self.assertEqual(self.cancel()['commands'][0]['status'],'committed')
        actor=self.worker.call_args.args[3]
        self.assertEqual(actor['role'],'директор'); self.assertEqual(actor['id'],12)
        self.assertEqual(actor['assignedProjects'],['Project 2'])
        self.assertEqual(actor['assignedPackages'],['Electrical'])
        self.assertEqual(self.namespace['_create_warehouse_movement_review_task_safely'].call_args.args[3],actor)

    def test_selected_assignment_overlay_replaces_default(self):
        self.user.update(assignedProjects=['Wrong'],assignedPackages=['Wrong'])
        self.selected_role='прораб'; self.selected_projects=['Project 2']; self.selected_packages=['Selected']
        self.model.fromLocation='Project 2'; self.model.toLocation='Основной склад'; self.model.workPackage='Selected'
        self.access.side_effect=lambda actor,location:self.assertIn(location,actor['assignedProjects'])
        self.namespace['has_package_access'].side_effect=lambda actor,package:package in actor['assignedPackages']
        self.prepare(); self.execute()
        self.assertEqual(self.worker.call_args.args[3]['role'],'прораб')
        self.selected_packages=[]
        with self.assertRaises(HTTPException): self.execute()
        self.assertTrue(self.recover()['drafts'][0]['restricted'])

    def test_missing_selected_role_never_uses_default_role(self):
        self.selected_role=''
        for action in (self.prepare,self.recover,self.cancel,self.execute):
            with self.assertRaises(HTTPException): action()

    def test_dependencies_and_actor_lock_precede_mutations(self):
        tree=ast.parse((Path(__file__).resolve().parents[2]/'main.py').read_text())
        mutations=dict(zip(ROUTES,('drafts.prepare(', 'drafts.reconcile(', 'drafts.cancel_pending(', 'drafts.verify_prepared(')))
        for name in ROUTES:
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            defaults=[ast.unparse(d) for d in node.args.defaults]
            self.assertIn('Depends(get_current_user)',defaults)
            self.assertFalse(any('require_roles' in d for d in defaults))
            source=ast.unparse(node)
            self.assertLess(source.index('drafts.lock_actor('),source.index(mutations[name]))

    def test_duplicate_command_ids_and_nonfinite_quantity_fail_closed(self):
        duplicate=copy.deepcopy(self.model)
        with self.assertRaises(HTTPException): self.prepare([self.model,duplicate])
        self.model.quantity=float('nan')
        with self.assertRaises(HTTPException): self.prepare()
        self.assertEqual(self.store.state['drafts'],{})
        self.worker.assert_not_called()

    def test_unknown_or_corrupted_ledger_outcome_is_never_cancelled(self):
        self.prepare(); self.execute()
        self.store.state['ledger'][(2,self.model.commandId)]['payload_hash']='mismatch'
        for action in (self.recover,self.cancel):
            with self.assertRaises(HTTPException) as error: action()
            self.assertEqual(error.exception.status_code,409)
        self.assertFalse(next(iter(self.store.state['bindings'].values()))['cancelled'])
        self.assertFalse(next(iter(self.store.state['drafts'].values()))['complete'])

    def test_missing_draft_identity_and_wrong_nested_actor_rejected(self):
        self.prepare()
        self.model.draftId=None
        with self.assertRaises(HTTPException): self.execute()
        self.worker.assert_not_called()
        self.model=self.command(); self.model.expectedActorUserId=13
        with self.assertRaises(HTTPException) as error: self.prepare()
        self.assertEqual(error.exception.status_code,403)
