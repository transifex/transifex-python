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
}

logger = logging.getLogger('transifex.native.cds')
logger.addHandler(logging.StreamHandler(sys.stderr))


# A mapping of meta keys
# (interface_key: cds_key)
# Only contains meta keys that are different between the two
MAPPING = {KEY_DEVELOPER_COMMENT: 'developer_comment',
           KEY_CHARACTER_LIMIT: 'character_limit',
           KEY_TAGS: 'tags',
           KEY_OCCURRENCES: 'occurrences'}


class CDSHandler(object):
    """Handles communication with the Content Delivery Service."""

    def __init__(self, **kwargs):
        self._host = TRANSIFEX_CDS_HOST
        self._token = None
        self._secret = None
        self._configured_language_codes = None
        self._etags = {}
        self.setup(**kwargs)

    def setup(self, host=None, token=None, secret=None):
        if host is not None:
            self._host = host
        if token is not None:
            self._token = token
        if secret is not None:
            self._secret = secret

    def fetch_languages(self):
        """ Fetch the languages defined in the CDS for the specific project.

            :return: a list of language information
            :rtype: dict
        """

        last_response_status = 202
        while last_response_status == 202:
            response = requests.get(self._host + "/languages",
                                    headers=self._get_headers())
            last_response_status = response.status_code
        response.raise_for_status()
        return response.json()['data']

    def fetch_translations(self, language_code):
        """ Fetch all translations for the given
            organization/project/(resource) associated with the current token.
            Returns a tuple of refresh flag and a dictionary of the fetched
            translations per language. Refresh flag is going to be true
            whenever fresh data has been acquired false otherwise.

            :return: a (refresh_flag, translations) tuple
            :rtype: tuple
        """

        try:
            last_response_status = 202
            while last_response_status == 202:
                response = requests.get(
                    "{}/content/{}".format(self._host, language_code),
                    headers=self._get_headers(
                        etag=self._etags.get(language_code)
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
                return False, {}
            else:
                self._etags[language_code] = response.headers.get('ETag', '')
                return (True,
                        {key: value['string']
                         for key, value in response.json()['data'].items()})

        except (KeyError, ValueError):
            # Compatibility with python2.7 where `JSONDecodeError` doesn't
            # exist
            logger.error('Error retrieving translations from CDS: '
                         'Malformed response')  # pragma no cover
            return False, {}
        except requests.ConnectionError:
            logger.error(
                'Error retrieving translations from CDS: ConnectionError')
            return False, {}
        except Exception as e:
            logger.error(
                'Error retrieving translations from CDS: UnknownError '
                '(`{}`)'.format(str(e))
            )  # pragma no cover
            return False, {}

    def push_source_strings(self, strings, purge=False):
        """ Push source strings to CDS.

            :param list(SourceString) strings: a list of `SourceString` objects
                holding source strings
            :param bool purge: True deletes destination source content not
                included in pushed content. False appends the pushed content to
                destination source content.
            :return: the HTTP response object
            :rtype: requests.Response
        """

        if not self._secret:
            raise Exception('You need to use `TRANSIFEX_SECRET` when pushing '
                            'source content')

        data = dict((self._serialize(string) for string in strings))
        response = requests.post(
            self._host + '/content',
            headers=self._get_headers(use_secret=True),
            json={'data': data, 'meta': {'purge': purge}}
        )
        response.raise_for_status()

        return response.json()

    def _serialize(self, source_string):
        """ Serialize the given source string to a format suitable for the CDS.

            :param transifex.native.parsing.SourceString source_string: the
                object to serialize
            :return: a tuple that contains ths string key and its data, as
                (key, data)
            :rtype: tuple
        """

        attrs = ('context', 'character_limit', 'developer_comment',
                 'occurrences', 'tags')
        meta = {attr: getattr(source_string, attr)
                for attr in attrs
                if getattr(source_string, attr) is not None}

        return (source_string.key,
                {'string': source_string.source_string, 'meta': meta})

    def _get_headers(self, use_secret=False, etag=None):
        """ Return the headers to use when making requests.

            :param bool use_secret: if True, the Bearer authorization header
                will also include the secret, otherwise it will only use the
                token
            :param str etag: an optional etag to include
            :return: a dictionary with all headers
            :rtype: dict
        """

        headers = {
            'Authorization': 'Bearer {token}{secret}'.format(
                token=self._token,
                secret=(':' + self._secret if use_secret else '')
            ),
            'Accept-Encoding': 'gzip',
        }
        if etag:
            headers['If-None-Match'] = etag

        return headers
