# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
from django.core.management import call_command
from tests.native.django.test_tools.test_migrations.test_templatetags import (
    DJANGO_TEMPLATE, TRANSIFEX_TEMPLATE)
from transifex.common.console import Color
from transifex.native.django.management.commands.transifex import Command
from transifex.native.django.management.common import TranslatableFile
from transifex.native.tools.migrations.review import (FileReviewPolicy,
                                                      NoopReviewPolicy,
                                                      StringReviewPolicy)
from transifex.native.tools.migrations.save import (BackupSavePolicy,
                                                    NewFileSavePolicy,
                                                    NoopSavePolicy,
                                                    ReplaceSavePolicy)

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

PYTHON_SAMPLE = """
from something import gettext
from django.utils.translation import ugettext as _, ugettext_lazy as _lazy
from django.utils.translation import something as smth, ungettext as _pl, ungettext_lazy as _lazypl
from django.utils.translation import pgettext as _ctx
from django.utils.translation import pgettext_lazy as _lazyctx
from django.utils.translation import ugettext as ug, to_locale, get_language_info as lang_info
from django.utils import translation as _trans
import django
import django.utils
import django.something_else
from django import utils as _utils


# A comment
aa = 34
bb = aa + round(33.3)

_('This is "nice"')
_('This is %s') % something
_('This is %s and %s %s %s') % (3, something, "lit'eral", r"lit\'eral")
_('This is %s') % (3 * 15)
_('Hello! %(name)s %(last_name)s %(age)s %(gender)s') % {'name': 'You', 'last_name': user.last_name, 'age': 33, 'gender': gender}
_('This is %s and %s') % ("\\'", r"\\'")
_('This is %(foo)s and %(bar)s') % {'foo': foo, 'bar': 'bar'}
_('This is %(foo)s and %(bar)s') % dict(foo=foo, bar='bar')
_('This is %s') % obj.something('else', 'is', 'happening')
_lazy('Hello! %(name)s %(last_name)s %(age)s %(gender)s') % {'name': 'You', 'last_name': user.last_name, 'age': 33, 'gender': gender}

plural = _pl('One fish', plural='Many fishes', number=number)
plural = _lazypl('One fish', plural='Many fishes', number=number)
django.utils.translation.ugettext('Hello!')

_utils.translation.ugettext(**dict(message='Hello!'))
zero = _trans.ugettext('This is the zero')
first = _(message='This is the first')
plural = _pl('This is', 'These are', 3)
plural = _pl('One fish', plural='Many fishes', number=number)
plural = _pl(number=number, plural='Many "fishes', singular="One 'fish")
plural = _pl(number=number, plural='Many fishes', singular="One 'fish")


withcontext1 = _ctx('Some context', 'This is a message')
withcontext2 = _ctx(**dict(context='Some context', message='This is a message'))
withcontext3 = _lazyctx('Some context', 'This is a message')

do_something(
    django.utils.translation.ngettext('Hello!', 'Hellos!', 2),
    _('Aha! %(name)s %(last_name)s') % {'name': 'You', 'last_name': user.last_name},
    some_var,
    another=_('Yay %s %s') % [something, 33]
)

# Add an import statement after function calls
from django import utils as _utils
from django.utils.translation import ngettext as _ng


class MyClass(object):

    def myfunc(self, text1, text2):
        send_message(_('Foo %(t1)s - %(t2)s') % {'t1': text1, 't2': text2})
"""

PYTHON_SAMPLE_MIGRATED = """
from something import gettext
from transifex.native.django import lazyt, t
from django.utils.translation import something as smth
from django.utils.translation import to_locale, get_language_info as lang_info
from django.utils import translation as _trans
import django
import django.utils
import django.something_else
from django import utils as _utils


# A comment
aa = 34
bb = aa + round(33.3)

t('This is "nice"')
t('This is {variable_1}', variable_1=something)
t('This is {variable_1} and {variable_2} {variable_3} {variable_4}', variable_1=3, variable_2=something, variable_3="lit'eral", variable_4="lit'eral")
t('This is {variable_1}', variable_1=(3 * 15))
t('Hello! {name} {last_name} {age} {gender}', name='You', last_name=user.last_name, age=33, gender=gender)
t('This is {variable_1} and {variable_2}', variable_1="'", variable_2='\\'')
t('This is {foo} and {bar}', foo=foo, bar='bar')
t('This is {foo} and {bar}', __txnative_fixme="dict(foo=foo, bar='bar')")
t('This is {variable_1}', variable_1=obj.something('else', 'is', 'happening'))
lazyt('Hello! {name} {last_name} {age} {gender}', name='You', last_name=user.last_name, age=33, gender=gender)

plural = t('{cnt, one {One fish} other {Many fishes}}', cnt=number)
plural = lazyt('{cnt, one {One fish} other {Many fishes}}', cnt=number)
t('Hello!')

t('Hello!')
zero = t('This is the zero')
first = t('This is the first')
plural = t('{cnt, one {This is} other {These are}}', cnt=3)
plural = t('{cnt, one {One fish} other {Many fishes}}', cnt=number)
plural = t("{cnt, one {One 'fish} other {Many \\"fishes}}", cnt=number)
plural = t("{cnt, one {One 'fish} other {Many fishes}}", cnt=number)


withcontext1 = t('This is a message', _context='Some context')
withcontext2 = t('This is a message', _context='Some context')
withcontext3 = lazyt('This is a message', _context='Some context')

do_something(
    t('{cnt, one {Hello!} other {Hellos!}}', cnt=2),
    t('Aha! {name} {last_name}', name='You', last_name=user.last_name),
    some_var,
    another=t('Yay {variable_1} {variable_2}', variable_1=something, variable_2=33)
)

# Add an import statement after function calls
from django import utils as _utils


class MyClass(object):

    def myfunc(self, text1, text2):
        send_message(t('Foo {t1} - {t2}', t1=text1, t2=text2))
"""


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


