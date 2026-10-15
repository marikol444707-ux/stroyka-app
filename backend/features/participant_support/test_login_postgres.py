"""Real password + TOTP + cookie session against a disposable PostgreSQL."""
import os
import unittest
from unittest.mock import patch

from . import test_capabilities_postgres as capabilities


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupportLoginPostgresTests(unittest.TestCase):
    sql, api, seed, failure, report = (
        capabilities.SupportCapabilitiesPostgresTests.sql,
        capabilities.SupportCapabilitiesPostgresTests.api,
        capabilities.SupportCapabilitiesPostgresTests.seed,
        capabilities.SupportCapabilitiesPostgresTests.failure,
        capabilities.SupportCapabilitiesPostgresTests.report,
    )
    ticket, grant, path = (
        capabilities.SupportCapabilitiesPostgresTests.ticket,
        capabilities.SupportCapabilitiesPostgresTests.grant,
        capabilities.SupportCapabilitiesPostgresTests.path,
    )

    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(patch.stopall)
        capabilities.SupportCapabilitiesPostgresTests.setUpClass.__func__(cls)
        # The network-isolated base fixture intentionally replaces the environment.
        patch.object(cls.main, 'CSRF_LOGOUT_ENFORCED', True).start()

    def test_cookie_login_reload_logout_and_another_support_actor(self):
        from backend.auth import _generate_totp_secret, _totp_code
        password = 'Synthetic-test-only-password'
        actors = {}
        for key in ('support', 'other_support'):
            uid = self.fixture['users'][key]['id']
            email, secret = key + '@local.invalid', _generate_totp_secret()
            self.sql('''UPDATE users SET email=%s,password=%s,two_factor_secret=%s,
                     two_factor_required=TRUE,two_factor_enabled=TRUE WHERE id=%s''',
                     (email, self.main.hash_password(password), secret, uid))
            actors[key] = (email, secret)
        ticket = self.ticket()
        grant = self.grant(ticket)
        cookie_name = self.main.AUTH_SESSION_COOKIE_NAME
        for key in ('support', 'other_support'):
            email, secret = actors[key]
            login = self.client.post('/login', json={'email': email, 'password': password})
            self.assertEqual(login.status_code, 200)
            challenge = login.json()
            self.assertTrue(challenge['twoFactorRequired'])
            self.assertNotIn('authToken', challenge)
            self.assertNotIn(cookie_name, self.client.cookies)
            login = self.client.post('/login/2fa/verify', json={
                'challengeToken': challenge['challengeToken'], 'code': _totp_code(secret)})
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json()['id'], self.fixture['users'][key]['id'])
            self.assertIn('HttpOnly', login.headers['set-cookie'])
            cookie = self.client.cookies[cookie_name]
            for _ in range(2):  # Same cookie survives a page reload; no bearer is added.
                workspace = self.client.get('/participant-support/workspace')
                self.assertEqual(workspace.status_code, 200)
                self.assertIn('no-store', workspace.headers['cache-control'])
                ids = [item['id'] for item in workspace.json()['items']]
                self.assertEqual(ids, [grant['id']] if key == 'support' else [])
            diagnostic = self.client.get('/participant-support/workspace/' + grant['id'] + '/diagnostic')
            self.assertEqual(diagnostic.status_code, 200 if key == 'support' else 404)
            self.assertEqual(self.client.get('/projects').status_code, 403)
            csrf = self.client.get('/csrf-token')
            self.assertEqual(csrf.status_code, 200)
            self.assertEqual(self.client.post('/logout').status_code, 403)
            logout = self.client.post('/logout', headers={'X-CSRF-Token': csrf.json()['csrfToken']})
            self.assertEqual(logout.status_code, 200)
            self.assertNotIn(cookie_name, self.client.cookies)
            rejected = self.client.get('/participant-support/workspace', headers={'Cookie': cookie_name + '=' + cookie})
            self.assertEqual(rejected.status_code, 401)
        self.assertEqual(self.sql('SELECT count(*) FROM user_sessions WHERE revoked_at IS NULL'), [(0,)])
