import pytest
from mock import patch
from transifex.native.tools.migrations.mark import (
    MARK_PROOFREAD_FILE, MARK_PROOFREAD_STRING, MarkLowConfidenceFilesPolicy,
    MarkLowConfidenceStringsPolicy, MarkPolicy, NoopMarkPolicy)
from transifex.native.tools.migrations.models import (Confidence,
                                                      FileMigration,
                                                      StringMigration)


def test_base_class_policy_returns_false():
    policy = NoopMarkPolicy()
    assert policy.mark_file(_file()) is False
    assert policy.mark_string(_string()) is False


@patch('transifex.native.tools.migrations.mark.Color.echo')
@patch('transifex.native.tools.migrations.mark.mark_string')
def test_low_file_policy_marks_low_confidence_files(mock_mark_string,
                                                    mock_echo):
    # Create a file migration with 3 strings,
    # the middle one with low confidence
    policy = MarkLowConfidenceFilesPolicy()
    policy.set_comment_format('# {}')
    file_migration = _file()
    file_migration.add_string(_string(Confidence.HIGH))
    file_migration.add_string(_string(Confidence.LOW))
    file_migration.add_string(_string(Confidence.HIGH))

    # A proofread mark should have been added before the first string,
    # as the files policy adds a mark at the file top
    policy.mark_file(file_migration)
    mock_mark_string.assert_called_once_with(
        file_migration.strings[0],
        '# {}',
        MARK_PROOFREAD_FILE,
    )

    # Calls to mark_string() of a files policy should not mark anything
    mock_mark_string.reset_mock()
    policy.mark_string(file_migration.strings[1])
    assert mock_mark_string.called is False


@patch('transifex.native.tools.migrations.mark.Color.echo')
@patch('transifex.native.tools.migrations.mark.mark_string')
def test_low_string_policy_marks_low_confidence_strings(mock_mark_string,
                                                        mock_echo):
    # Create a file migration with 3 strings,
    # two of which have low confidence
    policy = MarkLowConfidenceStringsPolicy()
    policy.set_comment_format('<!-- {} -->')
    file_migration = _file()
    file_migration.add_string(_string(Confidence.HIGH))
    file_migration.add_string(_string(Confidence.LOW))
    file_migration.add_string(_string(Confidence.LOW))

    policy.mark_file(file_migration)
    assert mock_mark_string.called is False

    for string_migration in file_migration.strings:
        policy.mark_string(string_migration)

    assert mock_mark_string.call_args_list[0][0] == (
        file_migration.strings[1],
        '<!-- {} -->',
        MARK_PROOFREAD_STRING,
    )
    assert mock_mark_string.call_args_list[1][0] == (
        file_migration.strings[2],
        '<!-- {} -->',
        MARK_PROOFREAD_STRING,
    )


def test_set_comment_format_exception_for_wrong_format():
    # An exception should be raised if the given format does not include {}
    policy = MarkPolicy()
    with pytest.raises(ValueError):
        policy.set_comment_format('{')


def _string(confidence=Confidence.HIGH):
    """Return a sample StringMigration object for testing."""
    return StringMigration('original', 'new', confidence)


def _file():
    """Return a sample FileMigration object for testing."""
    return FileMigration('filename', 'content')
