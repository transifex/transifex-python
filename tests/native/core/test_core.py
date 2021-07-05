# -*- coding: utf-8 -*-

import pytest
from mock import MagicMock, patch
from transifex.common.utils import generate_key
from transifex.native.cache import MemoryCache
from transifex.native.cds import TRANSIFEX_CDS_HOST
from transifex.native.core import NotInitializedError, TxNative
from transifex.native.parsing import SourceString
from transifex.native.rendering import (PseudoTranslationPolicy,
                                        SourceStringPolicy)
from transifex.native.settings import parse_error_policy


class TestSourceString(object):
    """Tests the functionality of the SourceString class."""

    def test_default_values(self):
        string = SourceString('something')
        assert string.string == 'something'
        assert string.context is None
        assert string.meta == {}
        assert string.developer_comment is None
        assert string.character_limit is None
        assert string.tags == []

    def test_custom_meta(self):
        string = SourceString(
            'something',
            _context='one,two,three',
            _comment='A crucial comment',
            _charlimit=33,
            _tags=' t1,t2 ,  t3',
            custom='custom',
        )
        assert string.string == 'something'
        assert string.context == ['one', 'two', 'three']
        assert string.developer_comment == 'A crucial comment'
        assert string.character_limit == 33
        assert string.tags == ['t1', 't2', 't3']
        assert string.meta.get('custom') is None

    def test_tag_list(self):
        string = SourceString(
            'something',
            _tags=['t1', 't2', 't3'],
        )
        assert string.tags == ['t1', 't2', 't3']


