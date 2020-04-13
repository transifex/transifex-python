import importlib
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
    return datetime.utcnow().replace(tzinfo=pytz.utc)


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
