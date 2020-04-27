from __future__ import unicode_literals

from transifex.common.strings import printf_to_format_style


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
