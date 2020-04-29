import importlib
import re
from datetime import datetime
from hashlib import md5

import pytz
import six

if six.PY3:
    unicode_compat = str
else:
    unicode_compat = unicode


def generate_key(source_string, context=None):
    """Return a unique key based on the given source string and context.

    :param unicode source_string: the source string
    :param Union[unicode, list] context: an optional context that accompanies the string
    :return: a unique key
    :rtype: str
    """
    if context:  # pragma: no cover
        if isinstance(context, list):
            context = u':'.join(context)
        else:
            context = u':'.join(context.split(','))
    if not context:  # pragma: no cover
        context = ''
    return md5(
        (':'.join([source_string, context])).encode('utf-8')
    ).hexdigest()


def now():
    """Return the current datetime, as a UTC-aware object.

    :rtype: datetime
    """
    return datetime.utcnow().replace(tzinfo=pytz.utc)  # pragma no cover


def import_to_python(import_str):
    """Given a string 'a.b.c' return object c from a.b module.

    :param str import_str: a path like a.b.c.
    """
    mod_name, obj_name = import_str.rsplit('.', 1)
    obj = getattr(importlib.import_module(mod_name), obj_name)
    return obj


def make_hashable(data):
    """Make the given object hashable.

    It makes it ready to use in a `hash()` call, making sure that
    it's always the same for lists and dictionaries if they have the same items.

    :param object data: the object to hash
    :return: a hashable object
    :rtype: object
    """
    if isinstance(data, (list, tuple)):
        return tuple((make_hashable(item) for item in data))
    elif isinstance(data, dict):
        return tuple(
            (key, make_hashable(value))
            for key, value in sorted(data.items())
        )
    else:
        return data


def is_plural(string):
    """ Determine if `string` is the simplest possible version of a pluralized
        ICU string, ie whether the plural syntax is on the outermost part of
        the string.

        So, this `{cnt, plural, one {ONE} other {OTHER}}` will return True, but
        this `hello {cnt, plural, one {ONE} other {OTHER}}` will return False.
    """

    try:
        # {cnt, plural, one {foo} other {foos}}
        # ^^^^^^^^^^^^
        variable_name, remaining = _consume_preamble(string)
        plurals = {}
        # {cnt, plural, one {foo} other {foos}}
        #               ^^^^^^^^^
        rule, remaining = _consume_rule(remaining)
        plural, remaining = _consume_plural(remaining.strip())
        plurals[rule] = plural
        while remaining.strip():
            # {cnt, plural, one {foo} other {foos}}
            #                         ^^^^^^^^^^^^
            rule, remaining = _consume_rule(remaining.strip())
            plural, remaining = _consume_plural(remaining.strip())
            plurals[rule] = plural
    except Exception:
        return False

    if ((len(plurals) == 1 and 'other' not in plurals) or
            bool({'one', 'other'} - set(plurals.keys()))):
        return False

    return True


# The `_consume_FOO` functions take an input, "consume" a part of it to produce
# the first return value and return the "unconsumed" part of the input as the
# second return value
def _consume_preamble(string):
    """ Usage:

            >>> _consume_preamble('{cnt, plural, one {ONE} other {OTHER}}')
            <<< ('cnt', 'one {ONE} other {OTHER}')
    """

    if string[0] != '{' or string[-1] != '}':
        raise ValueError()
    first_comma_pos = string.index(',')
    second_comma_pos = string.index(',', first_comma_pos + 1)
    variable_name = string[1:first_comma_pos].strip()
    keyword = string[first_comma_pos + 1:second_comma_pos].strip()
    if not re.search(r'[\w_]+', variable_name) or keyword != "plural":
        raise ValueError()
    return variable_name, string[second_comma_pos + 1:-1].strip()


def _consume_rule(string):
    """ Usage:

            >>> _consume_rule('one {ONE} other {OTHER}')
            <<< ('one', '{ONE} other {OTHER}')
            >>> _consume_rule('other {OTHER}')
            <<< ('other', '{OTHER}')
    """

    left_bracket_pos = string.index('{')
    rule = string[:left_bracket_pos].strip()
    if rule[0] == "=":
        rule = rule[1:]
        rule = int(rule)
        rule = {0: "zero",
                1: "one", 2: "two", 3: "few", 4: "many", 5: "other"}[rule]
    else:
        if rule not in ('zero', 'one', 'two', 'few', 'many', 'other'):
            raise ValueError()
    return rule, string[left_bracket_pos:].strip()


def _consume_plural(string):
    """ Usage:

            >>> _consume_plural('{ONE} other {OTHER}')
            <<< ('ONE', 'other {OTHER}')
            >>> _consume_plural('{OTHER}')
            <<< ('OTHER', '')
    """

    bracket_count, escaping = 0, False
    ptr = 0
    while ptr < len(string):
        char = string[ptr]
        if char == "'":
            try:
                peek = string[ptr+1]
            except IndexError:  # pragma: no cover
                peek = None
            if peek == "'":
                ptr += 1
            else:
                if escaping:
                    escaping = False
                else:
                    if peek in ('{', '}'):
                        escaping = True
        elif char == '{':
            if not escaping:
                bracket_count += 1
        elif char == '}':
            if not escaping:
                bracket_count -= 1
            if bracket_count == 0:
                return string[1:ptr], string[ptr + 1:].strip()
        ptr += 1
    raise ValueError()
