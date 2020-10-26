# -*- coding: utf-8 -*-
import logging
import sys
import xml.sax.saxutils as saxutils
from math import ceil

from pyseeyou import format as icu_format

from transifex.common._compat import string_types, text_type
from transifex.common.utils import import_to_python

logger = logging.getLogger('transifex.rendering')
logger.addHandler(logging.StreamHandler(sys.stdout))


def identity(s):
    return s


def html_escape(item):
    """Escape certain HTML entities for security reasons.

    :param object item: the item to escape (could be a string, number, boolean)
    :return: the escaped value or the original value if not eligible for
        escaping
    :rtype: object
    """
    if not isinstance(item, string_types):
        return item

    html_escape_table = {
        '"': "&quot;",
        "'": "&#x27;"
    }
    return saxutils.escape(item, html_escape_table)


class ChainedMissingPolicy(object):
    """Return a string by combining multiple policies."""

    def __init__(self, *policies):
        self._policies = policies

    def __call__(self, source_string):
        """Return the string that is generated after going through all policies.

        The result of each policy is fed to the next as source string.
        """
        translation = source_string
        for policy in self._policies:
            translation = policy(translation)

        return translation


def source_string_missing_policy(source_string):
    return source_string


def pseudo_translation_missing_policy(source_string):
    TABLE = {
        # A to Z
        0x0041: 0x00C5, 0x0042: 0x0181, 0x0043: 0x010A, 0x0044: 0x0110,
        0x0045: 0x0204, 0x0046: 0x1E1E, 0x0047: 0x0120, 0x0048: 0x021E,
        0x0049: 0x0130, 0x004A: 0x0134, 0x004B: 0x01E8, 0x004C: 0x0139,
        0x004D: 0x1E40, 0x004E: 0x00D1, 0x004F: 0x00D2, 0x0050: 0x01A4,
        0x0051: 0xA756, 0x0052: 0x0212, 0x0053: 0x0218, 0x0054: 0x0164,
        0x0055: 0x00DC, 0x0056: 0x1E7C, 0x0057: 0x1E82, 0x0058: 0x1E8C,
        0x0059: 0x1E8E, 0x005A: 0x017D,

        # a to z
        0x0061: 0x00E0, 0x0062: 0x0180, 0x0063: 0x010B, 0x0064: 0x0111,
        0x0065: 0x00EA, 0x0066: 0x0192, 0x0067: 0x011F, 0x0068: 0x021F,
        0x0069: 0x0131, 0x006A: 0x01F0, 0x006B: 0x01E9, 0x006C: 0x013A,
        0x006D: 0x0271, 0x006E: 0x00F1, 0x006F: 0x00F8, 0x0070: 0x01A5,
        0x0071: 0x02A0, 0x0072: 0x0213, 0x0073: 0x0161, 0x0074: 0x0165,
        0x0075: 0x00FC, 0x0076: 0x1E7D, 0x0077: 0x1E81, 0x0078: 0x1E8B,
        0x0079: 0x00FF, 0x007A: 0x017A,
    }
    return text_type(source_string).translate(TABLE)


class WrappedStringMissingPolicy(object):
    """Wrap the returned string with a custom format.

    Usage:
    >>> WrappedStringMissingPolicy(u'>>', u'<<')(u'Click here')
    # returns u'>>Click here<<'
    """

    def __init__(self, start=None, end=None):
        """Constructor.

        :param unicode start: an optional string to prepend to
            the source string
        :param unicode end: an optional string to append to the source string
        """
        self.start = start
        self.end = end

    def __call__(self, source_string):
        """Return a string that includes the source string."""
        return u'{}{}{}'.format(
            self.start or u'[',
            source_string,
            self.end or u']',
        )


class ExtraLengthMissingPolicy(object):
    """Amend the string with extra characters, to reach a certain length.

    Useful for testing longer strings on UI elements.
    """

    def __init__(self, extra_percentage=0.3, extra_str=u'~extra~'):
        """Constructor.

        :param extra_percentage:
        :param extra_str:
        """
        self.extra_percentage = extra_percentage
        self.extra_str = extra_str

    def __call__(self, source_string):
        total_extra_chars = int(
            ceil(len(source_string) * self.extra_percentage)
        )

        if not total_extra_chars:
            return source_string

        repeats = int(ceil(total_extra_chars / float(len(self.extra_str))))
        extra_chars = self.extra_str * repeats
        return u'{}{}'.format(source_string, extra_chars[:total_extra_chars])


def parse_missing_policy(policy):
    """Parse the given rendering policy and return a callable subclass.

    :param Union[callable, str, tuple(str, dict), list] policy:
        could be
        - an instance of callable
        - a tuple of the class's path and parameters
        - the class's path
        - a list of callable objects or tuples or string paths
    :return: a callable object
    :rtype: callable
    """
    if callable(policy) or policy is None:
        return policy

    if isinstance(policy, list):
        return ChainedMissingPolicy(*[parse_missing_policy(p)
                                      for p in policy])

    # Reaching here means it's a tuple like (<path>, <params>)
    # or a string like <path>
    try:
        path, params = policy
    except ValueError:
        path, params = policy, None

    _class = import_to_python(path)
    if params:
        return _class(**params)
    return _class


class SourceStringErrorPolicy(object):
    """ An error policy that defaults to the source string.
    If rendering the source string fails as well, then it will default to
    an error string, configurable during initialization"""

    def __init__(self, default_text='ERROR'):
        self.default_text = default_text

    def __call__(
        self, source_string, translation_template, language_code,
        escape, params=None,
    ):
        """Try to render the source string. If something goes wrong,
        render a custom text provided by the user.

        :param str source_string: The source string
        :param str translation_template: The translation template (which has
            failed to render)
        :param str language_code: The language code being used
        :param bool escape: Whether to escape or not
        """

        if params is None:
            params = {}

        try:
            return icu_format(source_string, params, language_code)
        except Exception:
            return self.default_text


def parse_error_policy(policy):
    """Parse the given error policy and return an callable object.

    :param Union[callable, str, tuple(str, dict), list] policy:
        could be
        - an callable instance
        - a tuple of the class's path and parameters
        - the class's path
    :return: a callable object
    :rtype: callable
    """
    if callable(policy) or policy is None:
        return policy

    # Reaching here means it's a tuple like (<path>, <params>)
    # or a string like <path>
    try:
        path, params = policy
    except ValueError:
        path, params = policy, None

    _class = import_to_python(path)
    if params:
        return _class(**params)
    return _class()
