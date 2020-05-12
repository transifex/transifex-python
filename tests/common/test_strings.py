from __future__ import unicode_literals

from transifex.common.strings import (LazyString, alt_quote,
                                      printf_to_format_style)


def test_printf_to_format_style():
    string, variables = printf_to_format_style('This is %s & %s')
    assert string == 'This is {variable_1} & {variable_2}'
    assert set(variables) == {'variable_1', 'variable_2'}

    string, variables = printf_to_format_style('This is %(foo)s and %(bar)s')
    assert string == 'This is {foo} and {bar}'
    assert set(variables) == {'foo', 'bar'}

    string, variables = printf_to_format_style(
        'This is %s and %(bar)s and %s')
    assert string == 'This is {variable_1} and {bar} and {variable_2}'
    assert set(variables) == {'variable_1', 'bar', 'variable_2'}


def test_alt_quote():
    assert alt_quote('"', r'This is a string') == '"'
    assert alt_quote('"', r'This is a " string') == "'"
    assert alt_quote('"', r'This is a \" string') == '"'

    assert alt_quote("'", r"This is a string") == "'"
    assert alt_quote("'", r"This is a ' string") == '"'
    assert alt_quote("'", r"This is a \' string") == "'"


class TestLazyString(object):
    """Tests the functionality of the LazyString class."""

    def test_laziness(self):
        """Make sure the string produces the proper value when evaluates."""
        mapping = {}
        string = LazyString(lambda x: '{}={}'.format(x, mapping.get(x)), 'foo')
        mapping.update({'foo': 33, 'bar': 44})
        assert '{}'.format(string) == 'foo=33'

    def test_no_memoization(self):
        """Make sure the string produces a value every time it evaluates,
        i.e. it does not memoize the result."""
        mapping = {}
        string = LazyString(
            lambda x: '{}={}'.format(x, mapping.get(x, '<unknown>')), 'foo'
        )
        assert '{}'.format(string) == 'foo=<unknown>'
        mapping.update({'foo': 33, 'bar': 44})
        assert '{}'.format(string) == 'foo=33'

    def test_str_functionality(self):
        string = LazyString(lambda x: x * 2, 'foo')
        assert string == 'foofoo'
        assert len(string) == len('foofoo')
        assert string[1] == 'o'
        assert '.'.join([x for x in string]) == 'f.o.o.f.o.o'
        assert 'foo' in string
        assert 'goo' not in string
        assert string + 'z' == 'foofooz'
        assert 'z' + string == 'zfoofoo'
        assert string * 2 == 'foofoofoofoo'
        assert 2 * string == 'foofoofoofoo'
        assert string < 'goofoo'
        assert string > 'eoofoo'
        assert string <= 'goofoo'
        assert string >= 'eoofoo'
        assert {string: 'FOO'}.get('foofoo') == 'FOO'
