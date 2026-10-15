"""CI bridge for browser-worker offline tests.

The production CI discovers Python tests below backend/. These imports execute
only provider/verifier tests and do not install or start Chrome/Jev.
"""

from dev_control.browser_worker.test_container_contract import BrowserWorkerContainerContractTest
from dev_control.browser_worker.test_provider import ProviderPatchTest
from dev_control.browser_worker.test_run_safety import BrowserWorkerUrlSafetyTest
from dev_control.browser_worker.test_service import BrowserWorkerServiceConfigTest
from dev_control.browser_worker.test_verifier import VerifierTest

__all__ = [
    "BrowserWorkerContainerContractTest",
    "ProviderPatchTest",
    "BrowserWorkerUrlSafetyTest",
    "BrowserWorkerServiceConfigTest",
    "VerifierTest",
]
