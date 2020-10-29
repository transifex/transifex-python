# -*- coding: utf-8 -*-

import re
import tempfile

from transifex.native.parsing import Extractor, SourceString, extract

TEMPLATE = u"""
# -*- coding: utf-8 -*-

{_import}

{call1}(u'Le canapé', u'désign', param1='1', param2=2, param3=True)
{call2}(
    u'Les données', u'opération', _comment='comment', _tags='t1,t2', _charlimit=33,
)
"""


class TestExtractor(object):
    """Tests the functionality of the Extractor class."""

    def test_default_import(self):
        src = TEMPLATE.format(
            _import='import transifex.native',
            call1='native.translate',
            call2='native.translate',
        )
        self._assert(src)

    def test_default_import_as(self):
        src = TEMPLATE.format(
            _import='import transifex.native as _u',
            call1='_u.translate',
            call2='_u.translate',
        )
        self._assert(src)

    def test_default_import_from(self):
        src = TEMPLATE.format(
            _import='from transifex.native import translate',
            call1='translate',
            call2='ranslate',
        )
        self._assert(src)

    def test_default_import_from_as(self):
        src = TEMPLATE.format(
            _import='from transifex.native import translate as _t',
            call1='_t',
            call2='_t',
        )
        self._assert(src)

    def test_registered_imports(self):
        # Test all combinations in multi-level imports
        # with a custom registered function
        ex = Extractor()
        ex.register_functions('module1.module2.module3.myfunc')

        src = TEMPLATE.format(
            _import=(
                'from module1.module2 import module3 as m3\n'
                'import module1.module2.module3 as _m3\n'
            ),
            call1='m3.myfunc',
            call2='_m3.myfunc',
        )
        results = ex.extract_strings(src, 'myfile.py')
        assert results == self._strings()

        src = TEMPLATE.format(
            _import=(
                'from module1 import module2 as m2\n'
                'import module1.module2 as _m2\n'
            ),
            call1='m2.module3.myfunc',
            call2='_m2.module3.myfunc',
        )
        results = ex.extract_strings(src, 'myfile.py')
        assert results == self._strings()

        src = TEMPLATE.format(
            _import='import module1 as _m1',
            call1='_m1.module2.module3.myfunc',
            call2='_m1.module2.module3.myfunc',
        )

        # mocking gets a little bit different here shifting occurrences
        expected = [
            SourceString(u'Le canapé', u'désign', occurrences=['myfile.py:6']),
            SourceString(
                u'Les données', u'opération', developer_comment='comment',
                tags=['t1', 't2'], character_limit=33,
                occurrences=['myfile.py:7']
            ),
        ]

        results = ex.extract_strings(src, 'myfile.py')
        assert results == expected

    def test_exceptions_on_import(self):
        src = TEMPLATE.format(
            _import='from native import 33',
            call1='_',
            call2='_',
        )
        ex = Extractor()
        results = ex.extract_strings(src, 'myfile.py')
        assert results == []
        assert ex.errors[0][0] == 'myfile.py'
        assert isinstance(ex.errors[0][1], SyntaxError)

    def test_exceptions_on_function_call(self):
        src = TEMPLATE.format(
            _import='from transifex.native import translate',
            call1='33',  # should produce an error
            call2='_',
        )
        ex = Extractor()
        results = ex.extract_strings(src, 'myfile.py')
        assert results == []
        assert ex.errors[0][0] == 'myfile.py'
        assert isinstance(ex.errors[0][1], AttributeError)
        # Num/Constant discrepancy between python versions
        assert re.search(
            re.escape("Invalid module/function format on line 6 col 0: '") +
            r'Num|Constant' +
            re.escape("' object has no attribute 'attr'"),
            ex.errors[0][1].args[0]
        )

    def _assert(self, src):
        ex = Extractor()
        results = ex.extract_strings(src, 'myfile.py')
        return results == self._strings()

    def _strings(self):
        return [
            SourceString(u'Le canapé', u'désign', occurrences=['myfile.py:8']),
            SourceString(
                u'Les données', u'opération', developer_comment='comment',
                tags=['t1', 't2'], character_limit=33,
                occurrences=['myfile.py:9'],
            ),
        ]


def compare_strings(left, right):
    return (
        left.source_string == right.source_string and
        sorted(left.context or []) == sorted(right.context or []) and
        left.character_limit == right.character_limit and
        left.developer_comment == right.developer_comment and
        sorted(left.occurrences or []) == sorted(right.occurrences or []) and
        sorted(left.tags or []) == sorted(right.tags or [])
    )


def compare_extract(source, strings):
    with tempfile.NamedTemporaryFile('w+', encoding="UTF-8") as f:
        f.write(source)
        f.seek(0)
        actual_strings = extract(f.name)

    for string in strings:
        string.occurrences = ["{}:{}".format(f.name, occurrence)
                              for occurrence in string.occurrences or []]

    assert len(actual_strings) == len(strings)
    assert all((compare_strings(left, right)
                for left, right in zip(sorted(actual_strings),
                                       sorted(strings))))


def test_extract_simple():
    source = '\n'.join(('from transifex.native import t', 't("hello world")'))
    strings = [SourceString('hello world', occurrences="2")]
    compare_extract(source, strings)


def test_extract_metadata():
    source = '\n'.join((
        'from transifex.native import t',
        't("hello world", "fr", "context", _charlimit=3, _tags="a,b")',
    ))
    strings = [SourceString('hello world',
                            occurrences="2",
                            context=["context"],
                            character_limit=3,
                            tags=["a", "b"])]
    compare_extract(source, strings)


def test_strings_with_same_key_extracted_once():
    source = '\n'.join((
        'from transifex.native import t',
        't("hello world", "de", "context", _tags="a,b")',
        't("hello world", "fr", "context", _charlimit=3, _tags=["b", "c"])',
    ))
    strings = [SourceString('hello world',
                            occurrences="2,3",
                            context=["context"],
                            character_limit=3,
                            tags=['a', 'b', 'c'])]
    compare_extract(source, strings)


def test_extract_kwargs():
    source = '\n'.join((
        'from transifex.native import t',
        't(source_string="hello world", _context="context", _tags="tag")',
    ))
    strings = [SourceString('hello world',
                            context=['context'],
                            tags=['tag'],
                            occurrences=["2"])]
    compare_extract(source, strings)


def test_import_without_from():
    source = '\n'.join(('import transifex.native as nt',
                        'nt.t("hello world")'))
    strings = [SourceString('hello world', occurrences="2")]
    compare_extract(source, strings)


def test_other_imports():
    source = '\n'.join((
        'from transifex.native import t, tx',
        'from transifex.native.django import t as django_t, ut as django_ut',
        'from transifex.native.urwid import T',
        't("four")',
        'tx.translate("five", _context="five")',
        'django_t("six", _charlimit=6)',
        'django_ut("seven", _tags=["seven"])',
        'T(source_string="eight", _comment="eight")',
    ))
    strings = [SourceString('four', occurrences="4"),
               SourceString('five', context=['five'], occurrences="5"),
               SourceString('six', character_limit=6, occurrences="6"),
               SourceString('seven', tags="seven", occurrences="7"),
               SourceString('eight',
                            developer_comment="eight",
                            occurrences="8")]
    compare_extract(source, strings)
