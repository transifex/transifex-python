import logging
import sys

import requests
from transifex.native.consts import (KEY_CHARACTER_LIMIT,
                                     KEY_DEVELOPER_COMMENT, KEY_OCCURRENCES,
                                     KEY_TAGS)

TRANSIFEX_CDS_HOST = 'https://cds.svc.transifex.net'

TRANSIFEX_CDS_URLS = {
    'FETCH_AVAILABLE_LANGUAGES': '/languages',
    'FETCH_TRANSLATIONS_FOR_LANGUAGE': '/content/{language_code}',
    'PUSH_SOURCE_STRINGS': '/content/'
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

    def __init__(self, **kwargs):
        """Constructor.

        :param list configured_languages: a list of language codes for the
            configured languages in the application
        :param str token: the API token to use for connecting to the CDS
        :param str host: the host of the Content Delivery Service
        """
        self.configured_language_codes = None
        self.token = None
        self.secret = None
        self.host = TRANSIFEX_CDS_HOST
        self.etags = EtagStore()

        self.setup(**kwargs)

    def setup(self, configured_languages=None, token=None, secret=None,
              host=None):
        if configured_languages is not None:
            self.configured_language_codes = configured_languages
        if token is not None:
            self.token = token
        if secret is not None:
            self.secret = secret
        if host is not None:
            self.host = host

    def fetch_languages(self):
        """Fetch the languages defined in the CDS for the specific project.

        :return: a list of language information
        :rtype: dict
        """

        cds_url = TRANSIFEX_CDS_URLS['FETCH_AVAILABLE_LANGUAGES']
        languages = []

        try:
            last_response_status = 202
            while last_response_status == 202:
                response = requests.get(
                    self.host + cds_url,
                    headers=self._get_headers(),
                )
                last_response_status = response.status_code

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

    def fetch_translations(self, language_code):
        """Fetch all translations for the given organization/project/(resource)
        associated with the current token. Returns a tuple of refresh flag and
        a dictionary of the fetched translations per language.
        Refresh flag is going to be true whenever fresh data has been acquired
        false otherwise.

        :return: a dictionary of (refresh_flag, translations) tuples
        :rtype: dict
        """

        cds_url = TRANSIFEX_CDS_URLS['FETCH_TRANSLATIONS_FOR_LANGUAGE']

        translations = {}

        try:
            last_response_status = 202
            while last_response_status == 202:
                response = requests.get(
                    (self.host +
                     cds_url.format(language_code=language_code)),
                    headers=self._get_headers(
                        etag=self.etags.get(language_code)
                    )
                )
                last_response_status = response.status_code

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

    def push_source_strings(self, strings, purge=False):
        """Push source strings to CDS.

        :param list(SourceString) strings: a list of `SourceString` objects
            holding source strings
        :param bool purge: True deletes destination source content not included
            in pushed content. False appends the pushed content to destination
            source content.
        :return: the HTTP response object
        :rtype: requests.Response
        """
        if not self.secret:
            raise Exception('You need to use `TRANSIFEX_SECRET` when pushing '
                            'source content')

        cds_url = TRANSIFEX_CDS_URLS['PUSH_SOURCE_STRINGS']

        data = {k: v for k, v in [self._serialize(item) for item in strings]}
        try:
            response = requests.post(
                self.host + cds_url,
                headers=self._get_headers(use_secret=True),
                json={
                    'data': data,
                    'meta': {'purge': purge},
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
            'X-NATIVE-SDK': 'python',
        }
        if etag:
            headers['If-None-Match'] = etag

        return headers
