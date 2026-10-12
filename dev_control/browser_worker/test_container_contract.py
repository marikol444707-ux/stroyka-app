from pathlib import Path
import unittest


class BrowserWorkerContainerContractTest(unittest.TestCase):
    def test_worker_container_is_isolated_and_app_platform_ready(self):
        dockerfile = Path("dev_control/Dockerfile").read_text(encoding="utf-8")
        requirements = Path("dev_control/browser_worker/requirements.txt").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.12", dockerfile)
        self.assertIn("USER root", dockerfile)
        self.assertIn("useradd --create-home --uid 10001 worker", dockerfile)
        self.assertIn("useradd --create-home --uid 10002 chrome", dockerfile)
        self.assertIn("setpriv --reuid=10002", Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8"))
        self.assertIn("setpriv --reuid=10001", Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8"))
        self.assertIn("EXPOSE 8080", dockerfile)
        self.assertIn("COPY . /app/dev_control", dockerfile)
        self.assertIn("chown -R root:root /app /home/worker", dockerfile)
        self.assertIn("chmod -R go-w /app", dockerfile)
        self.assertIn("find /app/dev_control -type d -exec chmod 755 {} +", dockerfile)
        self.assertIn("find /app/dev_control -type f -name '*.py' -exec chmod 644 {} +", dockerfile)
        self.assertNotIn("chmod -R a+r /app", dockerfile)
        self.assertNotIn("chown -R worker:worker /app", dockerfile)
        self.assertNotIn("COPY backend", dockerfile)
        self.assertIn(
            "1231850a0bf1a0c0341fe408ef1668dbbfdfac46",
            requirements,
        )



    def test_docker_context_allowlists_code_and_excludes_untracked_secrets(self):
        context_rules = Path("dev_control/.dockerignore")
        if not context_rules.exists():
            # Docker intentionally excludes .dockerignore from COPY . .
            # The same test MUST also run on the checked-out host in CI.
            self.skipTest("Docker excludes .dockerignore from image; tested on CI checkout")
        rules = context_rules.read_text(encoding="utf-8").splitlines()
        rules = [line.strip() for line in rules if line.strip() and not line.startswith("#")]
        self.assertEqual(rules[0], "*")
        self.assertIn("browser_worker/*", rules)
        self.assertIn("!browser_worker/service.py", rules)
        self.assertIn("!browser_worker/qa_identity.py", rules)
        self.assertIn("!jev_timeweb.py", rules)
        self.assertNotIn("!browser_worker/*.py", rules)
        self.assertNotIn("!browser_worker/**", rules)
        self.assertNotIn("!**", rules)
        for name in (".env", ".env.local", "qa-token.txt", "id_rsa",
                     "secrets.json", "browser_worker/.env",
                     "browser_worker/evidence/result.json",
                     "browser_worker/qa-session.pem"):
            self.assertNotIn("!" + name, rules)

    def test_runtime_paths_cannot_be_replaced_by_worker_owned_symlinks(self):
        dockerfile = Path("dev_control/Dockerfile").read_text(encoding="utf-8")
        start = Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8")
        self.assertIn("install -d -m 0755 -o root -g root /var/lib/stroyka-jev-qa", dockerfile)
        for path in ("harness", "evidence", "chrome"):
            self.assertIn("/var/lib/stroyka-jev-qa/" + path, dockerfile)
        self.assertIn('if [[ -L "$runtime_root"', start)
        self.assertIn('if [[ -L "$path" ]]', start)
        self.assertIn("Refusing untrusted browser/evidence runtime directory overrides", start)
        self.assertIn("0:0:755", start)

    def test_qa_spki_is_pinned_without_global_certificate_bypass(self):
        script = Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8")
        self.assertIn('QA_CHROME_CERT_SPKI', script)
        self.assertIn('qa_spki="${QA_CHROME_CERT_SPKI#sha256/}"', script)
        self.assertIn('--ignore-certificate-errors-spki-list=$qa_spki', script)
        self.assertIn('QA Chrome SPKI trust is restricted to the dedicated QA gateway', script)
        self.assertIn('Invalid QA Chrome SPKI pin format', script)
        self.assertNotIn('--ignore-certificate-errors ', script)
        self.assertNotIn('chrome_args=(--ignore-certificate-errors "', script)

    def test_qa_ca_nss_trust_is_scoped_and_fail_closed(self):
        dockerfile = Path("dev_control/Dockerfile").read_text(encoding="utf-8")
        script = Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8")
        self.assertIn("libnss3-tools", dockerfile)
        self.assertIn('readonly qa_ca_path="/etc/stroyka-qa/caddy-root.crt"', script)
        self.assertIn('QA_CHROME_CA_TRUST:-0', script)
        self.assertIn('QA Chrome CA trust requires dedicated QA scope without SPKI override', script)
        self.assertIn('QA root CA must be a root-owned regular file', script)
        self.assertIn('certutil -N', script)
        self.assertIn('certutil -A', script)
        self.assertIn('certutil -L', script)
        self.assertIn('-t "C,," -i "$qa_ca_path"', script)
        self.assertIn('QA_CHROME_NSS_CA_READY', script)
        self.assertNotIn('chrome_args=(--ignore-certificate-errors "', script)

    def test_chrome_env_options_precede_assignments(self):
        # GNU env stops processing -u flags after its first NAME=VALUE operand.
        # The former 'env HOME=/home/chrome -u TOKEN ...' failed to start Chrome.
        script = Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8")
        launch = script.split("setpriv --reuid=10002", 1)[1].split("google-chrome-stable", 1)[0]
        self.assertIn("  env \\\n  -u TIMEWEB_AI_API_KEY", launch)
        for secret_name in (
            "TIMEWEB_AI_API_KEY", "DEV_CONTROL_API_TOKEN",
            "QA_SESSION_COOKIE_VALUE", "JEV_WATCH_GITHUB_TOKEN",
            "JEV_WATCHER_TOKEN", "TYPESAFE_API_KEY", "TEXT_MODEL_API_KEY",
        ):
            self.assertLess(launch.index("-u " + secret_name), launch.index("HOME=/home/chrome"))

    def test_worker_has_hard_timeout_and_authenticated_evidence_contract(self):
        service = Path("dev_control/browser_worker/service.py").read_text(encoding="utf-8")
        network_guard = Path("dev_control/browser_worker/network_guard.py").read_text(encoding="utf-8")
        start_script = Path("dev_control/browser_worker/start.sh").read_text(encoding="utf-8")

        self.assertIn("result_queue.get(timeout=remaining)", service)
        self.assertIn("deadline = time.monotonic() + request.max_seconds", service)
        self.assertIn("process.terminate()", service)
        self.assertGreaterEqual(service.count("_cleanup_qa_browser_contexts()"), 3)
        self.assertIn('/jobs/{job_id}/evidence/{filename}', service)
        self.assertIn("_authorize(authorization)", service)
        self.assertIn("Fetch.enable", network_guard)
        self.assertIn("Fetch.failRequest", network_guard)
        self.assertIn("PreAuthBodyLimitMiddleware", service)
        self.assertIn("_MAX_JOB_BODY_BYTES = 32 * 1024", service)
        self.assertIn("status_code=413", service)
        self.assertIn("QA_ALLOWED_ORIGIN", network_guard)
        self.assertIn('host.endswith(".stroyka26.pro")', network_guard)
        self.assertIn('"147.45.237.127"', network_guard)
        self.assertIn("shutil.rmtree(evidence_dir, ignore_errors=True)", service)
        self.assertIn("_executor.shutdown(wait=False, cancel_futures=True)", service)

        crash_branch = service.split("elif report is None:", 1)[1].split("else:", 1)[0]
        self.assertIn("_cleanup_qa_browser_contexts()", crash_branch)

        self.assertIn("Target.setAutoAttach", network_guard)
        self.assertIn("waitForDebuggerOnStart=True", network_guard)
        self.assertIn("Runtime.runIfWaitingForDebugger", network_guard)
        self.assertIn("Target.createBrowserContext", network_guard)
        self.assertIn("Target.disposeBrowserContext", network_guard)
        self.assertIn('"Browser.setDownloadBehavior"', network_guard)
        self.assertIn("browserContextId=self.browser_context_id", network_guard)
        self.assertIn("Page.addScriptToEvaluateOnNewDocument", network_guard)
        self.assertIn("WebSocket", network_guard)
        self.assertIn("WebTransport", network_guard)
        self.assertIn("RTCPeerConnection", network_guard)
        self.assertIn('"Network.setCookie"', network_guard)
        self.assertIn("session_id=browser_session_id", network_guard)
        self.assertNotIn('"Storage.setCookies"', network_guard)
        self.assertIn("bootstrap_session_cookie(base_url, self.session, cdp)", network_guard)
        self.assertIn("QA_SESSION_COOKIE_VALUE", network_guard)
        self.assertIn("QA navigation did not commit within 15s", network_guard)
        self.assertIn("self._cleanup_allocations()", network_guard)
        self.assertIn('"type": "worker"', network_guard)
        self.assertIn('"type": "shared_worker"', network_guard)
        self.assertIn('"type": "service_worker"', network_guard)
        self.assertIn('"type": "iframe"', network_guard)
        self.assertIn("globalThis", network_guard)
        self.assertIn("Runtime.evaluate", network_guard)
        self.assertIn("DEDICATED_CDP_URL = \"http://127.0.0.1:9222\"", network_guard)
        self.assertIn("Refusing external BU_CDP_URL", start_script)
        self.assertIn('export BU_CDP_URL="${expected_cdp_url}"', start_script)
        for secret_name in (
            "TIMEWEB_AI_API_KEY",
            "DEV_CONTROL_API_TOKEN",
            "QA_SESSION_COOKIE_VALUE",
            "TYPESAFE_API_KEY",
            "TEXT_MODEL_API_KEY",
        ):
            self.assertIn("-u " + secret_name, start_script)

if __name__ == "__main__":
    unittest.main()
