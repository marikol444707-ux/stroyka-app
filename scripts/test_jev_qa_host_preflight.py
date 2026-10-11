"""Offline, no-Docker/no-SSH tests for the read-only QA host inventory."""
import json
import unittest
from unittest.mock import patch

from scripts.jev_qa_host_preflight import inspect_host, _inspect, _host_port_owners


def _container(port, *, state="running", user="10001", privileged=False, security=None):
    return {
        "state": state,
        "user": user,
        "ports": {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]} if port else {},
        "privileged": privileged,
        "security": security or [],
        "pid_mode": "",
    }


def _fake_command(items, *, timer="inactive"):
    fields = {
        "{{json .State.Status}}": "state",
        "{{json .Config.User}}": "user",
        "{{json .HostConfig.PortBindings}}": "ports",
        "{{json .HostConfig.Privileged}}": "privileged",
        "{{json .HostConfig.SecurityOpt}}": "security",
        "{{json .HostConfig.PidMode}}": "pid_mode",
    }
    calls = []

    def command(args):
        calls.append(args)
        if args == ["docker", "ps", "-a", "--format", "{{.Names}}"]:
            return "\n".join(items)
        if args[:3] == ["docker", "inspect", "--format"]:
            fmt, name = args[3], args[4]
            if name not in items:
                return None
            return json.dumps(items[name][fields[fmt]])
        if args == ["systemctl", "is-active", "stroyka-jev-watch.timer"]:
            return timer
        if args == ["systemctl", "is-enabled", "stroyka-jev-watch.timer"]:
            return "disabled"
        raise AssertionError("Unexpected command or mutation attempt: " + repr(args))

    return command, calls


class HostPreflightTest(unittest.TestCase):
    def test_known_qa_worker_on_18088_only_requires_further_review(self):
        containers = {
            "stroyka-jev-qa": _container(18088),
            "stroyka-qa-backend": _container(8001),
            "stroyka-qa-gateway": _container(8443),
        }
        command, calls = _fake_command(containers)
        with patch("scripts.jev_qa_host_preflight._read_setting", return_value="unknown"):
            result = inspect_host(command)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["watch_port"]["owners"], ["stroyka-jev-qa"])
        self.assertEqual(result["verified"], "inventory_only")
        self.assertFalse(result["changes_made"])
        self.assertTrue(all(c[0] in {"docker", "systemctl"} for c in calls))
        self.assertTrue(all("Env" not in repr(c) and "Mounts" not in repr(c) for c in calls))
        self.assertNotIn("FAKE_SECRET_VALUE", json.dumps(result))

    def test_dialog_test_occupying_watch_port_is_blocking(self):
        containers = {
            "stroyka-jev-qa": _container(18082),
            "stroyka-jev-dialog-test": _container(18088),
            "stroyka-qa-backend": _container(8001),
            "stroyka-qa-gateway": _container(8443),
        }
        command, _ = _fake_command(containers, timer="active")
        with patch("scripts.jev_qa_host_preflight._read_setting", return_value="unknown"):
            result = inspect_host(command)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("MULTIPLE_ACTIVE_JEV_WORKERS", result["blockers"])
        self.assertIn("WATCH_PORT_18088_NOT_OWNED_BY_EXPECTED_WORKER", result["blockers"])
        self.assertIn("ACTIVE_TIMER_WITH_WRONG_WATCHER_ENDPOINT", result["blockers"])

    def test_stopped_dialog_container_does_not_own_host_port(self):
        items = {
            "stroyka-jev-qa": _container(18088),
            "stroyka-jev-dialog-test": _container(18088, state="exited"),
            "stroyka-qa-backend": _container(8001),
            "stroyka-qa-gateway": _container(8443),
        }
        command, _ = _fake_command(items)
        with patch("scripts.jev_qa_host_preflight._read_setting", return_value="unknown"):
            result = inspect_host(command)
        self.assertEqual(result["watch_port"]["owners"], ["stroyka-jev-qa"])
        self.assertEqual(result["status"], "review_required")

    def test_exposed_jev_api_port_and_unconfined_seccomp_are_blocked(self):
        worker = _container(18088, security=["seccomp=unconfined"])
        worker["ports"]["8080/tcp"][0]["HostIp"] = "0.0.0.0"
        containers = {
            "stroyka-jev-qa": worker,
            "stroyka-qa-backend": _container(8001),
            "stroyka-qa-gateway": _container(8443),
        }
        command, _ = _fake_command(containers)
        with patch("scripts.jev_qa_host_preflight._read_setting", return_value="unknown"):
            result = inspect_host(command)
        self.assertIn("JEV_WORKER_NOT_LOOPBACK_ONLY:stroyka-jev-qa", result["blockers"])
        self.assertIn("UNCONFINED_CONTAINER_SECURITY:stroyka-jev-qa", result["blockers"])
        self.assertEqual(result["status"], "blocked")

    def test_docker_permission_missing_reports_blocker_without_details(self):
        result = inspect_host(lambda _: None)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"], ["DOCKER_INSPECTION_UNAVAILABLE"])
        self.assertFalse("secrets" in json.dumps(result).lower())

    def test_privileged_worker_is_blocked(self):
        containers = {
            "stroyka-jev-qa": _container(18088, privileged=True),
            "stroyka-qa-backend": _container(8001),
            "stroyka-qa-gateway": _container(8443),
        }
        command, _ = _fake_command(containers)
        with patch("scripts.jev_qa_host_preflight._read_setting", return_value="unknown"):
            result = inspect_host(command)
        self.assertIn("PRIVILEGED_CONTAINER:stroyka-jev-qa", result["blockers"])


if __name__ == "__main__":
    unittest.main()
