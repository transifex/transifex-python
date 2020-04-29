from transifex.common.utils import now


class AbstractCache(object):
    """
    An interface for classes that cache translations.

    Implementors can use any type of storage for saving and retrieving
    the translations.
    """

    def get(self, key, language_code):
        """Return the translation stored in the cache for the specific
        key and language.

        The translation is a serialized string in ICU format.

        :param unicode key: the key of the translation to retrieve
        :param str language_code: the language code to retrieve the
            translation for
        :return: the stored translation or None if none found
        :rtype: unicode
        """
        # Example returns:
        #   'Hello there'
        #   '{num, plural, one {A table} other {{cnt} tables}}'
        #   '{num, gender, female {Her majesty} male {His majesty}}'
        pass

    def update(self, data):
        """Replace the cache with the given data.

        where `data` is expected to be structured like:
        {
            'fr': (True, {
                'key1': '...',
                'key2': '...',
            }),
            'de': (True, {
                'key1': '...',
                'key2': '...',
                'key3': '...',
            }),
            'gr': (False, {}),
        }

        Hint: the boolean values in the tuples above refer to whether local
        cache should be updated or not

        :param dict data: the translation data
        """
        pass


class MemoryCache(AbstractCache):
    """A cache that stores translations in memory."""

    def __init__(self):
        self._translations_by_lang = {}

    def update(self, data):
        """Replace the cache with the given data.

        :param dict data: the data to use in the cache, formatted as
            explained in AbstractCache.update()
        """
        for lang_code, (should_update, translations) in data.items():
            if should_update:
                self._translations_by_lang[lang_code] = {
                    'translations': translations,
                }

    def get(self, key, language_code):
        retrieved_translation = None
        try:
            retrieved_translation = self._translations_by_lang\
                .get(language_code, {})\
                .get('translations', {})\
                .get(key)\
                .get('string', None)
        except (ValueError, AttributeError):
            pass
        return retrieved_translation
