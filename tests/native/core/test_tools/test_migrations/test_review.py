import pytest
from mock import patch
from transifex.native.tools.migrations.models import (Confidence,
                                                      FileMigration,
                                                      StringMigration)
from transifex.native.tools.migrations.review import (
    REVIEW_ACCEPT, FileReviewPolicy, LowConfidenceFileReviewPolicy,
    LowConfidenceStringReviewPolicy, ReviewPolicy, StringReviewPolicy,
    add_line_prefix)


def test_base_class_policy_accepts_all():
    policy = ReviewPolicy()
    assert policy.review_file(_file()) == REVIEW_ACCEPT
    assert policy.review_string(_string(), 1, 1) == REVIEW_ACCEPT


@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_string')
@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_file')
def test_file_review_policy_prompts_for_file(mock_file_prompt,
                                             mock_string_prompt):
    # This policy prompts for any files
    policy = FileReviewPolicy()
    file_migration = _file()
    policy.review_file(file_migration)
    mock_file_prompt.assert_called_once_with(file_migration)

    # This policy does not prompt for strings
    policy.review_string(_string(Confidence.HIGH),
                         string_cnt=1, strings_total=5)
    policy.review_string(_string(Confidence.LOW),
                         string_cnt=1, strings_total=5)
    assert mock_string_prompt.call_count == 0


@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_string')
@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_file')
def test_low_file_review_policy_prompts_for_file_with_low_conf_strings(
    mock_file_prompt, mock_string_prompt
):
    # This policy prompts for files that include a string with low confidence
    policy = LowConfidenceFileReviewPolicy()
    file_migration = _file()
    file_migration.add_string(_string(Confidence.HIGH))
    file_migration.add_string(_string(Confidence.HIGH))
    file_migration.add_string(_string(Confidence.LOW))
    policy.review_file(file_migration)
    mock_file_prompt.assert_called_once_with(file_migration)

    # This policy does not prompt for strings
    policy.review_string(_string(Confidence.HIGH),
                         string_cnt=1, strings_total=5)
    policy.review_string(_string(Confidence.LOW),
                         string_cnt=1, strings_total=5)
    assert mock_string_prompt.call_count == 0


@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_file')
def test_low_file_review_policy_not_prompts_for_file_with_high_conf_strings(
    mock_file_prompt
):
    # This policy prompts for files that include a string with low confidence
    policy = LowConfidenceFileReviewPolicy()
    file_migration = _file()
    file_migration.add_string(_string(Confidence.HIGH))
    file_migration.add_string(_string(Confidence.HIGH))
    file_migration.add_string(_string(Confidence.HIGH))
    policy.review_file(file_migration)
    assert mock_file_prompt.call_count == 0


@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_string')
@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_file')
def test_string_review_policy_prompts_for_string(mock_file_prompt,
                                                 mock_string_prompt):
    # This policy prompts for all strings
    policy = StringReviewPolicy()
    string_migration1 = _string(Confidence.HIGH)
    policy.review_string(string_migration1, 5, 10)
    string_migration2 = _string(Confidence.LOW)
    policy.review_string(string_migration2, 15, 20)
    assert mock_string_prompt.call_args_list[0][0] == (
        string_migration1, 5, 10)
    assert mock_string_prompt.call_args_list[1][0] == (
        string_migration2, 15, 20)

    # This policy does not prompt for file reviews
    policy.review_file(_file())
    assert mock_file_prompt.call_count == 0


@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_string')
@patch('transifex.native.tools.migrations.review.ReviewPolicy'
       '.prompt_for_file')
def test_low_string_review_policy_prompts_for_low_conf_string_only(
    mock_file_prompt, mock_string_prompt
):
    # This policy prompts for strings that have a low confidence
    policy = LowConfidenceStringReviewPolicy()
    string_migration = _string(Confidence.HIGH)
    policy.review_string(string_migration, 5, 10)
    string_migration = _string(Confidence.LOW)
    policy.review_string(string_migration, 10, 10)
    mock_string_prompt.assert_called_once_with(string_migration, 10, 10)

    # This policy does not prompt for file reviews
    policy.review_file(_file())
    assert mock_file_prompt.call_count == 0


def test_set_comment_format_exception_for_wrong_format():
    # An exception should be raised if the given format does not include {}
    policy = ReviewPolicy()
    with pytest.raises(ValueError):
        policy.set_comment_format('{')


def test_add_line_prefix():
    text = "This\nis\ngood"
    assert add_line_prefix(text, '+ ') == "+ This\n+ is\n+ good"
    assert add_line_prefix(text, '+ ', 99) == \
        "99 + This\n100 + is\n101 + good"
    assert add_line_prefix('', '+ ') == ''
    assert add_line_prefix(None, '+ ') is None


def _string(confidence=Confidence.HIGH):
    """Return a sample StringMigration object for testing."""
    return StringMigration('original', 'new', confidence)


def _file():
    """Return a sample FileMigration object for testing."""
    return FileMigration('filename', 'content')
