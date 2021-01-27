from django.conf import settings
from django.utils.translation import get_language, to_locale
from transifex.common.strings import LazyString
from transifex.native import tx


def translate(_string, _context=None, _escape=True, **params):
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
    is_source = get_language() == settings.LANGUAGE_CODE
    locale = to_locale(get_language())  # e.g. from en-us to en_US
    return tx.translate(
        _string,
        locale,
        _context=_context,
        is_source=is_source,
        escape=_escape,
        params=params,
    )


def lazy_translate(_string, _context=None, _escape=True, **params):
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
    return LazyString(
        translate, _string, _context=_context, escape=_escape, **params
    )


def utranslate(_string, _context=None, **params):
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
    return translate(_string, _context, _escape=False, **params)
