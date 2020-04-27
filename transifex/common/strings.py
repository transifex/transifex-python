from __future__ import unicode_literals

# A single quote that is not preceded by \
# i.e. matches "This is 'something" but not "This is \' something"
import re

VAR_FORMAT = 'variable_{cnt}'

RE_SINGLE_QUOTE = r"(?<!\\)\'"
# A double quote that is not preceded by \
# i.e. matches 'This is "something' but not 'This is \" something'
RE_DOUBLE_QUOTE = r'(?<!\\)\"'


def printf_to_format_style(string):
    """Transform any %s-style placeholders in the given string to
    str.format() placeholders.

    Usage:
    >>> printf_to_format_style('This is %s & %s')
    <<< ('This is {variable_1} & {variable_2}', '['variable_1', 'variable_2']')

    >>> printf_to_format_style('This is %(foo)s and %(bar)s')
    <<< ('This is {foo} and {bar}', ['foo', 'bar'])

    :param unicode string: the source string
    :return: a tuple, containing the new string (with Transifex Native syntax)
        and a list of the names of all variables
    :rtype: tuple
    """
    obj = {'cnt': 1, 'variables': []}  # Python 2 nonlocal workaround

    def replace_named(match):
        """Given a regex match like '%(foo)s' return '{foo}'.

        Also stores the found variable inside `obj`.

        :param match: a regex match object
        :return: a new string using ICU placeholder syntax
        :rtype: str
        """
        # [2:-2] means from '%(foo)s' -> get 'foo'
        var = match.group(0)[2:-2]
        new = '{{{}}}'.format(var)
        obj['variables'].append(var)
        return new

    pattern = re.compile(r'(%\(\w+\)s)')
    new_string, total = re.subn(
        pattern,
        replace_named,
        string
    )

    def replace_unnamed(match):
        """Given a regex match like '%s' return '{variable_N}' where N
        is an auto-increase integer.

        Also stores the found variable inside `obj`.

        :param match: a regex match object
        :return: a new string using ICU placeholder syntax
        :rtype: str
        """
        var = VAR_FORMAT.format(cnt=str(obj['cnt']))
        new = '{{{}}}'.format(var)
        obj['variables'].append(var)
        obj['cnt'] += 1
        return new

    pattern = re.compile('(%s)')
    new_string, total = re.subn(pattern, replace_unnamed, new_string)

    return new_string, obj['variables']


def alt_quote(quote, string):
    """Return the proper quote character to use for wrapping the given string.

    Takes into account any identical quotes that are included in the string
    and, if found, it returns the alternate quote type, to avoid breaking the
    code if the string is wrapped in quotes.

    Usage:
    >>> alt_quote('"', 'This is a string')
    '"' (double quote)
    >>> alt_quote('"', 'This is a " string')
    "'" (single quote)
    >>> alt_quote('"', 'This is a \" string')
    '"' (double quote)


    :param unicode quote: either ' or ", the preferred quote to use for wrapping
        `string`
    :param unicode string: the string that will be wrapped in quotes
    :return: a new string
    :rtype: unicode
    """
    alternate = '"' if quote == "'" else "'"
    pattern = RE_SINGLE_QUOTE if quote == "'" else RE_DOUBLE_QUOTE
    pattern_alt = RE_SINGLE_QUOTE if quote == '"' else RE_DOUBLE_QUOTE
    if re.search(pattern, string) and not re.search(pattern_alt, string):
        return alternate
    return quote
