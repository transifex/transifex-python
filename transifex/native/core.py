# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from transifex.common.utils import generate_key, parse_plurals
from transifex.native.cache import MemoryCache
from transifex.native.cds import CDSHandler
from transifex.native.rendering import (SourceStringErrorPolicy,
                                        SourceStringPolicy, StringRenderer)


class TxNative(object):
    """The main class of the framework, responsible for orchestrating all
    behavior."""

    def __init__(self, **kwargs):
        self.source_language_code = None
        self.current_language_code = None
        self.hardcoded_language_codes = None
        self.remote_languages = None

        self._missing_policy = SourceStringPolicy()
        self._cds_handler = CDSHandler()
        self._cache = MemoryCache()
        self._error_policy = SourceStringErrorPolicy()

        self.setup(**kwargs)

    def setup(self,
              source_language=None, current_language=None, languages=None,
              token=None, secret=None, cds_host=None,
              missing_policy=None, error_policy=None):
        """Create an instance of the core framework class.

        Also warms up the cache by fetching the translations from the CDS.

        :param list languages: a list of language codes for the languages
            configured in the application
        :param str token: the API token to use for connecting to the CDS
        :param str secret: the additional secret to use for pushing source
            content
        :param str cds_host: an optional host for the Content Delivery Service,
            defaults to the host provided by Transifex
        :param AbstractRenderingPolicy missing_policy: an optional policy
            to use for returning strings when a translation is missing
        :param AbstractErrorPolicy error_policy: an optional policy
            to determine how to handle rendering errors
        """
        if source_language is not None:
            self.source_language_code = source_language
        if current_language is not None:
            self.current_language_code = current_language
        if languages is not None:
            self.hardcoded_language_codes = languages
        if missing_policy is not None:
            self._missing_policy = missing_policy
        if error_policy is not None:
            self._error_policy = error_policy

        self._cds_handler.setup(token=token,
                                secret=secret,
                                host=cds_host)

    def fetch_languages(self, force=False):
        if self.remote_languages is None or force:
            self.remote_languages = self._cds_handler.fetch_languages()

        if self.hardcoded_language_codes is not None:
            return [language
                    for language in self.remote_languages
                    if language['code'] in self.hardcoded_language_codes]
        else:
            return self.remote_languages

    def fetch_translations(self, language_code=None, force=False):
        """Fetch fresh content from the CDS."""
        if language_code is None:
            for language in self.fetch_languages():
                self.fetch_translations(language['code'], force=force)
        else:
            translations = self._cds_handler.fetch_translations(language_code)
            self._cache.update(translations)

    def translate(
        self, source_string, language_code, is_source=False,
        _context=None, escape=True, params=None
    ):
        """Translate the given string to the provided language.

        :param unicode source_string: the source string to get the translation
            for e.g. 'Order: {num, plural, one {A table} other {{num} tables}}'
        :param str language_code: the language to translate to
        :param bool is_source: a boolean indicating whether `translate`
            is being used for the source language
        :param unicode _context: an optional context that accompanies
            the string
        :param bool escape: if True, the returned string will be HTML-escaped,
            otherwise it won't
        :param dict params: optional parameters to replace any placeholders
            found in the translation string
        :return: the rendered string
        :rtype: unicode
        """

        if params is None:
            params = {}

        translation_template = self.get_translation(source_string,
                                                    language_code,
                                                    _context,
                                                    is_source)

        return self.render_translation(translation_template,
                                       params,
                                       source_string,
                                       language_code,
                                       escape)

    def get_translation(self, source_string, language_code, _context,
                        is_source=False):
        """ Try to retrieve the translation.

            A translation is a serialized source_string with ICU format
            support, e.g.
            '{num, plural, one {Ένα τραπέζι} other {{num} τραπέζια}}'
        """

        if is_source:
            translation_template = source_string
        else:
            pluralized, plurals = parse_plurals(source_string)
            key = generate_key(string=source_string, context=_context)
            translation_template = self._cache.get(key, language_code)
            if (translation_template is not None and pluralized and
                    translation_template.startswith('{???')):
                variable_name = source_string[1:source_string.index(',')].\
                    strip()
                translation_template = ('{' +
                                        variable_name +
                                        translation_template[4:])
        return translation_template

    def render_translation(self, translation_template, params, source_string,
                           language_code, escape=False):
        """ Replace the variables in the ICU translation """

        try:
            return StringRenderer.render(
                source_string=source_string,
                string_to_render=translation_template,
                language_code=language_code,
                escape=escape,
                missing_policy=self._missing_policy,
                params=params,
            )
        except Exception:
            return self._error_policy.get(
                source_string=source_string,
                translation=translation_template,
                language_code=language_code,
                escape=escape, params=params,
            )

    def push_source_strings(self, strings, purge=False):
        """Push the given source strings to the CDS.

        :param list strings: a list of SourceString objects
        :param bool purge: True deletes destination source content not included
                           in pushed content.
                           False appends the pushed content to destination
                           source content.
        :return: a tuple containing the status code and the content of the
            response
        :rtype: tuple
        """
        response = self._cds_handler.push_source_strings(strings, purge)
        return response.status_code, json.loads(response.content)
