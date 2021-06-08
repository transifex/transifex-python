# -*- coding: utf-8 -*-
import logging
import sys
import xml.sax.saxutils as saxutils
from math import ceil

from pyseeyou import format
from transifex.common._compat import string_types, text_type
from transifex.common.utils import import_to_python

logger = logging.getLogger('transifex.rendering')
logger.addHandler(logging.StreamHandler(sys.stdout))


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


class StringRenderer(object):
    """Takes a translation string template and optional parameters
    and returns the final translation string."""

    @classmethod
    def render(
        cls, source_string, string_to_render, language_code, escape,
        missing_policy, params=None,
    ):
        """Render the given ICU string.

        Takes into account the given language code (for the plurals)
        as well as the given parameters.

        If the given `string_to_render` is None, it returns a rendered
        string based on the given `missing_policy`.

        :param unicode source_string: the full ICU string in the source
            language
        :param unicode string_to_render: the full ICU string to render as a
            string_to_render
        :param str language_code: the language code to use
        :param bool escape: if True, the returned string will be HTML-escaped,
            otherwise it won't
        :param AbstractRenderingPolicy missing_policy: the policy to use for
            returning strings when `string_to_render` is missing. If `None`,
            don't use a missing policy. In that case, if `string_to_render`
            does not exist, a `RenderingError` will be raised.
        :return: the final rendered string
        :rtype: unicode
        """

        if params is None:
            params = {}

        try:
            if not string_to_render and not missing_policy:
                raise Exception(
                    "No string to render and no missing policy defined!"
                    " (Source String: `{}`)".format(source_string)
                )

            # `string_to_render` doesn't exist, fallback to the missing policy
            if not string_to_render and missing_policy:
                if escape:
                    source_string = html_escape(source_string)
                return missing_policy.get(
                    format(source_string, params, language_code)
                )

            if escape:
                string_to_render = html_escape(string_to_render)

            rendered = format(string_to_render, params, language_code)
            return rendered
        except Exception as e:
            logger.error(
                "RenderingError: Could not render string `%s` in language `%s` "
                "with parameters `%s` (Error: %s, Source String: %s)",
                string_to_render, language_code, str(params),
                str(e), source_string
            )
            raise e


class AbstractRenderingPolicy(object):
    """An interface for classes that determine what translation is actually
    returned.

    Can be used in multiple cases, such as when the translation is not found
    """

    def get(self, source_string):
        """Return a string as a translation based on the given source string.

        Implementors may choose to return anything, relevant to the given
        source string or not, based on their custom policy

        :param unicode source_string: the source string
        :return: a new string
        :rtype: unicode
        """
        raise NotImplementedError()


class ChainedPolicy(AbstractRenderingPolicy):
    """Return a string by combining multiple policies."""

    def __init__(self, *policies):
        self._policies = policies

    def get(self, source_string):
        """Return the string that is generated after going through all policies.

        The result of each policy is fed to the next as source string.
        """
        translation = source_string
        for policy in self._policies:
            translation = policy.get(translation)

        return translation


class SourceStringPolicy(AbstractRenderingPolicy):
    """Return the source string when the translation string is missing."""

    def get(self, source_string):
        """Return the source string as the translation string."""
        return source_string


class PseudoTranslationPolicy(AbstractRenderingPolicy):
    """Return a string that looks like the source string but contains
    accented characters.

    Example:
    >>> PseudoTranslationPolicy().get(u'The quick brown fox')
    # returns u'Ťȟê ʠüıċǩ ƀȓøẁñ ƒøẋ'
    """

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

    def get(self, source_string):
        """Return a string that looks somewhat like the source string.

        :rtype: unicode
        """
        return text_type(source_string).translate(PseudoTranslationPolicy.TABLE)


class WrappedStringPolicy(AbstractRenderingPolicy):
    """Wrap the returned string with a custom format.

    Usage:
    >>> WrappedStringPolicy(u'>>', u'<<').get(u'Click here')
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

    def get(self, source_string):
        """Return a string that includes the source string."""
        return u'{}{}{}'.format(
            self.start or u'[',
            source_string,
            self.end or u']',
        )


class ExtraLengthPolicy(AbstractRenderingPolicy):
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

    def get(self, source_string):
        total_extra_chars = int(
            ceil(len(source_string) * self.extra_percentage)
        )

        if not total_extra_chars:
            return source_string

        repeats = int(ceil(total_extra_chars / float(len(self.extra_str))))
        extra_chars = self.extra_str * repeats
        return u'{}{}'.format(source_string, extra_chars[:total_extra_chars])


class AbstractErrorPolicy(object):
    """ Defines an interface for other error policy classes to implement.
    Error policies define what happens when rendering faces an error.
    They are useful to protect the user from pages failing to load."""

    def get(self, source_string, translation, language_code, escape,
            params=None):
        raise NotImplementedError()


class SourceStringErrorPolicy(AbstractErrorPolicy):
    """ An error policy that defaults to the source string.
    If rendering the source string fails as well, then it will default to
    an error string, configurable during initialization"""

    def __init__(self, default_text='ERROR'):
        self.default_text = default_text

    def get(
        self, source_string, translation, language_code,
        escape, params=None,
    ):
        """Try to render the source string. If something goes wrong,
        render a custom text provided by the user.

        :param str source_string: The source string
        :param str translation: The translation (which has failed to render)
        :param str language_code: The language code being used
        :param bool escape: Whether to escape or not
        """

        if params is None:
            params = {}

        try:
            return StringRenderer.render(
                source_string=source_string,
                string_to_render=source_string,
                language_code=language_code,
                escape=escape,
                missing_policy=None,
                params=params,
            )
        except Exception as e:
            logger.error(
                'ErrorPolicyError: Could not render string `{string}` '
                'with parameters `{parameters}`'.format(
                    string=source_string, parameters=str(params)
                )
            )

        # if all fails, return the default text
        return self.default_text
