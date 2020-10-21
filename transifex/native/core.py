# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from transifex.common.utils import generate_key, parse_plurals
from transifex.native.cds import CDSHandler
from transifex.native.events import EventDispatcher
from transifex.native.rendering import (SourceStringErrorPolicy,
                                        SourceStringPolicy, StringRenderer)


class TxNative(object):
    """ The main class of the framework, responsible for orchestrating all
        behavior.
    """

    def __init__(self, **kwargs):
        # Public
        self.hardcoded_language_codes = None
        self.remote_languages = None
        self.source_language_code = None
        self.current_language_code = None

        # Private
        self._cache = {}
        self._missing_policy = SourceStringPolicy()
        self._error_policy = SourceStringErrorPolicy()
        self._cds_handler = CDSHandler()
        self._event_distpatcher = EventDispatcher()

        self.setup(**kwargs)

    def setup(self, languages=None, source_language_code=None,
              missing_policy=None, error_policy=None,
              token=None, secret=None, cds_host=None):
        if languages is not None:
            self.hardcoded_language_codes = languages
        if source_language_code is not None:
            self.source_language_code = source_language_code
        if missing_policy is not None:
            self._missing_policy = missing_policy
        if error_policy is not None:
            self._error_policy = error_policy

        self._cds_handler.setup(host=cds_host, token=token, secret=secret)

    def set_current_language_code(self, language_code):
        if language_code not in [language['code']
                                 for language in self.get_languages()]:
            raise ValueError("Language '{}' is not available".
                             format(language_code))
        if language_code not in self._cache:
            self.fetch_translations(language_code)
        self.current_language_code = language_code
        self._event_distpatcher.trigger('CURRENT_LANGUAGE_CHANGED',
                                        language_code)

    def get_languages(self, refetch=False):
        """ Returns the list of supported languages.

            If remote_languages hasn't been fetched, or if `refetch` is True,
            will fetch the languages that the remote Transifex projects
            supports.

            If `_hardcoded_languages` has been set (via the `languages` kwarg
            of the `__init__` of `setup`), the intersection of remote and
            hardcoded languages will be returned. Otherwise, all the remote
            languages will be.
        """

        if refetch or self.remote_languages is None:
            self._event_distpatcher.trigger("FETCHING_LANGUAGES")
            self.remote_languages = self._cds_handler.fetch_languages()
            self._event_distpatcher.trigger("LANGUAGES_FETCHED")
        if self.hardcoded_language_codes is not None:
            return [language
                    for language in self.remote_languages
                    if language['code'] in self.hardcoded_language_codes]
        else:
            return self.remote_languages

    def translate(self, source_string, language_code=None, _context=None,
                  _escape=None, **params):
        """ Translate the given string to the provided language.

            :param unicode source_string: the source string to get the
                translation for e.g. 'Order: {num, plural, one {A table} other
                {{num} tables}}'
            :param str language_code: the language to translate to
            :param unicode _context: an optional context that accompanies the
                string
            :param bool _escape: if True, the returned string will be
                HTML-escaped, otherwise it won't
            :param dict params: optional parameters to replace any placeholders
                found in the translation string
            :return: the rendered string
            :rtype: unicode
        """

        if language_code is None:
            language_code = self.current_language_code
        if language_code is None:
            language_code = self.source_language_code

        if language_code == self.source_language_code:
            translation_template = source_string
        else:
            pluralized, plurals = parse_plurals(source_string)
            key = generate_key(string=source_string, context=_context)
            translation_template = self._cache.get(language_code, {}).get(key)
            if (translation_template is not None and pluralized and
                    translation_template.startswith('{???')):
                variable_name = source_string[1:source_string.index(',')].\
                    strip()
                translation_template = ('{' +
                                        variable_name +
                                        translation_template[4:])

        try:
            return StringRenderer.render(
                source_string=source_string,
                string_to_render=translation_template,
                language_code=language_code,
                escape=_escape,
                missing_policy=self._missing_policy,
                params=params,
            )
        except Exception:
            return self._error_policy.get(
                source_string=source_string,
                translation=translation_template,
                language_code=language_code,
                escape=_escape,
                params=params,
            )

    def fetch_translations(self, language_code=None):
        """Fetch fresh content from the CDS."""

        if language_code is not None:
            self._event_distpatcher.trigger("FETCHING_TRANSLATIONS",
                                            language_code)
            refresh, translations = self._cds_handler.\
                fetch_translations(language_code)
            if refresh:
                self._cache[language_code] = translations
            self._event_distpatcher.trigger("TRANSLATIONS_FETCHED",
                                            language_code)
        else:
            for language in self.get_languages():
                self.fetch_translations(language['code'])

    # Map to event dispatcher
    def on(self, event_name, callback):
        self._event_distpatcher.on(event_name, callback)

    def off(self, event_name, callback):
        self._event_distpatcher.off(event_name, callback)

    def push_source_strings(self, strings, purge=False):
        """ Push the given source strings to the CDS.

            :param list strings: a list of SourceString objects
            :param bool purge: True deletes destination source content not
                included in pushed content.  False appends the pushed content
                to destination source content.
            :return: a tuple containing the status code and the content of the
                response
            :rtype: tuple
        """

        response = self._cds_handler.push_source_strings(strings, purge)
        return response.status_code, json.loads(response.content)
