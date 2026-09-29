"""Retry only the explicit legacy lock-busy response, keeping the same command."""
import time


def api_after_busy(test, actor, method, path, payload):
    token = test.main.create_auth_token(test.fixture['users'][actor], two_factor_passed=True)
    deadline = time.monotonic() + 3
    while True:
        response = test.client.request(method, path, json=payload,
                                       headers={'Authorization': 'Bearer ' + token})
        if (response.status_code == 409
                and response.json().get('detail') == 'Документы снабжения заняты другой операцией. Повторите запрос.'
                and time.monotonic() < deadline):
            time.sleep(.05)
            continue
        test.assertEqual(response.status_code, 200, response.text)
        return response.json()
