import pytest


@pytest.fixture
def reset_tx():
    """Reset "global" TxNative instance so that it can be reinitialized."""
    from transifex.native import tx
    tx.initialized = False
