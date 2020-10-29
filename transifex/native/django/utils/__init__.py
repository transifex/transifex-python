from django.utils.translation import get_language, to_locale

from transifex.common.strings import LazyString
from transifex.native import tx
from transifex.native.rendering import html_escape


def translate(source_string, _context=None, _charlimit=None, _comment=None,
              _occurrences=None, _tags=None, _escape=True, **params):
    """Translate the given source string to the current language.

    A convenience wrapper that uses the current language of a Django app.

    If there are any placeholders to replace, they need to be passed as kwargs.

    :param unicode _string: the source string to get the translation for
    :param unicode _context: an optional context that gives more information
        about the source string
    :param bool _escape: if True, the returned string will be HTML-escaped,
        otherwise it won't
    :return: the final translation in the current language
    :rtype: unicode
    """
    locale = to_locale(get_language())  # e.g. from en-us to en_US
    return tx.translate(source_string, locale, _context=_context,
                        _charlimit=_charlimit, _comment=_comment,
                        _occurrences=_occurrences, _tags=_tags,
                        _escape=html_escape if _escape else None, **params)


def lazy_translate(source_string, _context=None, _charlimit=None,
                   _comment=None, _occurrences=None, _tags=None, _escape=True,
                   **params):
    """Lazily translate the given source string to the current language.

    Delays the evaluation of translating the given string until necessary.
    This is useful in cases where the call to translate() happens
    before any translations have been retrieved, e.g. in the definition
    of a Python class.

    See translate() for more details.

    :param unicode _string: the source string to get the translation for
    :param unicode _context: an optional context that gives more information
        about the source string
    :param bool _escape: if True, the returned string will be HTML-escaped,
        otherwise it won't
    :return: an object that when evaluated as a string will return
        the final translation in the current language
    :rtype: LazyString
    """
    return LazyString(translate, source_string, _context=_context,
                      _charlimit=_charlimit, _comment=_comment,
                      _occurrences=_occurrences, _tags=_tags, _escape=_escape
                      if _escape else None, **params)


def utranslate(source_string, _context=None, _charlimit=None, _comment=None,
               _occurrences=None, _tags=None, _escape=True, **params):
    """Translate the given source string to the current language, without HTML
    escaping.

    While the given `string` is not escaped, all `params` are, before replacing
    the placeholders inside the `string`.

    A convenience wrapper that uses the current language of a Django app.

    If there are any placeholders to replace, they need to be passed as kwargs.

    :param unicode _string: the source string to get the translation for
    :param unicode _context: an optional context that gives more information
        about the source string
    :return: the final translation in the current language
    :rtype: unicode
    """
    return tx.translate(source_string, _context=_context,
                        _charlimit=_charlimit, _comment=_comment,
                        _occurrences=_occurrences, _tags=_tags,
                        _escape=html_escape if _escape else None, **params)
