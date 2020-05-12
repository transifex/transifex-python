from __future__ import unicode_literals

# A single quote that is not preceded by \
# i.e. matches "This is 'something" but not "This is \' something"
import re

from transifex.common._compat import PY3, binary_type, text_type

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
    :return: a tuple, containing the new string (with str.format() syntax)
        and a list of the names of all variables
    :rtype: tuple
    """
    obj = {'cnt': 1, 'variables': []}  # Python 2 nonlocal workaround

    def replace_named(match):
        """Given a regex match like '%(foo)s' return '{foo}'.

        Also stores the found variable inside `obj`.

        :param match: a regex match object
        :return: a new string using str.format() placeholder syntax
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
        :return: a new string using str.format() placeholder syntax
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
    >>> alt_quote('"', r'This is a \" string')
    '"' (double quote)

    :param unicode quote: either ' or ", the preferred quote to use for
        wrapping `string`
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


class LazyString(object):
    """Can be used instead of a string instance when delayed evaluation
    is desired.

    Upon instantiation, the caller needs to provide a function along
    with any parameters, that will be used when the string value will be
    evaluated.

    Lazy evaluation is achieved through Pythons magic methods `__str__`
    and `__unicode__`.

    Usage:
    In the following example, the value of 'foo' and 'bar' is not available
    # when the string is declared (mapping is empty). However, mapping is only
    # accessed
    >>> mapping = {}
    >>> string = LazyString(lambda x: '{}={}'.format(x, mapping[x]), 'foo')
    >>> mapping.update({'foo': 33, 'bar': 44})
    >>> print(string)
    foo=44
    """

    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._encoding = kwargs.pop('encoding', 'utf-8')
        self._kwargs = kwargs

    def __getattr__(self, attr):
        if attr == "__setstate__":
            raise AttributeError(attr)
        string = self._text()
        if hasattr(string, attr):
            return getattr(string, attr)
        raise AttributeError(attr)

    @property
    def _resolved(self):
        """Call the proper text_type wrapper (str() or unicode() depending
        on the Python version) on the resolved value."""
        return self._text()

    def __unicode__(self):  # pragma: no cover
        """Resolve the value of the string.

        Calls the evaluation function together with all parameters.
        """

        return self._text()

    def __str__(self):  # pragma: no cover
        """Resolve the value of the string.

        Calls the evaluation function together with all parameters.
        """

        if PY3:
            return self._text()
        else:
            return self._binary()

    def __bytes__(self):  # pragma: no cover
        """Resolve the value of the string.

        Calls the evaluation function together with all parameters.
        """

        return self._binary()

    def _text(self):  # pragma: no cover
        text = self._func(*self._args, **self._kwargs)
        if isinstance(text, binary_type):
            text = text.decode(self._encoding)
        return text

    def _binary(self):  # pragma: no cover
        binary = self._func(*self._args, **self._kwargs)
        if isinstance(binary, text_type):
            binary = binary.encode(self._encoding)
        return binary

    def __len__(self):
        return len(self._resolved)

    def __getitem__(self, key):
        return self._resolved[key]

    def __iter__(self):
        return iter(self._resolved)

    def __contains__(self, item):
        return item in self._resolved

    def __add__(self, other):
        return self._resolved + other

    def __radd__(self, other):
        return other + self._resolved

    def __mul__(self, other):
        return self._resolved * other

    def __rmul__(self, other):
        return other * self._resolved

    def __lt__(self, other):
        return self._resolved < other

    def __le__(self, other):
        return self._resolved <= other

    def __eq__(self, other):
        return self._resolved == other

    def __ne__(self, other):
        return self._resolved != other

    def __gt__(self, other):
        return self._resolved > other

    def __ge__(self, other):
        return self._resolved >= other

    def __hash__(self):
        return hash(self._text())
