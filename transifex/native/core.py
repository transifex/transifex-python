# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from transifex.common.utils import generate_key, parse_plurals
from transifex.native.cache import MemoryCache
from transifex.native.cds import CDSHandler
from transifex.native.rendering import (SourceStringErrorPolicy,
                                        SourceStringPolicy, StringRenderer)


class NotInitializedError(Exception):
    """Raised when a method of a TxNative instance is called but the class
    hasn't been initialized.

    Allows for better debugging when developers neglect to call init().
    """
    pass


class TxNative(object):
    """The main class of the framework, responsible for orchestrating all
    behavior."""

    def __init__(self):
        # The class uses an untypical initialization scheme, defining
        # an init() method, instead of initializing inside the constructor
        # This is necessary for allowing it to be initialized by its clients
        # with proper arguments, while at the same time being very easy
        # to import and use a single "global" instance
        self._cache = None
        self._languages = []
        self._error_policy = None
        self._missing_policy = None
        self._cds_handler = None
        self.initialized = False

    def init(
        self, languages, token, secret=None, cds_host=None,
        missing_policy=None, error_policy=None, cache=None,
    ):
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
        :param AbstractCache cache: an optional cache
        """
        self._languages = languages
        self._cache = cache or MemoryCache()
        self._missing_policy = missing_policy or SourceStringPolicy()
        self._error_policy = error_policy or SourceStringErrorPolicy()
        self._cds_handler = CDSHandler(
            self._languages, token, secret=secret, host=cds_host
        )
        self.initialized = True

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

        self._check_initialization()

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
        """Return the proper translation for the given string
        and language code.

        A translation is a serialized source_string with ICU format
        support, e.g.
        '{num, plural, one {Ένα τραπέζι} other {{num} τραπέζια}}'

        Supports strings in the source language as well, which means
        that if there is a translation available in the cache
        for the source language, it will be used instead of the
        original source_string provided here.
        """
        pluralized, plurals = parse_plurals(source_string)
        key = generate_key(string=source_string, context=_context)
        translation_template = self._cache.get(key, language_code)
        if (translation_template is not None and pluralized and
                translation_template.startswith('{???')):
            variable_name = source_string[1:source_string.index(',')].strip()
            translation_template = '{{{var}{content}'.format(
                var=variable_name,
                content=translation_template[4:],
            )

        # If rendering the source language and there is no
        # (overridden) translation in the cache, use the original
        # source string
        if is_source and not translation_template:
            translation_template = source_string

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

    def fetch_translations(self):
        """Fetch fresh content from the CDS."""
        self._check_initialization()
        self._cache.update(self._cds_handler.fetch_translations())

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
        self._check_initialization()
        response = self._cds_handler.push_source_strings(strings, purge)
        return response.status_code, json.loads(response.content)

    def invalidate_cache(self, purge=False):
        """Invalidate CDS cache."""
        self._check_initialization()
        response = self._cds_handler.invalidate_cache(purge)
        return response.status_code, json.loads(response.content)

    def _check_initialization(self):
        """Raise an exception if the class has not been initialized.

        :raise NotInitializedError: if the class hasn't been initialized
        """
        if not self.initialized:
            raise NotInitializedError(
                'TxNative is not initialized, make sure you call init() first.'
            )
