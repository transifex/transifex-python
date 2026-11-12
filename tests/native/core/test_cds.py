from operator import itemgetter

import pytest
import requests
import responses
from mock import patch, MagicMock
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
    def test_fetch_translations_filter_tags(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en', 'fr'],
            'some_token',
            host=cds_host,
            filter_tags='foo,bar',
        )

        # add response for translations
        responses.add(
            responses.GET, cds_host + '/content/el?filter[tags]=foo,bar',
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
            }),
        }

        responses.reset()

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_fetch_translations_filter_status(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(
            ['el', 'en', 'fr'],
            'some_token',
            host=cds_host,
            filter_status='reviewed',
        )

        # add response for translations
        responses.add(
            responses.GET, cds_host + '/content/el?filter[status]=reviewed',
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
            }),
        }

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

        # test push no content
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
            'Accept-Version': 'v2',
            'X-NATIVE-SDK': 'python',
        }

        assert cds_handler._get_headers(use_secret=True) == {
            'Authorization': 'Bearer some_token:some_secret',
            'Accept-Encoding': 'gzip',
            'Accept-Version': 'v2',
            'X-NATIVE-SDK': 'python',
        }

        headers = cds_handler._get_headers(
            use_secret=True, etag='something')
        assert headers == {
            'Authorization': 'Bearer some_token:some_secret',
            'Accept-Encoding': 'gzip',
            'Accept-Version': 'v2',
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
            status=200, json={'data': {'count': 5}}
        )

        cds_handler.invalidate_cache(False)
        assert patched_logger.error.call_count == 0

        # test purge
        responses.add(
            responses.POST, cds_host + '/purge',
            status=200, json={'data': {'count': 5}}
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

    @staticmethod
    def _json_response(status_code, payload=None):
        response = MagicMock()
        response.ok = status_code < 400
        response.status_code = status_code
        response.headers = {}
        response.json.return_value = payload
        return response

    @patch('transifex.native.cds.time.sleep')
    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_retry_get_request_raises_timeout_on_202_at_deadline(
        self, mock_get, mock_time, mock_sleep
    ):
        cds_handler = CDSHandler(['el'], 'some_token', fetch_timeout=5)
        mock_get.return_value = self._json_response(202)
        # deadline 0 -> 5; requests at 0.1 and 2.2; after the second 202
        # the 2s retry delay would pass the deadline
        mock_time.side_effect = [0, 0.1, 0.1, 2.2, 3.5]

        with pytest.raises(requests.Timeout):
            cds_handler.retry_get_request('https://some.host/languages')

        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1

    @patch('transifex.native.cds.time.sleep')
    @patch('transifex.native.cds.requests.get')
    def test_retry_get_request_returns_unexpected_status(
        self, mock_get, mock_sleep
    ):
        cds_handler = CDSHandler(['el'], 'some_token')
        response = self._json_response(600)
        mock_get.return_value = response

        assert cds_handler.retry_get_request('https://some.host/x') is response
        assert mock_get.call_count == 1
        mock_sleep.assert_not_called()

    @patch('transifex.native.cds.logger')
    @patch('transifex.native.cds.time.sleep')
    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_fetch_translations_202_at_deadline_is_a_timeout(
        self, mock_get, mock_time, mock_sleep, patched_logger
    ):
        cds_handler = CDSHandler(['el'], 'some_token', fetch_timeout=1)
        cds_handler.etags.set('el', 'old-etag')
        mock_get.return_value = self._json_response(202, {'data': {}})
        # deadline 0 -> 1; checked at 0.1, request at 0.2, 202 at 0.3 leaves
        # less than the 2s retry delay
        mock_time.side_effect = [0, 0.1, 0.2, 0.3]

        translations = cds_handler.fetch_translations(language_code='el')

        assert translations == {'el': (False, {})}
        assert cds_handler.etags.get('el') == 'old-etag'
        patched_logger.error.assert_called_once_with(
            'Error retrieving translations from CDS: Timeout')

    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_request_timeout_is_capped_by_deadline(self, mock_get, mock_time):
        mock_get.return_value = self._json_response(200, {'data': []})
        mock_time.side_effect = [0, 3]

        CDSHandler(['el'], 'some_token', fetch_timeout=5).fetch_languages()

        assert mock_get.call_args[1]['timeout'] == (2, 2)

    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_no_request_once_deadline_has_passed(self, mock_get, mock_time):
        mock_time.side_effect = [0, 6]
        cds_handler = CDSHandler(['el'], 'some_token', fetch_timeout=5)

        with pytest.raises(requests.Timeout):
            cds_handler.retry_get_request('https://some.host/languages')
        mock_get.assert_not_called()

    @patch('transifex.native.cds.logger')
    def test_invalid_fetch_timeout_disables_it(self, patched_logger):
        for value, expected in ((None, 0), ('30', 30), (2, 2), ('abc', 0)):
            cds_handler = CDSHandler(['el'], 'some_token', fetch_timeout=value)
            assert cds_handler.fetch_timeout == expected
        patched_logger.error.assert_called_once_with(
            'Invalid fetch_timeout `abc`, fetch timeout disabled')

    @patch('transifex.native.cds.requests.get')
    def test_fetch_requests_use_request_timeout(self, mock_get):
        mock_get.return_value = self._json_response(200, {'data': []})

        for request_timeout, expected in (
            (None, (10, 60)),
            ((3, 7), (3, 7)),
            (5, 5),
        ):
            mock_get.reset_mock()
            kwargs = {} if request_timeout is None else {
                'request_timeout': request_timeout}
            cds_handler = CDSHandler(['el'], 'some_token', **kwargs)

            cds_handler.fetch_languages()
            cds_handler.fetch_translations(language_code='el')

            timeouts = [c[1]['timeout'] for c in mock_get.call_args_list]
            assert timeouts == [expected, expected]

    @patch('transifex.native.cds.logger')
    @patch('transifex.native.cds.requests.get')
    def test_fetch_logs_request_timeouts(self, mock_get, patched_logger):
        cds_handler = CDSHandler(['el'], 'some_token')

        for exception in (requests.ReadTimeout(), requests.ConnectTimeout()):
            mock_get.side_effect = exception
            patched_logger.reset_mock()

            assert cds_handler.fetch_languages() == []
            assert cds_handler.fetch_translations(language_code='el') == {
                'el': (False, {})
            }
            assert [c[0][0] for c in patched_logger.error.call_args_list] == [
                'Error retrieving languages from CDS: Timeout',
                'Error retrieving translations from CDS: Timeout',
            ]

    @patch('transifex.native.cds.logger')
    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_fetch_timeout_bounds_whole_fetch(
        self, mock_get, mock_time, patched_logger
    ):
        cds_handler = CDSHandler(['el', 'en'], 'some_token', fetch_timeout=5)
        mock_get.side_effect = [
            self._json_response(200, {'data': [{'code': 'el'},
                                               {'code': 'en'}]}),
            self._json_response(200, {'data': {'key': {'string': 'x'}}}),
        ]
        # deadline 0 -> 5; languages request at 0.5, first language checked
        # and requested at 1, second language checked at 10
        mock_time.side_effect = [0, 0.5, 1, 1, 10]

        translations = cds_handler.fetch_translations()

        assert mock_get.call_count == 2
        assert sorted(translations.values(), key=lambda v: v[0]) == [
            (False, {}),
            (True, {'key': {'string': 'x'}}),
        ]
        skipped = [lang for lang, (refresh, _) in translations.items()
                   if not refresh]
        patched_logger.error.assert_called_once_with(
            'Error retrieving translations from CDS: fetch timeout reached, '
            'skipped `{}`'.format(skipped[0])
        )

    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_number_request_timeout_is_capped_by_deadline(
        self, mock_get, mock_time
    ):
        mock_get.return_value = self._json_response(200, {'data': []})
        mock_time.side_effect = [0, 3]
        cds_handler = CDSHandler(['el'], 'some_token', fetch_timeout=5,
                                 request_timeout=30)

        cds_handler.fetch_languages()

        assert mock_get.call_args[1]['timeout'] == 2

    @patch('transifex.native.cds.time.sleep')
    @patch('transifex.native.cds.time.monotonic')
    @patch('transifex.native.cds.requests.get')
    def test_retry_get_request_returns_5xx_at_deadline(
        self, mock_get, mock_time, mock_sleep
    ):
        response = self._json_response(503)
        mock_get.return_value = response
        # deadline 0 -> 1; request at 0.1, 503 at 0.2 leaves less than 2s
        mock_time.side_effect = [0, 0.1, 0.2]
        cds_handler = CDSHandler(['el'], 'some_token', fetch_timeout=1)

        assert cds_handler.retry_get_request('https://some.host/x') is response
        assert mock_get.call_count == 1
        mock_sleep.assert_not_called()