@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_READ_FILE)
@mock.patch('os.getcwd')
def test_dry_run_save_none_review0(mock_cur_dir, mock_read,
                                   mock_prompt_to_start1):
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


@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_dry_run_save_none_review(mock_find_files, mock_read,
                                  mock_prompt_to_start1):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
        HTML_SAMPLE_2,  # 1.txt,
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='none',
                 review_policy='none')
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      NoopSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      NoopReviewPolicy)


@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_SAVE_FILE, return_value=(True, None))
@mock.patch(PATH_PROMPT_STRING)
@mock.patch(PATH_PROMPT_FILE)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_new_file_save_file_review(mock_find_files, mock_read,
                                   mock_prompt_file, mock_prompt_string,
                                   mock_save_file,
                                   mock_prompt_to_start1):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.py', 'locdir1'),
    ]
    mock_read.side_effect = [
        HTML_SAMPLE_1,  # 1.html
        HTML_SAMPLE_2,  # 1.txt
        PYTHON_SAMPLE,  # 1.py
    ]
    command = Command()
    call_command(command, 'migrate', save_policy='new', review_policy='file')
    assert isinstance(command.subcommands['migrate'].executor.save_policy,
                      NewFileSavePolicy)
    assert isinstance(command.subcommands['migrate'].executor.review_policy,
                      FileReviewPolicy)

    # The first FileMigration instance that reached the review object
    # should compile to the proper Native syntax (1.html)
    file_migration1 = mock_prompt_file.call_args_list[0][0][0]
    assert file_migration1.compile() == HTML_COMPILED_1

    # The same for 1.py
    file_migration2 = mock_prompt_file.call_args_list[1][0][0]
    assert file_migration2.compile() == PYTHON_SAMPLE_MIGRATED

    # No string review should have taken place
    assert mock_prompt_string.call_count == 0

    # The path and content that reached the save object
    # should have the correct values
    assert mock_save_file.call_args_list[0][0][0] == 'dir1/dir2/1__native.html'
    migration_compile = mock_save_file.call_args_list[0][0][1]
    assert migration_compile() == HTML_COMPILED_1

    assert mock_save_file.call_args_list[1][0][0] == 'dir4/dir5/1__native.py'
    migration_compile = mock_save_file.call_args_list[1][0][1]
    assert migration_compile() == PYTHON_SAMPLE_MIGRATED


@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_SAVE_FILE, return_value=(True, None))
@mock.patch(PATH_PROMPT_STRING)
@mock.patch(PATH_PROMPT_FILE)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_backup_save_string_review(mock_find_files, mock_read,
                                   mock_prompt_file, mock_prompt_string,
                                   mock_save_file,
                                   mock_prompt_to_start1):
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
    assert mock_prompt_string.call_count == 13  # 11 migrated strings

    # The path and content that reached the save object
    # should have the correct values, one for the backup and one for
    # the new content
    assert mock_save_file.call_args_list[0][0][0] == 'dir1/dir2/1.html.bak'
    original_content_getter = mock_save_file.call_args_list[0][0][1]
    assert original_content_getter() == HTML_SAMPLE_1

    assert mock_save_file.call_args_list[1][0][0] == 'dir1/dir2/1.html'
    migration_compile = mock_save_file.call_args_list[1][0][1]
    assert migration_compile() == HTML_COMPILED_1


@mock.patch(PATH_PROMPT_START1)
@mock.patch(PATH_SAVE_FILE, return_value=(True, None))
@mock.patch(PATH_PROMPT_STRING)
@mock.patch(PATH_PROMPT_FILE)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_replace_save_string_review(mock_find_files, mock_read,
                                    mock_prompt_file, mock_prompt_string,
                                    mock_save_file,
                                    mock_prompt_to_start1):
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
    assert mock_prompt_string.call_count == 13

    # The path and content that reached the save object
    # should have the correct values
    assert mock_save_file.call_args[0][0] == 'dir1/dir2/1.html'
    migration_compile = mock_save_file.call_args[0][1]
    assert migration_compile() == HTML_COMPILED_1


@mock.patch('transifex.common.console.Color.echo')
def test_text_migration_template_code(mock_echo):
    """Test the mode that migrates directly given text instead of files
    (Django HTML templates)."""
    command = Command()
    call_command(command, 'migrate', text=DJANGO_TEMPLATE)
    expected = Color.format(
        '\n[high]Transifex Native syntax:[end]\n[green]{}[end]'.format(
            TRANSIFEX_TEMPLATE
        )
    )
    actual = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == actual

    # Make sure it's idempotent
    mock_echo.reset_mock()
    call_command(command, 'migrate', text=TRANSIFEX_TEMPLATE)
    actual = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == actual


@mock.patch('transifex.common.console.Color.echo')
def test_text_migration_python_code(mock_echo):
    """Test the mode that migrates directly given text instead of files
    (Python/gettext code)."""
    command = Command()
    call_command(command, 'migrate', text=PYTHON_SAMPLE)
    expected = Color.format(
        '\n[high]Transifex Native syntax:[end]\n[green]{}[end]'.format(
            PYTHON_SAMPLE_MIGRATED
        )
    )
    native = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == native

    # Make sure it's idempotent
    mock_echo.reset_mock()
    call_command(command, 'migrate', text=PYTHON_SAMPLE_MIGRATED)
    actual = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == actual
