# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
from django.core.management import call_command
from tests.native.django.test_tools.test_migrations.test_templatetags import (
    DJANGO_TEMPLATE, TRANSIFEX_TEMPLATE)
from transifex.native.django.management.commands.transifex import Command
from transifex.native.django.management.common import TranslatableFile
from transifex.native.tools.migrations.review import (FileReviewPolicy,
                                                      NoopReviewPolicy,
                                                      StringReviewPolicy)
from transifex.native.tools.migrations.save import (BackupSavePolicy,
                                                    NewFileSavePolicy,
                                                    NoopSavePolicy,
                                                    ReplaceSavePolicy)

PYTHON_TEMPLATE = u"""
# -*- coding: utf-8 -*-

{_import}

{call1}(u'{string1}', u'désign1,désign2', param1='1', param2=2, param3=True)
{call2}(
    u'{string2}', u'opération', _comment='comment', _tags='t1,t2', _charlimit=33,
)
"""

HTML_SAMPLE_1 = DJANGO_TEMPLATE
HTML_SAMPLE_2 = """
{% load i18n %}
{% load t from transifex %}

{% t "Hello!" %}

{% t "May" _context="month name" %}

{% t counter='something'|length name=name %}
{counter, plural, one {
There is only one {name} object.
} other {
There are {counter} {name} objects.
}}
{% endt %}

<a href="{{ url }}">Text</a>
"""
HTML_COMPILED_1 = TRANSIFEX_TEMPLATE

PATH_FIND_FILES = ('transifex.native.django.management.utils.base.'
                   'CommandMixin._find_files')
PATH_READ_FILE = ('transifex.native.django.management.utils.base.CommandMixin.'
                  '_read_file')
PATH_PROMPT_FILE = 'transifex.native.tools.migrations.review.ReviewPolicy' \
                   '.prompt_for_file'
PATH_PROMPT_STRING = 'transifex.native.tools.migrations.review' \
                     '.ReviewPolicy.prompt_for_string'
PATH_SAVE_FILE = 'transifex.native.tools.migrations.save.SavePolicy' \
                 '._safe_save'
PATH_PROMPT_START1 = 'transifex.native.tools.migrations.execution' \
                     '.MigrationExecutor._prompt_to_start'
PATH_ECHO = 'transifex.native.tools.migrations.execution' \
            '.Color.echo'


@mock.patch(PATH_ECHO)
@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_READ_FILE)
@mock.patch('os.getcwd')
def test_dry_run_save_none_review0(mock_cur_dir, mock_read,
                                   mock_prompt_to_start1, mock_echo):
    mock_cur_dir.return_value = 'dir1/dir2'
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='none',
                 review_policy='none', files=['1.html'])
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      NoopSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      NoopReviewPolicy)


@mock.patch(PATH_ECHO)
@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_dry_run_save_none_review(mock_find_files, mock_read,
                                  mock_prompt_to_start1, mock_echo):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
        HTML_SAMPLE_2,  # 1.txt
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='none',
                 review_policy='none')
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      NoopSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      NoopReviewPolicy)


@mock.patch(PATH_ECHO)
@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_SAVE_FILE, return_value=(True, None))
@mock.patch(PATH_PROMPT_STRING)
@mock.patch(PATH_PROMPT_FILE)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_new_file_save_file_review(mock_find_files, mock_read,
                                   mock_prompt_file, mock_prompt_string,
                                   mock_save_file,
                                   mock_prompt_to_start1, mock_echo):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
        HTML_SAMPLE_2,  # 1.txt
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='new', review_policy='file')
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      NewFileSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      FileReviewPolicy)

    # The FileMigration instance that reached the review object
    # should compile to the proper Native syntax
    file_migration = mock_prompt_file.call_args[0][0]
    assert file_migration.compile() == HTML_COMPILED_1

    # No string review should have taken place
    assert mock_prompt_string.call_count == 0

    # The path and content that reached the save object
    # should have the correct values
    assert mock_save_file.call_args[0][0] == 'dir1/dir2/1__native.html'
    migration_compile = mock_save_file.call_args[0][1]
    assert migration_compile() == HTML_COMPILED_1


@mock.patch(PATH_ECHO)
@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_SAVE_FILE, return_value=(True, None))
@mock.patch(PATH_PROMPT_STRING)
@mock.patch(PATH_PROMPT_FILE)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_backup_save_string_review(mock_find_files, mock_read,
                                   mock_prompt_file, mock_prompt_string,
                                   mock_save_file,
                                   mock_prompt_to_start1, mock_echo):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
        HTML_SAMPLE_2,  # 1.txt
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='backup',
                 review_policy='string')
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      BackupSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      StringReviewPolicy)

    assert mock_prompt_file.call_count == 0
    assert mock_prompt_string.call_count == 11  # 11 migrated strings

    # The path and content that reached the save object
    # should have the correct values, one for the backup and one for
    # the new content
    assert mock_save_file.call_args_list[0][0][0] == 'dir1/dir2/1.html.bak'
    original_content_getter = mock_save_file.call_args_list[0][0][1]
    assert original_content_getter() == HTML_SAMPLE_1

    assert mock_save_file.call_args_list[1][0][0] == 'dir1/dir2/1.html'
    migration_compile = mock_save_file.call_args_list[1][0][1]
    assert migration_compile() == HTML_COMPILED_1


@mock.patch(PATH_ECHO)
@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_SAVE_FILE, return_value=(True, None))
@mock.patch(PATH_PROMPT_STRING)
@mock.patch(PATH_PROMPT_FILE)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_replace_save_string_review(mock_find_files, mock_read,
                                    mock_prompt_file, mock_prompt_string,
                                    mock_save_file,
                                    mock_prompt_to_start1, mock_echo):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
        HTML_SAMPLE_2,  # 1.txt
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='replace',
                 review_policy='string')
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      ReplaceSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      StringReviewPolicy)

    assert mock_prompt_file.call_count == 0
    assert mock_prompt_string.call_count == 11

    # The path and content that reached the save object
    # should have the correct values
    assert mock_save_file.call_args[0][0] == 'dir1/dir2/1.html'
    migration_compile = mock_save_file.call_args[0][1]
    assert migration_compile() == HTML_COMPILED_1
