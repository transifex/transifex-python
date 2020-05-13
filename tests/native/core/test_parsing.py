# -*- coding: utf-8 -*-

import re

from transifex.native.parsing import Extractor, SourceString

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
            SourceString(u'Le canapé', u'désign',
                         param1='1', param2=2, param3=True,
                         _occurrences=['myfile.py:6']),
            SourceString(
                u'Les données', u'opération', _comment='comment', _tags=['t1', 't2'],
                _charlimit=33, _occurrences=['myfile.py:7']
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
            SourceString(u'Le canapé', u'désign',
                         param1='1', param2=2, param3=True,
                         _occurrences=['myfile.py:8'], ),
            SourceString(
                u'Les données', u'opération', _comment='comment', _tags=['t1', 't2'],
                _charlimit=33, _occurrences=['myfile.py:9'],
            ),
        ]
