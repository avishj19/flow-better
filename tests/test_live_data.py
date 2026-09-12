"""Live FR24/weather connectors are optional and not part of ground-ops v3."""
import pytest


@pytest.mark.skip(reason='Ground-ops desk focuses on synthetic on-ground scenarios; live FR24 not required')
def test_live_data_skipped():
    assert False
