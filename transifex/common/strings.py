from __future__ import unicode_literals

# A single quote that is not preceded by \
# i.e. matches "This is 'something" but not "This is \' something"
import re
from functools import wraps

VAR_FORMAT = "variable_{cnt}"

RE_SINGLE_QUOTE = r"(?<!\\)\'"
# A double quote that is not preceded by \
# i.e. matches 'This is "something' but not 'This is \" something'
RE_DOUBLE_QUOTE = r"(?<!\\)\""


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
    obj = {"cnt": 1, "variables": []}  # Python 2 nonlocal workaround

    def replace_named(match):
        """Given a regex match like '%(foo)s' return '{foo}'.

        Also stores the found variable inside `obj`.

        :param match: a regex match object
        :return: a new string using str.format() placeholder syntax
        :rtype: str
        """
        # [2:-2] means from '%(foo)s' -> get 'foo'
        var = match.group(0)[2:-2]
        new = "{{{}}}".format(var)
        obj["variables"].append(var)
        return new

    pattern = re.compile(r"(%\(\w+\)s)")
    new_string, total = re.subn(pattern, replace_named, string)

    def replace_unnamed(match):
        """Given a regex match like '%s' return '{variable_N}' where N
        is an auto-increase integer.

        Also stores the found variable inside `obj`.

        :param match: a regex match object
        :return: a new string using str.format() placeholder syntax
        :rtype: str
        """
        var = VAR_FORMAT.format(cnt=str(obj["cnt"]))
        new = "{{{}}}".format(var)
        obj["variables"].append(var)
        obj["cnt"] += 1
        return new

    pattern = re.compile("(%s)")
    new_string, total = re.subn(pattern, replace_unnamed, new_string)

    return new_string, obj["variables"]


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


def lazy_str_meta(name, bases, dct):
    """Metaclass for lazy strings. We modify all functions of `str` except the
    "dangerous" ones to versions that operate on `str(self)`. `str(self)` is what
    performs the lazy evaluation of the string (see below).
    """

    for attr in set(dir(str)) - {
        "__repr__",
        "__sizeof__",
        "__init__",
        "__doc__",
        "__reduce__",
        "__new__",
        "__str__",
        "__dir__",
        "__getnewargs__",
        "__getattribute__",
        "__subclasshook__",
        "__delattr__",
        "__setattr__",
        "__reduce_ex__",
        "__init_subclass__",
        "__class__",
    }:
        func = getattr(str, attr)
        if not callable(func):
            continue

        # We have to do this "double-wrapping" of the function because otherwise all
        # functions assigned to `dct` will have the same, last function we defined
        def a(func):
            @wraps(func)
            def b(self, *args, **kwargs):
                return func(str(self), *args, **kwargs)

            return b

        dct[attr] = a(func)

    return type(name, bases, dct)


class LazyString(str, metaclass=lazy_str_meta):
    """Lazy string implementation.

    We use __new__ to save an empty string and also the '_func', '_args' and '_kwargs'
    attributes. The empty string is not supposed to be used anywhere. Instead, all
    methods that would be inherited from `str` have been replaced by the metaclass with
    ones that operate on `str(self)`, which runs the lazy evaluation. We also manually
    override '__radd__'.

        Usage:

            >>> mapping = {}
            >>> s = LazyString(lambda: "hello {name}".format(**mapping))
            >>> mapping['name'] = "Bill"

            >>> str(s)
            <<< 'hello Bill'

            >>> print(s)
            <<< hello Bill

            >>> isinstance(s, str)
            <<< True
    """

    def __new__(cls, func, *args, **kwargs):
        result = super().__new__(cls, "")
        result._func = func
        result._args = args
        result._kwargs = kwargs
        return result

    def __str__(self):
        """Perform lazy evaluation"""

        return self._func(*self._args, **self._kwargs)

    def __radd__(right, left):
        """`str` doesn't define `__radd__` because for its use-case, `__add__` is
        enough. However, since we want both:

            - `LazyString(lambda: "lazy string") + "string"` and
            - `"string" + LazyString(lambda: "lazy string")`

        to work, we need to implement `__radd__` ourselves.
        """

        return left + str(right)
