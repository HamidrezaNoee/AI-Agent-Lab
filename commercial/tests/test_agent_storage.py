"""Dedicated database boundary and transactional failure guarantees."""
from unittest.mock import Mock, patch
import pytest
from commercial import agent_storage as storage, agent_install


@pytest.mark.parametrize('config', [
    {'database': 'EnterpriseProcess2', 'username': storage.LOGIN},
    {'database': storage.DATABASE, 'username': 'sa'},
    {'database': storage.DATABASE, 'username': storage.LOGIN, 'server': 'db;UID=sa'},
])
def test_refuse_non_dedicated_connection(config):
    with pytest.raises(storage.AgentStorageUnavailable):
        storage.connect(config)


def test_transaction_failure_rolls_back_and_closes():
    con = Mock()
    with patch.object(storage, 'connect', return_value=con):
        with pytest.raises(ValueError):
            with storage.transaction():
                raise ValueError('draft validation failed')
    con.rollback.assert_called_once()
    con.commit.assert_not_called()
    con.close.assert_called_once()


@pytest.mark.parametrize('permissions,allowed', [
    ((1, 1, 1, 1, 1, 0, 0), True),
    ((1, 0, 1, 1, 1, 0, 0), False),
    ((1, 1, 1, 1, 1, 1, 0), False),
    ((1, 1, 1, 1, 1, 0, 1), False),
    ((1, 1, 1, 1, 1, None, 0), False),
])
def test_account_check_fails_closed(permissions, allowed):
    con = Mock()
    con.cursor.return_value.execute.return_value.fetchone.return_value = permissions
    with patch.object(agent_install, 'connect', return_value=con):
        if allowed:
            assert agent_install.check({})['connected']
        else:
            with pytest.raises(storage.AgentStorageUnavailable):
                agent_install.check({})
    con.close.assert_called_once()