class TestNative(object):
    """Tests the TxNative class."""

    def _get_tx(self, **kwargs):
        mytx = TxNative()
        mytx.init(['en', 'el'], 'cds_token', **kwargs)
        return mytx

    def test_uninitialized(self):
        mytx = TxNative()
        with pytest.raises(NotInitializedError):
            mytx.translate('string', 'en')
        with pytest.raises(NotInitializedError):
            mytx.fetch_translations()
        with pytest.raises(NotInitializedError):
            mytx.push_source_strings([], False)

    def test_default_init(self):
        mytx = self._get_tx()
        assert mytx.initialized is True
        assert mytx._languages == ['en', 'el']
        assert isinstance(mytx._missing_policy, SourceStringPolicy)
        assert isinstance(mytx._cache, MemoryCache)
        assert mytx._cds_handler.token == 'cds_token'
        assert mytx._cds_handler.host == TRANSIFEX_CDS_HOST

    def test_custom_init(self):
        missing_policy = PseudoTranslationPolicy()
        mytx = self._get_tx(cds_host='myhost', missing_policy=missing_policy)
        assert mytx.initialized is True
        assert mytx._languages == ['en', 'el']
        assert mytx._missing_policy == missing_policy
        assert isinstance(mytx._cache, MemoryCache)
        assert mytx._cds_handler.token == 'cds_token'
        assert mytx._cds_handler.host == 'myhost'

    @patch('transifex.native.core.StringRenderer.render')
    def test_translate_source_language_reaches_renderer(self, mock_render):
        mytx = self._get_tx()
        mytx.translate('My String', 'en', is_source=True)
        mock_render.assert_called_once_with(
            source_string='My String',
            string_to_render='My String',
            language_code='en',
            escape=True,
            missing_policy=mytx._missing_policy,
            params={},
        )

    @patch('transifex.native.core.MemoryCache.get')
    @patch('transifex.native.core.StringRenderer.render')
    def test_translate_target_language_missing_reaches_renderer(self, mock_render,
                                                                mock_cache):
        mock_cache.return_value = None
        mytx = self._get_tx()
        mytx.translate('My String', 'en', is_source=False)
        mock_cache.assert_called_once_with(
            generate_key(string='My String'), 'en')
        mock_render.assert_called_once_with(
            source_string='My String',
            string_to_render=None,
            language_code='en',
            escape=True,
            missing_policy=mytx._missing_policy,
            params={},
        )

    def test_translate_target_language_missing_reaches_missing_policy(self):
        missing_policy = MagicMock()
        mytx = self._get_tx(missing_policy=missing_policy)
        mytx.translate('My String', 'en', is_source=False)
        missing_policy.get.assert_called_once_with('My String')

    @patch('transifex.native.core.StringRenderer')
    def test_translate_error_reaches_error_policy(self, mock_renderer):
        error_policy = MagicMock()
        mock_renderer.render.side_effect = Exception
        mytx = self._get_tx(error_policy=error_policy)
        mytx.translate('My String', 'en', is_source=False)
        error_policy.get.assert_called_once_with(
            source_string='My String', translation=None, language_code='en',
            escape=True, params={},
        )

    def test_translate_error_reaches_source_string_error_policy(
        self
    ):
        # Trigger a random error in rendering to fallback to the
        # error policy, e.g. an error in missing_policy
        mock_missing_policy = MagicMock()
        mock_missing_policy.get.side_effect = Exception
        mytx = self._get_tx(missing_policy=mock_missing_policy)
        result = mytx.translate('My String', 'en', is_source=False)
        assert result == 'My String'

    @patch('transifex.native.core.StringRenderer')
    @patch('transifex.native.rendering.StringRenderer')
    def test_source_string_policy_custom_text(
        self, mock_renderer1, mock_renderer2
    ):
        error_policy_identifier = (
            'transifex.native.rendering.SourceStringErrorPolicy',
            {'default_text': 'my-default-text'}
        )
        error_policy = parse_error_policy(error_policy_identifier)

        mock_renderer1.render.side_effect = Exception
        mock_renderer2.render.side_effect = Exception
        mytx = self._get_tx(
            error_policy=error_policy
        )
        result = mytx.translate('My String', 'en', is_source=False)
        assert result == 'my-default-text'

    def test_translate_source_language_renders_icu(self):
        mytx = self._get_tx()
        translation = mytx.translate(
            u'{cnt, plural, one {{cnt} duck} other {{cnt} ducks}}',
            'en',
            is_source=True,
            params={'cnt': 1}
        )
        assert translation == '1 duck'

    @patch('transifex.native.core.MemoryCache.get')
    def test_translate_target_language_renders_icu(self, mock_cache):
        mock_cache.return_value = u'{cnt, plural, one {{cnt} παπί} other {{cnt} παπιά}}'
        mytx = self._get_tx()
        translation = mytx.translate(
            u'{cnt, plural, one {{cnt} duck} other {{cnt} ducks}}',
            'en',
            is_source=False,
            params={'cnt': 1}
        )
        assert translation == u'1 παπί'

    def test_translate_source_language_escape_html_true(self):
        mytx = self._get_tx()
        translation = mytx.translate(
            u'<script type="text/javascript">alert(1)</script>',
            'en',
            is_source=True,
            escape=True,
            params={'cnt': 1}
        )
        assert translation == (
            u'&lt;script type=&quot;text/javascript&quot;&gt;alert(1)&lt;/script&gt;'
        )

    def test_translate_source_language_escape_html_false(self):
        mytx = self._get_tx()
        translation = mytx.translate(
            u'<script type="text/javascript">alert(1)</script>',
            'en',
            is_source=True,
            escape=False,
            params={'cnt': 1}
        )
        assert translation == u'<script type="text/javascript">alert(1)</script>'

    def test_translate_source_language_returns_overridden_translation(self):
        """If there is a newer translation in the cache for the source language
        use that instead of the original source string.
        """
        # Populate the cache with two strings in the source language,
        # essentially providing custom translations for the source strings
        cache = MemoryCache()
        source_string1 = u'{cnt, plural, one {{cnt} duck} other {{cnt} ducks}}'
        updated_string1 = u'{???, plural, one {# goose} other {# geese}}'
        key1 = generate_key(source_string1)
        source_string2 = u'Hello {username}'
        updated_string2 = u'Hello to you, {username}!'
        key2 = generate_key(source_string2)
        data = {
            'en': (
                True, {
                    key1: {'string': updated_string1},
                    key2: {'string': updated_string2},
                }
            )
        }
        cache.update(data)

        # Make sure the updated translations are returned
        mytx = self._get_tx(cache=cache)
        translation = mytx.translate(
            source_string1,
            'en',
            is_source=True,
            params={'cnt': 1}
        )
        assert translation == u'1 goose'
        translation = mytx.translate(
            source_string1,
            'en',
            is_source=True,
            params={'cnt': 10}
        )
        assert translation == u'10 geese'
        translation = mytx.translate(
            source_string2,
            'en',
            is_source=True,
            params={'username': 'Jane'}
        )
        assert translation == u'Hello to you, Jane!'

    def test_translate_source_language_returns_original_string(self):
        """If there is no newer translation in the cache for the source language
        use the original source string.
        """
        source_string1 = u'{cnt, plural, one {{cnt} duck} other {{cnt} ducks}}'
        source_string2 = u'Hello {username}'

        # Make sure the updated translations are returned
        mytx = self._get_tx()
        translation = mytx.translate(
            source_string1,
            'en',
            is_source=True,
            params={'cnt': 1}
        )
        assert translation == u'1 duck'
        translation = mytx.translate(
            source_string1,
            'en',
            is_source=True,
            params={'cnt': 10}
        )
        assert translation == u'10 ducks'
        translation = mytx.translate(
            source_string2,
            'en',
            is_source=True,
            params={'username': 'Jane'}
        )
        assert translation == u'Hello Jane'

    def test_translate_with_custom_keys(self):
        # Populate the cache with two strings in the source language,
        # essentially providing custom translations for the source strings
        cache = MemoryCache()
        source_string1 = u'Table'
        source_string2 = u'Hello {username}'
        data = {
            'en': (
                True, {
                    'mykey_1': {'string': u'A table'},
                    'mykey_2': {'string': u'Hello {username}!'},
                }
            ),
            'el': (
                True, {
                    'mykey_1': {'string': u'Ένα τραπέζι'},
                    'mykey_2': {'string': u'Γεια σου, {username}!'},
                }
            )
        }
        cache.update(data)
        mytx = self._get_tx(cache=cache)

        translation = mytx.translate(
            source_string1,
            'en',
            is_source=True,
            _key='mykey_1',
        )
        assert translation == u'A table'
        translation = mytx.translate(
            source_string1,
            'el',
            _key='mykey_1',
        )
        assert translation == u'Ένα τραπέζι'

        translation = mytx.translate(
            source_string2,
            'en',
            is_source=True,
            params={'username': 'Jane'},
            _key='mykey_2',
        )
        assert translation == u'Hello Jane!'
        translation = mytx.translate(
            source_string2,
            'el',
            params={'username': 'Jane'},
            _key='mykey_2',
        )
        assert translation == u'Γεια σου, Jane!'

    @patch('transifex.native.core.CDSHandler.push_source_strings')
    def test_push_strings_reaches_cds_handler(self, mock_push_strings):
        response = MagicMock()
        response.status_code = 200
        response.content = '{}'
        mock_push_strings.return_value = response
        strings = [SourceString('a'), SourceString('b')]
        mytx = self._get_tx()
        mytx.push_source_strings(strings, False)
        mock_push_strings.assert_called_once_with(strings, False)

    @patch('transifex.native.core.MemoryCache.update')
    @patch('transifex.native.core.CDSHandler.fetch_translations')
    def test_fetch_translations_reaches_cds_handler_and_cache(self, mock_cds,
                                                              mock_cache):
        mytx = self._get_tx()
        mytx.fetch_translations()
        assert mock_cds.call_count == 1
        assert mock_cache.call_count > 0

    @patch('transifex.native.core.MemoryCache.get')
    def test_plural(self, cache_mock):
        cache_mock.return_value = u'{???, plural, one {ONE} other {OTHER}}'
        tx = self._get_tx()
        translation = tx.translate(u'{cnt, plural, one {one} other {other}}',
                                   u"fr_FR",
                                   params={'cnt': 1})
        assert translation == u'ONE'
        translation = tx.translate(u'{cnt, plural, one {one} other {other}}',
                                   u"fr_FR",
                                   params={'cnt': 2})
        assert translation == u'OTHER'
