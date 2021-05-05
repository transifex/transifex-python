from operator import itemgetter

import pytest
import responses
from mock import patch
from transifex.native.cds import CDSHandler
from transifex.native.parsing import SourceString


class TestCDSHandler(object):

    def _lang_lists_equal(self, list_1, list_2):
        try:
            sorted_1, sorted_2 = [sorted(language, key=itemgetter('code'))
                                  for language in (list_1, list_2)]
            pairs = zip(sorted_1, sorted_2)
            difference = any(x != y for x, y in pairs)
        except Exception:
            difference = True
        return not difference

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_fetch_languages(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            host=cds_host
        )

        # correct response
        responses.add(
            responses.GET, cds_host + '/languages',
            json={
                "data": [
                    {
                        "code": "el",
                    },
                    {
                        "code": "en",
                    },
                ],
                "meta": {
                    "some_key": "some_value"
                }
            }, status=200
        )

        languages_response = cds_handler.fetch_languages()
        assert self._lang_lists_equal(
            languages_response,
            [{'code': 'el'}, {'code': 'en'}]
        )
        assert patched_logger.error.call_count == 0
        responses.reset()

        # wrong payload structure
        responses.add(
            responses.GET, cds_host + '/languages',
            json={
                "wrong_key": [
                    {
                        "code": "el",
                    },
                    {
                        "code": "en",
                    },
                ],
                "meta": {
                    "some_key": "some_value"
                }
            }, status=200
        )

        assert cds_handler.fetch_languages() == []
        patched_logger.error.assert_called_with(
            'Error retrieving languages from CDS: Malformed response'
        )
        responses.reset()

        # bad request
        responses.add(
            responses.GET, cds_host + '/languages',
            json={
                "data": [
                    {
                        "code": "el",
                    },
                    {
                        "code": "en",
                    },
                ],
                "meta": {
                    "some_key": "some_value"
                }
            }, status=400
        )

        assert cds_handler.fetch_languages() == []
        patched_logger.error.assert_called_with(
            'Error retrieving languages from CDS: UnknownError (`400 Client '
            'Error: Bad Request for url: https://some.host/languages`)'
        )
        responses.reset()

        # unauthorized
        responses.add(
            responses.GET, cds_host + '/languages',
            json={
                "data": [
                    {
                        "code": "el",
                    },
                    {
                        "code": "en",
                    },
                ],
                "meta": {
                    "some_key": "some_value"
                }
            }, status=403
        )

        assert cds_handler.fetch_languages() == []
        patched_logger.error.assert_called_with(
            'Error retrieving languages from CDS: UnknownError (`403 Client '
            'Error: Forbidden for url: https://some.host/languages`)'
        )
        responses.reset()

        # connection error
        assert cds_handler.fetch_languages() == []
        patched_logger.error.assert_called_with(
            'Error retrieving languages from CDS: ConnectionError'
        )
        responses.reset()

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_fetch_translations(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en', 'fr'],
            'some_token',
            host=cds_host
        )

        # add response for languages
        responses.add(
            responses.GET, cds_host + '/languages',
            json={
                "data": [
                    {
                        "code": "el",
                    },
                    {
                        "code": "en",
                    },
                    {
                        "code": "fr",
                    },
                ],
                "meta": {
                    "some_key": "some_value"
                }
            }, status=200
        )

        # add response for translations
        responses.add(
            responses.GET, cds_host + '/content/el',
            json={
                'data': {
                    'key1': {
                        'string': 'key1_el'
                    },
                    'key2': {
                        'string': 'key2_el'
                    },
                },
                'meta': {
                    "some_key": "some_value"
                }
            }, status=200
        )

        responses.add(
            responses.GET, cds_host + '/content/en',
            json={
                'data': {
                    'key1': {
                        'string': 'key1_en'
                    },
                    'key2': {
                        'string': 'key2_en'
                    },
                },
                'meta': {
                }
            }, status=200
        )

        # add response bad status response for a language here
        responses.add(
            responses.GET, cds_host + '/content/fr', status=404
        )

        resp = cds_handler.fetch_translations()
        assert resp == {
            'el': (True, {
                'key1': {
                    'string': 'key1_el'
                },
                'key2': {
                    'string': 'key2_el'
                },
            }),
            'en': (True, {
                'key1': {
                    'string': 'key1_en'
                },
                'key2': {
                    'string': 'key2_en'
                },
            }),
            'fr': (False, {})  # that is due to the error status in response
        }

        responses.reset()

        # test fetch_languages fails with connection error
        responses.add(responses.GET, cds_host + '/languages', status=500)
        resp = cds_handler.fetch_translations()
        assert resp == {}

        patched_logger.error.assert_called_with(
            'Error retrieving languages from CDS: UnknownError '
            '(`500 Server Error: Internal Server Error for url: '
            'https://some.host/languages`)'
        )
        responses.reset()
        patched_logger.reset_mock()

        # test language code
        responses.add(
            responses.GET, cds_host + '/content/el',
            json={
                'data': {
                    'key1': {
                        'string': 'key1_el'
                    },
                    'key2': {
                        'string': 'key2_el'
                    },
                },
                'meta': {
                    "some_key": "some_value"
                }
            }, status=200
        )

        resp = cds_handler.fetch_translations(language_code='el')
        assert resp == {
            'el': (True, {
                'key1': {
                    'string': 'key1_el'
                },
                'key2': {
                    'string': 'key2_el'
                },
            })
        }
        responses.reset()
        assert patched_logger.error.call_count == 0

        # test connection_error
        resp = cds_handler.fetch_translations(language_code='el')
        patched_logger.error.assert_called_with(
            'Error retrieving translations from CDS: ConnectionError'
        )
        assert resp == {'el': (False, {})}

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_fetch_translations_etags_management(self, patched_logger):

        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            host=cds_host
        )

        # add response for languages
        responses.add(
            responses.GET, cds_host + '/languages',
            json={
                "data": [
                    {
                        "code": "el",
                    },
                    {
                        "code": "en",
                    },
                ],
                "meta": {
                    "some_key": "some_value"
                }
            }, status=200
        )

        # add response for translations
        responses.add(
            responses.GET, cds_host + '/content/el',
            json={
                'data': {
                    'key1': {
                        'string': 'key1_el'
                    },
                    'key2': {
                        'string': 'key2_el'
                    },
                },
                'meta': {
                    "some_key": "some_value"
                }
            },
            status=200,
            headers={'ETag': 'some_unique_tag_is_here'}
        )

        responses.add(
            responses.GET, cds_host + '/content/en',
            # whatever, we don't care about the content of json repsone atm.
            json={},
            status=304
        )

        resp = cds_handler.fetch_translations()
        assert resp == {
            'el': (True, {
                'key1': {
                    'string': 'key1_el'
                },
                'key2': {
                    'string': 'key2_el'
                },
            }),
            'en': (False, {})
        }
        assert cds_handler.etags.get('el') == 'some_unique_tag_is_here'

    def test_push_source_strings_no_secret(self):
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
        )
        with pytest.raises(Exception):
            cds_handler.push_source_strings([], False)

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_push_source_strings(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            secret='some_secret',
            host=cds_host
        )

        # test push no correct
        responses.add(
            responses.POST, cds_host + '/content/',
            status=200, json={'data': []}
        )

        cds_handler.push_source_strings([], False)
        assert patched_logger.error.call_count == 0

        # test push with content
        responses.add(
            responses.POST, cds_host + '/content/',
            status=200, json={'data': []}
        )

        source_string = SourceString('some_string')
        cds_handler.push_source_strings([source_string], False)
        assert patched_logger.error.call_count == 0
        responses.reset()

        # test wrong data format
        responses.add(
            responses.POST, cds_host + '/content/',
            status=422, json={
                "status": 422,
                "message": "Invalid Payload",
                "details": [
                    {
                        "message": "\"string\" is required",
                        "path": [
                            "some_key1",
                            "string"
                        ],
                        "type": "any.required",
                        "context": {
                            "key": "string",
                            "label": "string"
                        }
                    }
                ]
            }
        )
        # we don't care about the payload this time, just want to
        # see how the service handles the errors
        cds_handler.push_source_strings([], False)
        # The actual error message differs between Python 2 and Python 3
        messages = [
            'Error pushing source strings to CDS: UnknownError '
            '(`422 Client Error: {err} for url: '
            'https://some.host/content/`)'.format(err=x)
            for x in ('Unprocessable Entity', 'None')
        ]
        assert patched_logger.error.call_args[0][0] in messages

    def test_get_headers(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            secret='some_secret',
            host=cds_host
        )
        assert cds_handler._get_headers() == {
            'Authorization': 'Bearer some_token',
            'Accept-Encoding': 'gzip',
            'X-NATIVE-SDK': 'python',
        }

        assert cds_handler._get_headers(use_secret=True) == {
            'Authorization': 'Bearer some_token:some_secret',
            'Accept-Encoding': 'gzip',
            'X-NATIVE-SDK': 'python',
        }

        headers = cds_handler._get_headers(
            use_secret=True, etag='something')
        assert headers == {
            'Authorization': 'Bearer some_token:some_secret',
            'Accept-Encoding': 'gzip',
            'X-NATIVE-SDK': 'python',
            'If-None-Match': 'something',
        }

    @responses.activate
    def test_retry_fetch_languages(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            host=cds_host,
        )
        responses.add(responses.GET, cds_host + '/languages', status=500)
        responses.add(responses.GET, cds_host + '/languages', status=202)
        responses.add(responses.GET, cds_host + '/languages',
                      json={'data': [{'code': "el"},
                                     {'code': "en"}],
                            'meta': {'some_key': "some_value"}},
                      status=200)
        languages_response = cds_handler.fetch_languages()
        assert self._lang_lists_equal(
            languages_response,
            [{'code': 'el'}, {'code': 'en'}]
        )

    @responses.activate
    def test_retry_fetch_translations(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            host=cds_host,
        )
        responses.add(responses.GET, cds_host + '/content/el', status=500)
        responses.add(responses.GET, cds_host + '/content/el', status=202)
        responses.add(responses.GET,
                      cds_host + '/content/el',
                      json={'data': {'source': {'string': "translation"}}},
                      status=200)
        translations = cds_handler.fetch_translations('el')
        assert (translations ==
                {'el': (True, {'source': {'string': "translation"}})})

    def test_invalidate_no_secret(self):
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
        )
        with pytest.raises(Exception):
            cds_handler.invalidate_cache(False)

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_invalidate(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en'],
            'some_token',
            secret='some_secret',
            host=cds_host
        )

        # test invalidate
        responses.add(
            responses.POST, cds_host + '/invalidate',
            status=200, json={'count': 5}
        )

        cds_handler.invalidate_cache(False)
        assert patched_logger.error.call_count == 0

        # test purge
        responses.add(
            responses.POST, cds_host + '/purge',
            status=200, json={'count': 5}
        )

        cds_handler.invalidate_cache(True)
        assert patched_logger.error.call_count == 0
        responses.reset()

        # test response error
        responses.add(
            responses.POST, cds_host + '/invalidate',
            status=422, json={
                "status": 422,
            }
        )
        # we don't care about the payload this time, just want to
        # see how the service handles the errors
        cds_handler.invalidate_cache(False)
        # The actual error message differs between Python 2 and Python 3
        messages = [
            'Error invalidating CDS: UnknownError '
            '(`422 Client Error: {err} for url: '
            'https://some.host/invalidate`)'.format(err=x)
            for x in ('Unprocessable Entity', 'None')
        ]
        assert patched_logger.error.call_args[0][0] in messages
