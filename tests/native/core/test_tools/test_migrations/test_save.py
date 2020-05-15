from mock import mock_open, patch
from transifex.native.tools.migrations.models import (FileMigration,
                                                      StringMigration)
from transifex.native.tools.migrations.save import (BackupSavePolicy,
                                                    NewFileSavePolicy,
                                                    NoopSavePolicy,
                                                    ReplaceSavePolicy,
                                                    SavePolicy)


def _file_migration():
    migration = FileMigration('path/filename.html', 'the content')
    migration.add_string(StringMigration(
        'the content', 'the migrated content'))
    return migration


def test_noop_policy_does_not_open_file():
    policy = NoopSavePolicy()
    m = mock_open()
    with patch("io.open", m, create=True):
        saved, error_type = policy.save_file(_file_migration())
        assert saved is False
        assert error_type is None
    assert m.call_count == 0


def test_new_file_policy_writes_to_new_file():
    policy = NewFileSavePolicy()
    m = mock_open()
    with patch("io.open", m, create=True):
        saved, error_type = policy.save_file(_file_migration())
        assert saved is True
        assert error_type is None

    m.assert_called_once_with('path/filename__native.html', 'w',
                              encoding="utf-8")
    m().write.assert_called_once_with('the migrated content')


def test_backup_policy_writes_to_original_file_and_takes_backup():
    policy = BackupSavePolicy()
    m = mock_open()
    with patch("io.open", m, create=True):
        saved, error_type = policy.save_file(_file_migration())
        assert saved is True
        assert error_type is None

    assert m.call_args_list[0][0] == ('path/filename.html.bak', 'w')
    assert m.call_args_list[1][0] == ('path/filename.html', 'w')
    handler = m()
    assert handler.write.call_args_list[0][0] == (u'the content',)
    assert handler.write.call_args_list[1][0] == (u'the migrated content',)


def test_in_place_policy_writes_to_original_file():
    policy = ReplaceSavePolicy()
    m = mock_open()
    with patch("io.open", m, create=True):
        saved, error_type = policy.save_file(_file_migration())
        assert saved is True
        assert error_type is None

    m.assert_called_once_with('path/filename.html', 'w', encoding="utf-8")
    m().write.assert_called_once_with('the migrated content')


@patch('transifex.native.tools.migrations.save.Color.echo')
def test_safe_save_handles_io_error(mock_echo):
    def raise_error():
        raise IOError()

    policy = SavePolicy()
    m = mock_open()
    with patch("io.open", m, create=True):
        saved, error_type = policy._safe_save(
            'doesnt-matter', raise_error, 'Dummy')
        assert saved is False
        assert error_type is IOError

    assert 'IOError while saving to dummy' in mock_echo.call_args[0][0]


@patch('transifex.native.tools.migrations.save.Color.echo')
def test_safe_save_handles_any_error(mock_echo):
    def raise_error():
        raise ValueError()

    policy = SavePolicy()
    m = mock_open()
    with patch("io.open", m, create=True):
        saved, error_type = policy._safe_save(
            'doesnt-matter', raise_error, 'Dummy')
        assert saved is False
        assert error_type is ValueError

    assert 'Error while saving to dummy' in mock_echo.call_args[0][0]
