import logging
import sys
import time
from urllib.parse import urlencode

import requests
from transifex.native.consts import (KEY_CHARACTER_LIMIT,
                                     KEY_DEVELOPER_COMMENT, KEY_OCCURRENCES,
                                     KEY_TAGS)

TRANSIFEX_CDS_HOST = 'https://cds.svc.transifex.net'

TRANSIFEX_CDS_URLS = {
    'FETCH_AVAILABLE_LANGUAGES': '/languages',
    'FETCH_TRANSLATIONS_FOR_LANGUAGE': '/content/{language_code}',
    'PUSH_SOURCE_STRINGS': '/content/',
    'INVALIDATE_CACHE': '/invalidate',
    'PURGE_CACHE': '/purge',
}

logger = logging.getLogger('transifex.native.cds')
logger.addHandler(logging.StreamHandler(sys.stderr))


# A mapping of meta keys
# (interface_key: cds_key)
# Only contains meta keys that are different between the two
MAPPING = {
    KEY_DEVELOPER_COMMENT: 'developer_comment',
    KEY_CHARACTER_LIMIT: 'character_limit',
    KEY_TAGS: 'tags',
    KEY_OCCURRENCES: 'occurrences',
}

# Number of times to retry connecting to CDS before bailing out
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2


class EtagStore(object):
    """ Manges etags """

    # Probably we need to a duration policy here

    def __init__(self):
        self._mem = {}

    def set(self, key, value):
        self._mem[key] = value

    def get(self, key):
        return self._mem.get(key, '')


