# -*- coding: utf-8 -*-
import mock
import transifex.native.consts as consts
from django.core.management import call_command
from transifex.native.django.management.commands.transifex import Command
from transifex.native.django.management.common import TranslatableFile
from transifex.native.parsing import SourceString

PYTHON_TEMPLATE = u"""
# -*- coding: utf-8 -*-

{_import}

{call1}(u'{string1}', u'désign1,désign2', param1='1', param2=2, param3=True)
{call2}(
    u'{string2}', u'opération', _comment='comment', _tags='t1,t2', _charlimit=33,
)
"""

HTML_TEMPLATE = u"""
{% load transifex %}

{content}
"""

PATH_FIND_FILES = ('transifex.native.django.management.utils.base.'
                   'CommandMixin._find_files')
PATH_READ_FILE = ('transifex.native.django.management.utils.base.CommandMixin.'
                  '_read_file')
PATH_EXTRACT_STRINGS = ('transifex.native.django.management.utils.push.Push.'
                        '_extract_strings')
PATH_PUSH_STRINGS = ('transifex.native.django.management.utils.push.tx.'
                     'push_source_strings')
PATH_PUSH_STRINGS2 = ('transifex.native.django.management.utils.push.Push.'
                      'push_strings')

PYTHON_FILES = [
    # 1.py
    PYTHON_TEMPLATE.format(
        _import='import transifex.native',
        call1='native.translate',
        call2='native.translate',
        string1=u'Le canapé',
        string2=u'Les données',
    ),
    # 2.py
    PYTHON_TEMPLATE.format(
        _import='import transifex.native as _n',
        call1='_n.translate',
        call2='_n.translate',
        string1=u'Le canapé 2',
        string2=u'Les données 2',
    ),
    # 3.py
    PYTHON_TEMPLATE.format(
        _import='from transifex.native import translate',
        call1='translate',
        call2='translate',
        string1=u'Le canapé 3',
        string2=u'Les données 3',
    ),
]

SOURCE_STRINGS = [
    # 1.py
    SourceString(u'Le canapé', u'désign1,désign2',
                 _occurrences=['r1/1.py:6'],),
    SourceString(
        u'Les données', u'opération', _comment='comment', _tags='t1,t2',
        _charlimit=33, _occurrences=['r1/1.py:7'],
    ),
    # 2.py
    SourceString(u'Le canapé 2', u'désign1,désign2',
                 _occurrences=['r1/dir2/2.py:6'],),
    SourceString(
        u'Les données 2', u'opération', _comment='comment', _tags='t1,t2',
        _charlimit=33, _occurrences=['r1/dir2/2.py:7'],
    ),
    # 3.py
    SourceString(u'Le canapé 3', u'désign1,désign2',
                 _occurrences=['r1/dir3/3.py:6'],),
    SourceString(
        u'Les données 3', u'opération', _comment='comment', _tags='t1,t2',
        _charlimit=33, _occurrences=['r1/dir3/3.py:7'],
    ),
]


@mock.patch(PATH_FIND_FILES)
@mock.patch(PATH_READ_FILE)
def test_python_parsing_raises_unicode_error(mock_read, mock_find_files):
    o = b'\x00\x00'
    mock_read.side_effect = UnicodeDecodeError(
        'funnycodec', o, 1, 2, 'This is just a fake reason!')
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
    ]

    command = Command()
    call_command(command, 'push')
    # command.string_collection.strings is like: {<key>: <SourceString>}
    found = command.subcommands['push'].string_collection.strings.values()
    assert set(found) == set([])


