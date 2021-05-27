import importlib
import re
from datetime import datetime
from hashlib import md5

import pytz


def generate_key(string=None, context=None, parsed=False, plurals=None):
    """Return a unique key based on the given source string and context.

    :param str string: An ICU string
    :param dict plurals: A dictionary with pre-parsed plurals.
        Should be like:
            { 1: "Here is one dog",
              5: "Here are many dogs"}
    :param Union[unicode, list] context: an optional context that
        accompanies the string
    :return: a unique key
    :rtype: str
    """

    def escape_plural(plural):
        """ Escape the : character (and the \ character that will be
        used for escaping)"""
        return plural.replace('\\', '\\\\').replace(':', '\:')

    if not string and not plurals:
        raise ValueError("You need to specify at least "
                         "one of `string`, `plurals`")
    if string and plurals:
        raise ValueError("Cannot use both `string` and `plurals`")

    if not plurals:
        _, plurals = parse_plurals(string)

    string_content = u':'.join(
        u'{}:{}'.format(rule, escape_plural(string))
        for rule, string in sorted(
            plurals.items(), key=lambda x: x[0]
        )
    )

    if context:  # pragma: no cover
        if isinstance(context, list):
            context = u':'.join(context)
        else:
            context = u':'.join(context.split(','))
    if not context:  # pragma: no cover
        context = ''
    return md5(
        (':'.join([string_content, context])).encode('utf-8')
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
        return tuple((make_hashable(item) for item in sorted(data)))
    elif isinstance(data, dict):
        return tuple(
            (key, make_hashable(value))
            for key, value in sorted(data.items())
        )
    else:
        return data


def parse_plurals(string):
    """ Tries to parse an ICU (possibly pluralized) string, returning its
        plurals separated. It only works if `string` is the simplest possible
        version of a pluralized ICU string, ie whether the plural syntax is on
        the outermost part of the string.

        So, this `{cnt, plural, one {ONE} other {OTHER}}` will return a parsed version,
        but this `hello {cnt, plural, one {ONE} other {OTHER}}` will not.

        The plurals dictionary looks like:
            { 1: "Here is one dog",
              5: "Here are many dogs"}

        If a string cannot be parsed, it's considered a non-pluralized string and is
        assigned the rule "5".

        :rtype: tuple(bool, dict) (Whether the string was parsed & the resulted plurals)
    """

    plurals = {}
    try:
        # {cnt, plural, one {foo} other {foos}}
        # ^^^^^^^^^^^^
        variable_name, remaining = _consume_preamble(string)
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
        return (False, {5: string})

    if ((len(plurals) == 1 and 5 not in plurals) or
            bool({1, 5} - set(plurals.keys()))):
        return (False, {5: string})

    return (True, plurals)


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

    def _get_rule_num(rule):
        return {
            'zero': 0, 'one': 1, 'two': 2,
            'few': 3, 'many': 4, 'other': 5
        }[rule]

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

    return _get_rule_num(rule), string[left_bracket_pos:].strip()


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
