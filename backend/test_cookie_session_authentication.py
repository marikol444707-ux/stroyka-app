import base64
import hashlib
import hmac
import inspect
import json
import time
import unittest
from unittest import mock

from backend import auth


build_cookie_session_authentication = (
    auth.build_cookie_session_authentication
)


AUTHENTICATION_REQUIRED = "cookie_session_authentication_required"
CSRF_INVALID = "cookie_session_csrf_invalid"
TEST_AUTH_SECRET = "cookie-adapter-test-secret"
SESSION_COOKIE = "A" * 62 + "_-"
OTHER_SESSION_COOKIE = "B" * 64


def _b64url(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _session_hash(session_cookie):
    return hmac.new(
        TEST_AUTH_SECRET.encode("utf-8"),
        session_cookie.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _signed_csrf_token(session_cookie, expires_at):
    payload = {
        "purpose": "csrf",
        "session": _session_hash(session_cookie),
        "nonce": "cookie-adapter-test-nonce",
        "exp": int(expires_at),
    }
    body = _b64url(json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8"))
    signature = hmac.new(
        TEST_AUTH_SECRET.encode("utf-8"),
        ("csrf:" + body).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return body + "." + _b64url(signature)


class _TextSubclass(str):
    pass


class _ReadOnceCookies:
    def __init__(self, value):
        self.value = value
        self.reads = []

    def get(self, key, default=None):
        self.reads.append(key)
        if len(self.reads) > 1:
            raise AssertionError("session cookie was read more than once")
        return self.value if self.value is not None else default


class _Request:
    def __init__(self, session_cookie):
        self._cookies = _ReadOnceCookies(session_cookie)
        self.cookie_property_reads = 0

    @property
    def cookies(self):
        self.cookie_property_reads += 1
        if self.cookie_property_reads > 1:
            raise AssertionError("request.cookies was accessed more than once")
        return self._cookies

    @property
    def cookie_reads(self):
        return list(self._cookies.reads)


class CookieSessionAuthenticationTests(unittest.TestCase):
    def _call(
        self,
        request,
        authorization=None,
        csrf_token=None,
        *,
        require_csrf=True,
    ):
        with mock.patch.object(auth, "AUTH_SECRET", TEST_AUTH_SECRET):
            return build_cookie_session_authentication(
                request,
                authorization,
                csrf_token,
                require_csrf=require_csrf,
            )

    def _assert_fixed_error(self, expected_code, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(type(error).__name__, "CookieSessionAuthenticationError")
        self.assertEqual(getattr(error, "code", None), expected_code)
        self.assertEqual(str(error), expected_code)
        self.assertEqual(error.args, (expected_code,))
        rendered = " ".join((
            str(error),
            repr(error),
            repr(error.args),
            repr(vars(error)),
        ))
        for secret in secrets:
            if secret and secret.strip():
                self.assertNotIn(secret, rendered)
        return error

    def test_public_callable_has_the_exact_db_free_adapter_signature(self):
        parameters = inspect.signature(
            build_cookie_session_authentication
        ).parameters
        self.assertEqual(list(parameters), [
            "request", "authorization", "csrf_token", "require_csrf",
        ])
        self.assertIs(parameters["request"].default, inspect.Parameter.empty)
        self.assertIsNone(parameters["authorization"].default)
        self.assertIsNone(parameters["csrf_token"].default)
        self.assertEqual(
            parameters["require_csrf"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIs(parameters["require_csrf"].default, True)

    def test_get_mode_reads_cookie_once_and_returns_only_exact_hmac_context(self):
        request = _Request(SESSION_COOKIE)

        result = self._call(request, require_csrf=False)

        self.assertIs(type(result), dict)
        self.assertEqual(result, {
            "authenticationKind": "cookie_session",
            "sessionHash": _session_hash(SESSION_COOKIE),
        })
        self.assertEqual(
            set(result), {"authenticationKind", "sessionHash"},
        )
        self.assertNotEqual(
            result["sessionHash"],
            hashlib.sha256(SESSION_COOKIE.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(request.cookie_property_reads, 1)
        self.assertEqual(request.cookie_reads, [auth.AUTH_SESSION_COOKIE_NAME])

    def test_any_authorization_header_is_rejected_before_cookie_access(self):
        for authorization in (
            "", " ", "Bearer compatibility-token", "Basic credential",
            _TextSubclass("Bearer subclass-token"),
        ):
            with self.subTest(authorization=repr(authorization)):
                request = _Request(SESSION_COOKIE)
                self._assert_fixed_error(
                    AUTHENTICATION_REQUIRED,
                    lambda: self._call(
                        request,
                        authorization=authorization,
                        require_csrf=False,
                    ),
                    secrets=(str(authorization), SESSION_COOKIE),
                )
                self.assertEqual(request.cookie_property_reads, 0)
                self.assertEqual(request.cookie_reads, [])

    def test_cookie_must_be_an_exact_builtin_64_character_urlsafe_token(self):
        invalid_cookies = (
            None,
            "",
            "A" * 63,
            "A" * 65,
            "A" * 63 + "=",
            "A" * 63 + "+",
            "A" * 63 + "/",
            "A" * 63 + ".",
            "A" * 63 + " ",
            "A" * 63 + "é",
            b"A" * 64,
            _TextSubclass("A" * 64),
        )
        for cookie in invalid_cookies:
            with self.subTest(cookie=repr(cookie)):
                request = _Request(cookie)
                self._assert_fixed_error(
                    AUTHENTICATION_REQUIRED,
                    lambda: self._call(request, require_csrf=False),
                    secrets=(str(cookie),) if cookie else (),
                )
                self.assertEqual(request.cookie_property_reads, 1)
                self.assertEqual(
                    request.cookie_reads, [auth.AUTH_SESSION_COOKIE_NAME],
                )

    def test_post_mode_accepts_only_current_csrf_bound_to_the_same_cookie(self):
        now = int(time.time())
        valid = _signed_csrf_token(SESSION_COOKIE, now + 3600)
        tampered = valid[:-1] + ("A" if valid[-1] != "A" else "B")
        invalid_tokens = (
            None,
            "",
            "not-a-signed-token",
            tampered,
            _signed_csrf_token(SESSION_COOKIE, now - 3600),
            _signed_csrf_token(OTHER_SESSION_COOKIE, now + 3600),
        )

        for csrf_token in invalid_tokens:
            with self.subTest(csrf_token=repr(csrf_token)):
                request = _Request(SESSION_COOKIE)
                self._assert_fixed_error(
                    CSRF_INVALID,
                    lambda: self._call(request, csrf_token=csrf_token),
                    secrets=tuple(filter(None, (
                        SESSION_COOKIE,
                        str(csrf_token) if csrf_token else "",
                    ))),
                )
                self.assertEqual(request.cookie_property_reads, 1)
                self.assertEqual(
                    request.cookie_reads, [auth.AUTH_SESSION_COOKIE_NAME],
                )

        request = _Request(SESSION_COOKIE)
        result = self._call(request, csrf_token=valid)
        self.assertEqual(result, {
            "authenticationKind": "cookie_session",
            "sessionHash": _session_hash(SESSION_COOKIE),
        })
        self.assertEqual(request.cookie_property_reads, 1)
        self.assertEqual(request.cookie_reads, [auth.AUTH_SESSION_COOKIE_NAME])

    def test_adapter_never_opens_a_database_or_emits_logs(self):
        csrf_token = _signed_csrf_token(
            SESSION_COOKIE,
            int(time.time()) + 3600,
        )
        with mock.patch.object(
            auth, "get_db", create=True,
        ) as get_db, mock.patch.object(
            auth, "log_audit", create=True,
        ) as log_audit, mock.patch.object(
            auth, "logger", create=True,
        ) as logger, mock.patch(
            "logging.getLogger",
        ) as get_logger, mock.patch(
            "logging.Logger._log",
        ) as log_record, mock.patch(
            "builtins.print",
        ) as print_output:
            result = self._call(
                _Request(SESSION_COOKIE),
                csrf_token=csrf_token,
            )
            self._assert_fixed_error(
                AUTHENTICATION_REQUIRED,
                lambda: self._call(
                    _Request(SESSION_COOKIE),
                    authorization="Bearer must-not-be-logged",
                    require_csrf=False,
                ),
                secrets=(SESSION_COOKIE, "Bearer must-not-be-logged"),
            )

        self.assertEqual(result["sessionHash"], _session_hash(SESSION_COOKIE))
        get_db.assert_not_called()
        log_audit.assert_not_called()
        self.assertEqual(logger.mock_calls, [])
        get_logger.assert_not_called()
        log_record.assert_not_called()
        print_output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