@mock.patch(PATH_FIND_FILES)
@mock.patch(PATH_EXTRACT_STRINGS)
def test_python_parsing_no_strings(mock_extract, mock_find_files):
    mock_extract.return_value = []
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
        TranslatableFile('dir1/dir2', '2.py', 'locdir1'),
        TranslatableFile('dir1/dir3', '3.py', 'locdir1'),
    ]

    command = Command()
    call_command(command, 'push')
    # command.string_collection.strings is like: {<key>: <SourceString>}
    found = command.subcommands['push'].string_collection.strings.values()
    assert set(found) == set([])


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_python_parsing_push_exception(mock_find_files, mock_read, mock_push_strings):
    mock_push_strings.return_value = 500, "content_to_trigger_exception"
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
        TranslatableFile('dir1/dir2', '2.py', 'locdir1'),
        TranslatableFile('dir1/dir3', '3.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    expected = SOURCE_STRINGS
    run_and_compare(expected)


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_python_parsing_success(mock_find_files, mock_read, mock_push_strings):
    mock_push_strings.return_value = 200, {'doesnt': 'matter'}
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
        TranslatableFile('dir1/dir2', '2.py', 'locdir1'),
        TranslatableFile('dir1/dir3', '3.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    expected = SOURCE_STRINGS
    run_and_compare(expected)


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_append_tags(mock_find_files, mock_read, mock_push_strings):
    """Test the functionality of the --append_tags option.

    The new tags should be added to the existing ones of each string.
    """
    mock_push_strings.return_value = 200, {'doesnt': 'matter'}
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    expected = [
        clone_string(SOURCE_STRINGS[0], new_tags=['extra1', 'extra2']),
        clone_string(SOURCE_STRINGS[1], new_tags=[
                     't1', 't2', 'extra1', 'extra2']),
    ]
    run_and_compare(expected, append_tags=u'extra1,extra2')


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_with_tags_only(mock_find_files, mock_read, mock_push_strings):
    mock_push_strings.return_value = 200, {'doesnt': 'matter'}
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
        TranslatableFile('dir1/dir2', '2.py', 'locdir1'),
        TranslatableFile('dir1/dir3', '3.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    expected = [
        clone_string(SOURCE_STRINGS[1]),
        clone_string(SOURCE_STRINGS[3]),
        clone_string(SOURCE_STRINGS[5]),
    ]
    run_and_compare(expected, with_tags_only='t1,t2')


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_without_tags_only(mock_find_files, mock_read, mock_push_strings):
    mock_push_strings.return_value = 200, {'doesnt': 'matter'}
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
        TranslatableFile('dir1/dir2', '2.py', 'locdir1'),
        TranslatableFile('dir1/dir3', '3.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    expected = [
        clone_string(SOURCE_STRINGS[0]),
        clone_string(SOURCE_STRINGS[2]),
        clone_string(SOURCE_STRINGS[4]),
    ]
    run_and_compare(expected, without_tags_only='t1,t2')


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_all_tags_options(mock_find_files, mock_read, mock_push_strings):
    mock_push_strings.return_value = 200, {'doesnt': 'matter'}
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
        TranslatableFile('dir1/dir2', '2.py', 'locdir1'),
        TranslatableFile('dir1/dir3', '3.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    expected = [
        clone_string(SOURCE_STRINGS[0], new_tags=['extra1', 'extra2']),
        clone_string(SOURCE_STRINGS[2], new_tags=['extra1', 'extra2']),
        clone_string(SOURCE_STRINGS[4], new_tags=['extra1', 'extra2']),
    ]
    run_and_compare(
        expected,
        append_tags='extra1,extra2',
        with_tags_only='extra1',
        without_tags_only='t1,t2',
    )


@mock.patch(PATH_PUSH_STRINGS2)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_template_parsing(mock_find_files, mock_read, mock_push_strings):
    mock_find_files.return_value = [
        TranslatableFile('dir1/dir2', '1.html', 'locdir1'),
        TranslatableFile('dir4/dir5', '1.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        # 1.html
        HTML_TEMPLATE.replace(
            '{content}',
            u'<p>{% t "<b>Strong</b> {a}" a="A" _context="c1,c2" '
            u'_tags="t1,t2" _comment="comment1" _charlimit=22 %}</p>\n'

            u'<p>{% ut "παράδειγμα {b}" b="B" _context="c1,c2" '
            u'_tags="t1,t2" _comment="comment2" _charlimit=33 %}</p>'
        ),
        # 1.txt
        HTML_TEMPLATE.replace(
            '{content}',
            u'{% t _context="c1,c2" _tags="t1,t2" _comment="co1" _charlimit=22 %}\n'
            u'This is a short string\n'
            u'{% endt %}\n'

            u'{% t _context="c1,c2" _tags="t1,t2" _comment="co2" _charlimit=33 %}\n'
            u'This is not a shorter string\n'
            u'{% endt %}'
        ),
    ]

    expected = [
        # 1.html
        SourceString(
            u'<b>Strong</b> {a}', 'c1,c2', _tags='t1,t2', _comment="comment1",
            _charlimit=22, _occurrences=['r1/dir2/1.html:4'],
        ),
        SourceString(
            u'παράδειγμα {b}', 'c1,c2', _tags='t1,t2', _comment="comment2",
            _charlimit=33, _occurrences=['r1/dir2/1.html:5'],
        ),

        # 1.txt
        SourceString(
            u'\nThis is a short string\n', 'c1,c2', _tags='t1,t2',
            _comment="co1", _charlimit=22, _occurrences=['r4/dir5/1.txt:4'],
        ),
        SourceString(
            u'\nThis is not a shorter string\n', 'c1,c2', _tags='t1,t2',
            _comment="co2", _charlimit=33, _occurrences=['r4/dir5/1.txt:7'],
        ),
    ]
    run_and_compare(expected)


@mock.patch(PATH_PUSH_STRINGS2)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_no_detection_for_non_transifex(mock_find_files, mock_read, mock_push_strings):
    """No strings should be detected if a format other than Transifex Native
    is used in Python files and templates.
    """
    mock_find_files.return_value = [
        # 2 files with valid extension but no translatable content
        TranslatableFile('dir4/dir5', 'empty.py', 'locdir1'),
        TranslatableFile('dir4/dir5', 'empty.txt', 'locdir1'),
    ]
    mock_read.side_effect = [
        # empty.py - shouldn't detect any strings as non-transifex
        PYTHON_TEMPLATE.format(
            _import='from django.utils.translation import ugettext_lazy as _',
            call1='_',
            call2='_',
            string1=u'A Django string',
            string2=u'Another Django string',
        ),
        # empty.txt - shouldn't detect any strings as non-transifex
        (
            u'{% load i18n %}\n'
            u'{% trans "A Django string %}\n'
            u'{% blocktrans %}Another Django string{% endblocktrans %}',
        ),
    ]
    command = Command()
    call_command(command, 'push', domain='djangojs')
    # command.string_collection.strings is like: {<key>: <SourceString>}
    found = command.subcommands['push'].string_collection.strings.values()
    assert set(found) == set([])


@mock.patch(PATH_PUSH_STRINGS)
@mock.patch(PATH_READ_FILE)
@mock.patch(PATH_FIND_FILES)
def test_dry_run(mock_find_files, mock_read, mock_push_strings):
    mock_push_strings.return_value = 200, {'doesnt': 'matter'}
    mock_find_files.return_value = [
        TranslatableFile('dir1', '1.py', 'locdir1'),
    ]
    mock_read.side_effect = PYTHON_FILES

    call_command(Command(), 'push', dry_run=1)
    assert not mock_push_strings.called


def clone_string(source_string, new_tags=None):
    """Create a new SourceString instance, identical to the one given,
    by optionally replacing its tags with the ones given.

    :param SourceString source_string: the string to clone
    :param list new_tags: a list of strings to use as the tags
        for the new string
    :rtype: SourceString
    :return: a new SourceString instance
    """
    cloned_string = SourceString(
        source_string.string,
        _context=(
            ','.join(source_string.context)
            if source_string.context else ''
        ),
        **source_string.meta
    )
    if new_tags is not None:
        cloned_string.meta[consts.KEY_TAGS] = new_tags
    return cloned_string


def run_and_compare(expected, **kwargs):
    """Run the command and compare the detected strings with the expected ones.

    Any given kwarg is passed as an argument to the command.
    For example `run_and_compare([...], append_tags=u'extra1,extra2')
    is equivalent to running with `--append_tags=extra1,extra2`.

    :param list expected: a list of SourceString objects
    """
    command = Command()
    call_command(command, 'push', **kwargs)
    # command.string_collection.strings is like: {<key>: <SourceString>}
    found = command.subcommands['push'].string_collection.strings.values()
    assert set(found) == set(expected)
