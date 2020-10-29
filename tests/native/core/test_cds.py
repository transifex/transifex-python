from operator import itemgetter

import pytest
import requests
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
    def test_fetch_languages_success(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token', host=cds_host)

        # correct response
        responses.add(responses.GET,
                      cds_host + '/languages',
                      json={"data": [{"code": "el"}, {"code": "en"}],
                            "meta": {"some_key": "some_value"}},
                      status=200)

        assert (sorted(cds_handler.fetch_languages(),
                       key=lambda l: l['code']) ==
                [{"code": "el"}, {"code": "en"}])

    @responses.activate
    def test_fetch_languages_error(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token', host=cds_host)

        responses.add(responses.GET, cds_host + '/languages', status=400)

        with pytest.raises(Exception):
            cds_handler.fetch_languages()

    @responses.activate
    def test_fetch_translations_success(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token', host=cds_host)

        # add response for translations
        responses.add(responses.GET,
                      cds_host + '/content/el',
                      json={'data': {'key1': {'string': 'key1_el'},
                                     'key2': {'string': 'key2_el'}},
                            'meta': {"some_key": "some_value"}},
                      status=200)

        assert (cds_handler.fetch_translations('el') ==
                (True, {'key1': 'key1_el', 'key2': 'key2_el'}))

        responses.add(responses.GET,
                      cds_host + '/content/en',
                      json={'data': {'key1': {'string': 'key1_en'},
                                     'key2': {'string': 'key2_en'}},
                            'meta': {}},
                      status=200)

        assert (cds_handler.fetch_translations('en') ==
                (True, {'key1': 'key1_en', 'key2': 'key2_en'}))

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_fetch_translations_not_found(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token', host=cds_host)

        # add response bad status response for a language here
        responses.add(responses.GET, cds_host + '/content/fr', status=404)

        assert cds_handler.fetch_translations('fr') == (False, {})

        responses.reset()

    @responses.activate
    @patch('transifex.native.cds.logger')
    def test_fetch_translations_etags_management(self, patched_logger):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token', host=cds_host)

        responses.add(responses.GET,
                      cds_host + '/content/el',
                      json={'data': {'key1': {'string': 'key1_el'},
                                     'key2': {'string': 'key2_el'}},
                            'meta': {"some_key": "some_value"}},
                      status=200,
                      headers={'ETag': 'some_unique_tag_is_here'})
        responses.add(responses.GET,
                      cds_host + '/content/en',
                      # whatever, we don't care about the content of json
                      # repsone atm.
                      json={},
                      status=304)

        assert (cds_handler.fetch_translations('el') ==
                (True, {'key1': "key1_el", 'key2': "key2_el"}))
        assert cds_handler.fetch_translations('en') == (False, {})
        assert cds_handler._etags.get('el') == 'some_unique_tag_is_here'

    def test_push_source_strings_no_secret(self):
        cds_handler = CDSHandler(token='some_token')
        with pytest.raises(Exception):
            cds_handler.push_source_strings([], False)

    @responses.activate
    def test_push_source_strings(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token',
                                 secret='some_secret',
                                 host=cds_host)

        # test push no content
        responses.add(responses.POST,
                      cds_host + '/content',
                      status=200, json={'data': {}})

        cds_handler.push_source_strings([], False)

        # test push with content
        responses.add(responses.POST,
                      cds_host + '/content',
                      status=200,
                      json={'data': {}})

        source_string = SourceString('some_string')
        cds_handler.push_source_strings([source_string], False)
        responses.reset()

        # test wrong data format
        responses.add(responses.POST, cds_host + '/content', status=422)
        # we don't care about the payload this time, just want to
        # see how the service handles the errors
        with pytest.raises(requests.exceptions.HTTPError):
            cds_handler.push_source_strings([], False)

    def test_get_headers(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token',
                                 secret='some_secret',
                                 host=cds_host)
        assert (cds_handler._get_headers() ==
                {'Authorization': 'Bearer some_token',
                 'Accept-Encoding': 'gzip'})

        assert (cds_handler._get_headers(use_secret=True) ==
                {'Authorization': 'Bearer some_token:some_secret',
                 'Accept-Encoding': 'gzip'})

        headers = cds_handler._get_headers(use_secret=True, etag='something')
        assert (headers ==
                {'Authorization': 'Bearer some_token:some_secret',
                 'Accept-Encoding': 'gzip', 'If-None-Match': 'something'})

    @responses.activate
    def test_retry_fetch_languages(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token',
                                 host=cds_host)
        responses.add(responses.GET, cds_host + '/languages', status=202)
        responses.add(responses.GET, cds_host + '/languages', status=202)
        responses.add(responses.GET,
                      cds_host + '/languages',
                      json={'data': [{'code': "el"}, {'code': "en"}],
                            'meta': {'some_key': "some_value"}},
                      status=200)
        languages_response = cds_handler.fetch_languages()
        assert self._lang_lists_equal(languages_response,
                                      [{'code': 'el'}, {'code': 'en'}])

    @responses.activate
    def test_retry_fetch_translations(self):
        cds_host = 'https://some.host'
        cds_handler = CDSHandler(token='some_token',
                                 host=cds_host)
        responses.add(responses.GET, cds_host + '/content/el', status=202)
        responses.add(responses.GET, cds_host + '/content/el', status=202)
        responses.add(responses.GET,
                      cds_host + '/content/el',
                      json={'data': {'source': {'string': "translation"}}},
                      status=200)
        assert (cds_handler.fetch_translations('el') ==
                (True, {'source': "translation"}))