class CDSHandler(object):
    """Handles communication with the Content Delivery Service."""

    def __init__(self, configured_languages, token, secret=None,
                 host=TRANSIFEX_CDS_HOST, fetch_all_langs=False,
                 filter_tags=None, filter_status=None):
        """Constructor.

        :param list configured_languages: a list of language codes for the
            configured languages in the application
        :param str token: the API token to use for connecting to the CDS
        :param str host: the host of the Content Delivery Service
        """
        self.configured_language_codes = configured_languages
        self.fetch_all_langs = fetch_all_langs
        self.filter_tags = filter_tags
        self.filter_status = filter_status
        self.token = token
        self.secret = secret
        self.host = host or TRANSIFEX_CDS_HOST
        self.etags = EtagStore()

    def fetch_languages(self):
        """Fetch the languages defined in the CDS for the specific project.

        Contains the source language and all target languages.

        :return: a list of language information
        :rtype: dict
        """

        cds_url = TRANSIFEX_CDS_URLS['FETCH_AVAILABLE_LANGUAGES']
        languages = []

        try:
            response = self.retry_get_request(
                self.host + cds_url,
                headers=self._get_headers(),
            )

            if not response.ok:
                logger.error(
                    'Error retrieving languages from CDS: `{}`'.format(
                        response.reason
                    )
                )
                response.raise_for_status()

            json_content = response.json()
            languages = json_content['data']

        except (KeyError, ValueError):
            # Compatibility with python2.7 where `JSONDecodeError` doesn't
            # exist
            logger.error(
                'Error retrieving languages from CDS: Malformed response')
        except requests.ConnectionError:
            logger.error(
                'Error retrieving languages from CDS: ConnectionError')
        except Exception as e:
            logger.error('Error retrieving languages from CDS: UnknownError '
                         '(`{}`)'.format(str(e)))

        return languages

    def fetch_translations(self, language_code=None):
        """Fetch all translations for the given organization/project/(resource)
        associated with the current token.

        Returns a tuple of refresh flag and a dictionary of the fetched
        translations per language. Refresh flag is going to be True whenever
        fresh data has been acquired, False otherwise.

        :return: a dictionary of (refresh_flag, translations) tuples
        :rtype: dict
        """

        cds_url = TRANSIFEX_CDS_URLS['FETCH_TRANSLATIONS_FOR_LANGUAGE']

        # Append filters
        query_params = {}
        if self.filter_tags:
            query_params["filter[tags]"] = self.filter_tags
        if self.filter_status:
            query_params["filter[status]"] = self.filter_status
        if query_params:
            cds_url = cds_url + '?' + urlencode(query_params)

        translations = {}

        if not language_code:
            languages = [lang['code'] for lang in self.fetch_languages()]
        else:
            languages = [language_code]

        # All remote languages
        languages = set(languages)

        # Scope down to only languages appearing in LANGUAGES setting
        if not self.fetch_all_langs:
            languages &= set(self.configured_language_codes)

        for language_code in languages:

            try:
                response = self.retry_get_request(
                    (self.host + cds_url.format(language_code=language_code)),
                    headers=self._get_headers(
                        etag=self.etags.get(language_code)
                    )
                )

                if not response.ok:
                    logger.error(
                        'Error retrieving translations from CDS: `{}`'.format(
                            response.reason
                        )
                    )
                    response.raise_for_status()

                # etags indicate that no translation have been updated
                if response.status_code == 304:
                    translations[language_code] = (False, {})
                else:
                    self.etags.set(
                        language_code, response.headers.get('ETag', ''))
                    json_content = response.json()
                    translations[language_code] = (
                        True, json_content['data']
                    )

            except (KeyError, ValueError):
                # Compatibility with python2.7 where `JSONDecodeError` doesn't
                # exist
                logger.error('Error retrieving translations from CDS: '
                             'Malformed response')  # pragma no cover
                translations[language_code] = (False, {})  # pragma no cover
            except requests.ConnectionError:
                logger.error(
                    'Error retrieving translations from CDS: ConnectionError')
                translations[language_code] = (False, {})
            except Exception as e:
                logger.error(
                    'Error retrieving translations from CDS: UnknownError '
                    '(`{}`)'.format(str(e))
                )  # pragma no cover
                translations[language_code] = (False, {})

        return translations

    def push_source_strings(self, strings, purge=False,
                            do_not_keep_translations=False,
                            override_tags=False,
                            override_occurrences=False):
        """Push source strings to CDS.

        :param list(SourceString) strings: a list of `SourceString` objects
            holding source strings
        :param bool purge: True deletes destination source content not included
            in pushed content. False appends the pushed content to destination
            source content.
        :param bool do_not_keep_translations: True deletes translations when the
            source strings of existing keys are updated. False preserves them.
        :param bool override_tags: True replaces all the tags of pushed strings.
            False appends them to existing tags.
        :param bool override_occurrences: True replaces all the occurrences of pushed strings.
            False appends them to existing occurrences.
        :return: the HTTP response object
        :rtype: requests.Response
        """
        if not self.secret:
            raise Exception('You need to use `TRANSIFEX_SECRET` when pushing '
                            'source content')

        cds_url = TRANSIFEX_CDS_URLS['PUSH_SOURCE_STRINGS']

        data = {k: v for k, v in [self._serialize(item) for item in strings]}
        response = None

        try:
            response = requests.post(
                self.host + cds_url,
                headers=self._get_headers(use_secret=True),
                json={
                    'data': data,
                    'meta': {
                        'purge': purge,
                        'keep_translations': not do_not_keep_translations,
                        'override_tags': override_tags,
                        'override_occurrences': override_occurrences,
                    },
                }
            )
            response.raise_for_status()

        except requests.ConnectionError:
            logger.error(
                'Error pushing source strings to CDS: ConnectionError')
        except Exception as e:
            logger.error('Error pushing source strings to CDS: UnknownError '
                         '(`{}`)'.format(str(e)))

        return response

    def get_push_status(self, job_path):
        """Get source string push job status

        :param str job_path: Job url path
        :return: the HTTP response object
        :rtype: requests.Response
        """
        if not self.secret:
            raise Exception('You need to use `TRANSIFEX_SECRET` when polling '
                            'source content push')

        response = None
        try:
            response = requests.get(
                self.host + job_path,
                headers=self._get_headers(use_secret=True),
            )
            response.raise_for_status()

        except requests.ConnectionError:
            logger.error(
                'Error polling source strings push to CDS: ConnectionError')
        except Exception as e:
            logger.error(
                'Error polling source strings push to CDS: UnknownError '
                '(`{}`)'.format(str(e)))

        return response

    def invalidate_cache(self, purge=False):
        """Invalidate CDS cache.

        :param bool purge: True deletes CDS cache entirely instead of
            triggering a job to re-cache content.
        :return: the HTTP response object
        :rtype: requests.Response
        """
        if not self.secret:
            raise Exception('You need to use `TRANSIFEX_SECRET` when '
                            'invalidating cache')

        cds_url = TRANSIFEX_CDS_URLS['PURGE_CACHE'] if purge else \
            TRANSIFEX_CDS_URLS['INVALIDATE_CACHE']

        response = None
        try:
            response = requests.post(
                self.host + cds_url,
                headers=self._get_headers(use_secret=True),
                json={}
            )
            response.raise_for_status()

        except requests.ConnectionError:
            logger.error(
                'Error invalidating CDS: ConnectionError')
        except Exception as e:
            logger.error('Error invalidating CDS: UnknownError '
                         '(`{}`)'.format(str(e)))

        return response

    def _serialize(self, source_string):
        """Serialize the given source string to a format suitable for the CDS.

        :param transifex.native.parsing.SourceString source_string: the object
            to serialize
        :return: a tuple that contains ths string key and its data,
            as (key, data)
        :rtype: tuple
        """
        data = {
            'string': source_string.string,
            'meta': {
                MAPPING.get(k, k): v
                for k, v in source_string.meta.items()
            },
        }
        if source_string.context:
            data['meta']['context'] = source_string.context

        return source_string.key, data

    def _get_headers(self, use_secret=False, etag=None):
        """Return the headers to use when making requests.

        :param bool use_secret: if True, the Bearer authorization header
            will also include the secret, otherwise it will only use the token
        :param str etag: an optional etag to include
        :return: a dictionary with all headers
        :rtype: dict
        """
        headers = {
            'Authorization': 'Bearer {token}{secret}'.format(
                token=self.token,
                secret=(':' + self.secret if use_secret else '')
            ),
            'Accept-Encoding': 'gzip',
            'Accept-Version': 'v2',
            'X-NATIVE-SDK': 'python',
        }
        if etag:
            headers['If-None-Match'] = etag

        return headers

    def retry_get_request(self, *args, **kwargs):
        """ Resilient function for GET requests """
        retries, last_response_status = 0, 202
        while (last_response_status == 202 or
                500 <= last_response_status < 600 and
                retries < MAX_RETRIES):

            if 500 <= last_response_status < 600:
                retries += 1
                time.sleep(retries * RETRY_DELAY_SEC)

            response = requests.get(*args, **kwargs)
            last_response_status = response.status_code

        return response
