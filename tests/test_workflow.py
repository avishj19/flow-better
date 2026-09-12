"""Legacy workflow / live connectors are out of the ground-ops main path."""
import pytest


@pytest.mark.skip(reason='Ground-ops desk v3 removed disrupt/experiment workflow from the main path')
def test_workflow_placeholder():
    assert False


@pytest.mark.skip(reason='FR24/live observation flow is no longer part of the ground-ops desk UI')
def test_live_placeholder():
    assert False
