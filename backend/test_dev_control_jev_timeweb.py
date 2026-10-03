"""CI bridge for the isolated Dev Control Jev adapter tests.

The main CI discovers tests only under backend/, so importing the TestCase here
ensures the adapter regression tests are executed without changing workflow
permissions or storing any external API secret in CI.
"""

from dev_control.test_jev_timeweb import JevTimewebClientTest

__all__ = ["JevTimewebClientTest"]
