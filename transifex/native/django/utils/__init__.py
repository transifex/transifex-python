from django.conf import settings
from django.utils.translation import get_language, to_locale
from transifex.native import tx


def translate(string, _context=None, escape=True, **params):
    """Translate the given source string to the current language.

    A convenience wrapper that uses the current language of a Django app.

    If there are any placeholders to replace, they need to be passed as kwargs.

    :param unicode string: the source string to get the translation for
    :param unicode _context: an optional context that gives more information about
        the source string
    :param bool escape: if True, the returned string will be HTML-escaped,
        otherwise it won't
    :return: the final translation in the current language
    :rtype: unicode
    """
    is_source = get_language() == settings.LANGUAGE_CODE
    locale = to_locale(get_language())  # e.g. from en-us to en_US
    return tx.translate(
        string,
        locale,
        _context=_context,
        is_source=is_source,
        escape=escape,
        params=params,
    )


def utranslate(string, _context=None, **params):
    """Translate the given source string to the current language, without HTML escaping.

    While the given `string` is not escaped, all `params` are, before replacing
    the placeholders inside the `string`.

    A convenience wrapper that uses the current language of a Django app.

    If there are any placeholders to replace, they need to be passed as kwargs.

    :param unicode string: the source string to get the translation for
    :param unicode _context: an optional context that gives more information about
        the source string
    :return: the final translation in the current language
    :rtype: unicode
    """
    return translate(string, _context, escape=False, **params)
