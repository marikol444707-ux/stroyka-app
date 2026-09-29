"""Opt-in alias readers with the deployed receipt and exact journal-owner chain.

Fresh isolated PostgreSQL only. Whole migrations 0023/0024; real authorization.
"""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from backend.features.quality_journals import test_owner_stock_postgres as support


class OwnedAliasRuntimePostgresTests(support.OwnerStockPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0024_company_material_aliases.py'
        spec = importlib.util.spec_from_file_location('runtime_alias_migration', path)
        migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType('alembic')
        alembic.op = None
        with patch.dict(sys.modules, {'alembic': alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                with patch.object(migration, 'op', SimpleNamespace(execute=cur.execute)):
                    migration.upgrade()
        finally:
            conn.close()
        flag = patch.dict(os.environ, {'COMPANY_MATERIAL_ALIASES_ENABLED': '1', 'OWNED_INVOICE_QUALITY_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def seed_alias(self, company, alias, canonical, project=None):
        from backend.features.material_aliases.scoped import require_alias_actor, save_alias
        from psycopg2.extras import RealDictCursor
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                actor = self.f['users']['director' if company == 2 else 'stranger']
                access = require_alias_actor(cur, actor, company_id=company,
                    allowed_roles=('директор',), write=True, full_project_roles=('директор',),
                    platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
                    client_account_roles=self.main.CLIENT_ACCOUNT_ROLES)
                return save_alias(cur, access, alias_name=alias, canonical_name=canonical,
                                  canonical_unit='шт', project_id=project)
        finally:
            conn.close()

    def test_alias_receipt_preserves_original_and_journal_owner(self):
        import json
        brand = 'SKU-' + self.f['materialName']
        own = self.seed_alias(2, brand, self.f['materialName'])
        self.seed_alias(3, brand, 'Foreign canonical')
        self.sql("INSERT INTO material_aliases(alias_name,canonical_name,project_name,active) VALUES(%s,'Legacy poison','',TRUE)", (brand,))
        payload = self.receipt_payload()
        payload.update(location=self.f['project'], project=self.f['project'], warehouseTarget='object',
                       inventoryOnly=False, supplierId=self.f['supplierId'], supplierName='Test supplier')
        payload['items'][0].update(name=brand, materialName=brand)
        receipt = self.api('director', 'POST', '/warehouse-invoices', payload)
        raw = self.sql('SELECT items FROM warehouse_invoices WHERE id=%s', (receipt['id'],))[0][0]
        item = (json.loads(raw) if isinstance(raw, str) else raw)[0]
        self.assertEqual(item['name'], self.f['materialName'])
        self.assertEqual(item['invoiceOriginalName'], brand)
        self.assertEqual(item['materialAlias']['companyId'], 2)
        self.assertEqual(item['materialAlias']['id'], own['id'])
        self.assertEqual(self.sql('SELECT company_id,project_id,material_name,quantity FROM material_inspection_journal WHERE invoice_id=%s', (receipt['id'],)),
                         [(2, self.f['projectId'], self.f['materialName'], 2)])
        self.assertEqual(self.sql('SELECT company_id,name,quantity FROM materials WHERE project=%s', (self.f['project'],)),
                         [(2, self.f['materialName'], 2)])

    def test_same_project_name_different_companies_and_project_precedence(self):
        brand = 'SKU-' + self.f['materialName']
        foreign_project = self.sql("INSERT INTO projects(name,company_id) VALUES(%s,3) RETURNING id", (self.f['project'],))[0][0]
        common = self.seed_alias(2, brand, 'Common canonical')
        own = self.seed_alias(2, brand, self.f['materialName'], self.f['projectId'])
        foreign = self.seed_alias(3, brand, 'Foreign canonical', foreign_project)
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                for company, project, expected in [(2, self.f['project'], own), (3, self.f['project'], foreign), (2, '', common)]:
                    result = self.main._resolve_material_alias(cur, project, brand, company_id=company)
                    self.assertEqual(result['id'], expected['id'])
                    self.assertEqual(result['companyId'], company)
                with self.assertRaises(HTTPException):
                    self.main._resolve_material_alias(cur, self.f['project'], brand, company_id=2, project_id=foreign_project)
        finally:
            conn.close()

    def test_legacy_only_mapping_is_not_used(self):
        brand = 'SKU-' + self.f['materialName']
        self.sql("INSERT INTO material_aliases(alias_name,canonical_name,project_name,active) VALUES(%s,'Legacy poison','',TRUE)", (brand,))
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                self.assertIsNone(self.main._resolve_material_alias(cur, self.f['project'], brand, company_id=2))
        finally:
            conn.close()

    def test_document_transaction_keeps_one_alias_version_until_commit(self):
        from concurrent.futures import ThreadPoolExecutor
        import time
        old = self.seed_alias(2, 'Document brand', 'Original canonical')
        reader = self.main.get_db()
        reader.autocommit = False
        try:
            with reader.cursor() as cur:
                first = self.main._resolve_material_alias(cur, '', 'Document brand', company_id=2)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    writer = pool.submit(self.seed_alias, 2, 'Document brand', 'Updated canonical')
                    try:
                        deadline = time.monotonic() + 3
                        waiting = []
                        while time.monotonic() < deadline:
                            waiting = self.sql("""SELECT pid FROM pg_stat_activity WHERE datname=current_database()
                                AND wait_event_type='Lock' AND query LIKE %s""", ('SELECT pg_advisory_xact_lock(%',))
                            if waiting:
                                break
                            time.sleep(.02)
                        self.assertTrue(waiting, 'Alias replacement must wait for the document transaction')
                        second = self.main._resolve_material_alias(cur, '', 'Document brand', company_id=2)
                        self.assertEqual((first['id'], second['id']), (old['id'], old['id']))
                    finally:
                        reader.commit()
                    newer = writer.result(timeout=10)
                self.assertEqual(self.main._resolve_material_alias(cur, '', 'Document brand', company_id=2)['id'], newer['id'])
        finally:
            reader.rollback()
            reader.close()

    def test_estimate_control_keeps_explicit_project_when_names_duplicate(self):
        self.sql("INSERT INTO projects(name,company_id) VALUES(%s,2)", (self.f['project'],))
        brand = 'SKU-' + self.f['materialName']
        self.seed_alias(2, brand, self.f['materialName'], self.f['projectId'])
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                items = [dict(materialName=brand, unit='шт', quantity=1, workPackage='Основная')]
                self.main._attach_supply_estimate_control(cur, self.f['project'], items,
                    company_id=2, project_id=self.f['projectId'])
                self.assertIn('estimateControl', items[0])
                with self.assertRaises(HTTPException) as error:
                    self.main._resolve_material_alias(cur, self.f['project'], brand, company_id=2)
                self.assertEqual(error.exception.status_code, 409)
        finally:
            conn.close()
