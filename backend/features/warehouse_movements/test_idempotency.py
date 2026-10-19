"""Execute the real extracted route without importing startup or live DB config."""
import copy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import psycopg2
from fastapi import HTTPException

from backend.features.material_traceability.test_movement_transaction import load_route
from backend.features.warehouse_movements.idempotency import command_identity
from backend.features.company_context.service import effective_company_actors


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.row = None

    def execute(self, sql, args=()):
        if sql.startswith('SELECT payload_hash,response'):
            self.row = self.conn.pending.get(tuple(args))
        elif sql.startswith('INSERT INTO warehouse_movement_commands'):
            company, command, digest, response = args
            self.conn.pending[(company, command)] = {'payload_hash': digest, 'response': response.adapted}
        else:
            self.row = {'present': False}

    def fetchone(self):
        return copy.deepcopy(self.row)

    def close(self):
        pass


class Connection:
    def __init__(self, ledger):
        self.ledger = ledger
        self.pending = copy.deepcopy(ledger)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **kwargs):
        return Cursor(self)

    def commit(self):
        self.ledger.update(self.pending)
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class MovementRetryTests(TestCase):
    def setUp(self):
        # Dedicated test_drafts runs the real prepare/ownership path.
        patcher = patch("backend.features.warehouse_movements.drafts.verify_prepared")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ledger = {}
        self.connections = []
        self.company = 2
        self.worker = Mock(return_value={'id': 7, 'estimateControl': {'needsReview': True}})
        self.review = Mock(return_value={'taskId': 8, 'created': True})
        self.access = Mock()
        self.context = Mock(side_effect=lambda *a, **k: {'mode':'company', 'companyId':self.company, 'companyIds':[self.company], 'effectiveRole':'директор', 'assignedProjects':[], 'assignedPackages':[]})
        self.ai = Mock()
        def get_db():
            conn = Connection(self.ledger)
            self.connections.append(conn)
            return conn
        self.namespace = dict(get_db=get_db, psycopg2=psycopg2,
            _movement_draft_company=lambda cur, user, cid, mode: (self.company,effective_company_actors(user,self.context(cur,user))[0]),
            _authorize_movement_draft_command=lambda cur, model, company, user:self.access(user,model.toLocation),
            os=SimpleNamespace(getenv=lambda *args: None), HTTPException=HTTPException,
            PACKAGE_LIMIT_ROLES=(), MAIN_WAREHOUSE_WRITE_ROLES=('директор',),
            require_project_or_warehouse_access=self.access, _project_company_id=lambda *_: self.company,
            _positive_int_or_none=lambda value: value, _resolve_work_company_context=self.context,
            _apply_warehouse_movement=self.worker,
            _create_warehouse_movement_review_task_safely=self.review, _run_project_ai_control_safely=self.ai)
        self.route = load_route(self.namespace)
        self.model = SimpleNamespace(expectedActorUserId=12, commandId=str(uuid4()), materialName='Кабель', fromLocation='Основной склад',
            toLocation='Школа', workPackage='', quantity=5, unit='м', date='2026-10-18', createdBy='Директор',
            notes='', invoiceId=3, invoiceLineIndex=0)

    def call(self):
        return self.route(self.model, _current_user={'id':12, 'role': 'директор'})

    def test_lost_response_replays_exact_result_without_stock_or_side_effects(self):
        first = self.call()  # commit succeeds, client never sees this response
        self.assertEqual(self.call(), first)
        self.worker.assert_called_once()
        self.review.assert_called_once()
        self.ai.assert_called_once()
        self.assertEqual(len(self.ledger), 1)

    def test_changed_payload_rejected(self):
        self.call()
        for field, changed in [('quantity', 6), ('invoiceId', 4), ('invoiceLineIndex', 1), ('notes', 'changed')]:
            with self.subTest(field=field):
                previous = getattr(self.model, field)
                setattr(self.model, field, changed)
                with self.assertRaises(HTTPException) as error:
                    self.call()
                self.assertEqual(error.exception.status_code, 409)
                setattr(self.model, field, previous)
        self.worker.assert_called_once()

    def test_company_scoped_key_never_returns_other_company_response(self):
        self.call()
        self.company = 3
        self.worker.return_value = {'id': 99}
        self.assertEqual(self.call(), {'id': 99})
        self.assertEqual(len(self.ledger), 2)

    def test_permissions_rechecked_on_replay(self):
        self.call()
        self.access.side_effect = HTTPException(403, 'revoked')
        with self.assertRaises(HTTPException) as error:
            self.call()
        self.assertEqual(error.exception.status_code, 403)
        self.worker.assert_called_once()

    def test_company_access_rechecked_on_replay(self):
        self.call()
        self.context.side_effect = HTTPException(403, 'membership revoked')
        with self.assertRaises(HTTPException) as error:
            self.call()
        self.assertEqual(error.exception.status_code, 403)
        self.worker.assert_called_once()

    def test_partial_batch_failure_only_failed_line_reexecutes(self):
        self.call()
        first_command = self.model.commandId
        self.model.commandId = str(uuid4())
        self.worker.side_effect = ValueError('stock rejected')
        with self.assertRaises(ValueError):
            self.call()
        self.assertEqual(len(self.ledger), 1)
        self.assertEqual(self.connections[-1].rollbacks, 1)
        self.worker.side_effect = None
        self.worker.return_value = {'id': 9}
        self.assertEqual(self.call(), {'id': 9})
        self.model.commandId = first_command
        self.assertEqual(self.call()['id'], 7)
        self.assertEqual(self.worker.call_count, 3)

    def test_invalid_or_missing_key_and_nonfinite_quantity_fail_closed(self):
        for value in ('', None, 'garbage'):
            self.model.commandId = value
            with self.assertRaises(HTTPException) as error:
                self.call()
            self.assertEqual(error.exception.status_code, 422)
        self.model.commandId = str(uuid4())
        self.model.quantity = float('nan')
        with self.assertRaises(HTTPException):
            command_identity(self.model)
        self.worker.assert_not_called()

    def test_feature_flag_still_blocks_even_replay(self):
        self.call()
        self.namespace['os'] = SimpleNamespace(getenv=lambda *a: '1')
        with self.assertRaises(HTTPException) as error:
            self.call()
        self.assertEqual(error.exception.status_code, 409)
        self.worker.assert_called_once()
