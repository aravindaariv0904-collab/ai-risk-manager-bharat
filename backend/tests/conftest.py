import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    """
    Test configuration.
    The risk engine trains a small Isolation Forest on first use;
    tests that hit it need matplotlib-free operation only.
    """
    os.environ.setdefault("DEMO_MODE", "true")