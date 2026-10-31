"""Disposable real-API fixture for check-participant-supplier-browser.py only."""
import argparse
from contextlib import nullcontext
import importlib
import json
from pathlib import Path
import secrets
import signal
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve(build, artifacts, scenario='merge'):
    from backend.features.supplier_access.test_postgres_chain_support import connection_settings
    import os
    connection_settings(os.environ)  # Explicit opt-in, socket and dedicated DB name.
    if scenario == 'managers':
        from backend.features.supplier_team.test_manager_revocation_postgres import ManagerRevocationPostgresTests as Suite
        method = 'test_two_managers_reassignment_revokes_cached_draft_and_reenable_keeps_assignments_empty'
    else:
        from backend.features.participant_support.test_history_merge_postgres import SupplierHistoryMergePostgresTests as Suite
        method = 'test_complete_missing_inn_then_merge_uses_the_full_history_plan'
    import uvicorn
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    Suite.setUpClass()  # Also verifies the database is empty and blocks outbound TCP.
    fixture = Suite(method)
    try:
        migration = importlib.import_module('migrations.versions.0005_platform_client_contracts')
        connection = fixture.main.get_db()
        try:
            with connection, connection.cursor() as cursor:
                with patch.object(migration, 'op', SimpleNamespace(execute=cursor.execute)):
                    migration.upgrade()
        finally:
            connection.close()
        password = secrets.token_urlsafe(24)
        state = {'password': password, 'users': {}, 'scenarios': {}}
        if scenario == 'managers':
            state['managerScenario'] = fixture.seed_managers()
            state['supplierId'] = fixture.fixture['supplierId']
        actors = ('supplier', 'manager', 'manager_b') if scenario == 'managers' else ('admin', 'supplier', 'stranger')
        for actor in actors:
            user = fixture.fixture['users'][actor]
            secret = fixture.main._generate_totp_secret()
            two_factor = actor in ('admin', 'stranger')
            fixture.sql('''UPDATE users SET password=%s,two_factor_secret=%s,
                two_factor_enabled=%s,two_factor_required=%s WHERE id=%s''',
                (fixture.main.hash_password(password), secret, two_factor, two_factor, user['id']))
            email = 'admin@local.invalid' if actor == 'admin' else user['email']
            state['users'][actor] = {'email': email, 'secret': secret}
        originals = {}
        if scenario == 'managers':
            offer_ids = [state['managerScenario'][key] for key in ('offerA', 'offerB')]
            originals['offers'] = fixture.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=ANY(%s) ORDER BY id', (offer_ids,))
            originals['events'] = fixture.sql('SELECT to_jsonb(e) FROM supplier_offer_events e WHERE offer_id=ANY(%s) ORDER BY id', (offer_ids,))
        for size in (() if scenario == 'managers' else ('mobile', 'desktop')):
            source, target, invoice = fixture.seed()
            fixture.sql('UPDATE suppliers SET name=%s WHERE id=%s', ('BROWSER '+size+' receipt', source))
            fixture.sql("UPDATE suppliers SET name=%s,inn='' WHERE id=%s", ('BROWSER '+size+' cabinet', target))
            state['scenarios'][size] = dict(source=source, target=target, invoice=invoice)
            originals[size] = fixture.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,))
        state_path = artifacts / 'state.json'
        with state_path.open('x', encoding='utf-8') as stream:
            state_path.chmod(0o600)
            json.dump(state, stream)
        app = fixture.main.app
        app.mount('/static', StaticFiles(directory=str(build / 'static')), name='browser_check_static')
        if (build / 'site-assets').is_dir():
            app.mount('/site-assets', StaticFiles(directory=str(build / 'site-assets')), name='browser_check_site_assets')

        @app.get('/app', response_class=HTMLResponse)
        def frontend():
            return (build / 'index.html').read_text(encoding='utf-8')

        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8001,
            loop='asyncio', lifespan='off', access_log=False, log_level='warning'))
        # Return through finally on SIGTERM; do not re-raise Uvicorn's captured signal.
        server.capture_signals = nullcontext
        def stop(_signum, _frame):
            server.should_exit = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            server.run()
        finally:
            results = {}
            if scenario == 'managers':
                row = state['managerScenario']
                offer_ids = [row['offerA'], row['offerB']]
                results['managers'] = {
                    'offersPreserved': originals['offers'] == fixture.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=ANY(%s) ORDER BY id', (offer_ids,)),
                    'eventsPreserved': originals['events'] == fixture.sql('SELECT to_jsonb(e) FROM supplier_offer_events e WHERE offer_id=ANY(%s) ORDER BY id', (offer_ids,)),
                    'managerAClosed': fixture.api('manager', 'GET', '/supplier-offers') == [],
                    'managerBClosedAfterReenable': fixture.api('manager_b', 'GET', '/supplier-offers') == [],
                    'memberReenabled': fixture.sql('SELECT active FROM supplier_team_members WHERE id=%s', (row['memberB'],)) == [(True,)],
                    'assignmentsCleared': fixture.sql('SELECT count(*) FROM supplier_customer_assignments WHERE supplier_id=%s AND member_id IS NOT NULL', (state['supplierId'],)) == [(0,)],
                    'ownerKeepsAccess': set(offer_ids) <= {r['id'] for r in fixture.api('supplier', 'GET', '/supplier-offers')},
                }
            for size, row in state['scenarios'].items():
                source, target, invoice = row['source'], row['target'], row['invoice']
                results[size] = {
                    'invoicePreserved': originals[size] == fixture.sql(
                        'SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,)),
                    'ownerAssigned': fixture.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,))
                        == [(fixture.fixture['users']['supplier']['id'],)],
                    'canonicalCard': fixture.sql("SELECT profile->>'mergedIntoSupplierId' FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s", (source,)) == [(str(target),)],
                    'oneMergeAudit': fixture.sql("SELECT count(*) FROM audit_log WHERE action='supplier_history_merged' AND entity_id=%s", (source,)) == [(1,)],
                    'oneInnAudit': fixture.sql("SELECT count(*) FROM audit_log WHERE action='supplier_missing_inn_completed' AND entity_id=%s", (target,)) == [(1,)],
                }
            (artifacts / 'database-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    finally:
        Suite.doClassCleanups()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--scenario', choices=('merge', 'merge-denials', 'managers'), default='merge')
    args = parser.parse_args()
    serve(args.build.resolve(), args.artifacts.resolve(), args.scenario)
