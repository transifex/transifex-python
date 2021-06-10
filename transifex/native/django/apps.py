import logging
import os
import sys

from django.apps import AppConfig
from django.core.signals import request_finished
from django.utils.translation import to_locale
from transifex.native import init, tx
from transifex.native.daemon import daemon
from transifex.native.django import settings as native_settings
from transifex.native.settings import (parse_cache, parse_error_policy,
                                       parse_rendering_policy)

logger = logging.getLogger('transifex.native.django')
logger.addHandler(logging.StreamHandler(sys.stdout))


def _segments_match(segments_to_match, arguments):
    """
    Tries to find matching segments in the arguments of the command
    that started the app. Will be used to determine whether we want
    to fetch translations or not.

    :param list(str) segments_to_match: The segments that should be
    matched. Expects to match all segments and will match subsequences
    as well (e.g. `./manage.py` will match `manage.py`)
    :param list(str) arguments: The arguments of the command that started
    the app (probably `sys.argv`)
    :rtype bool: Whether segments match or not
    """

    segments_to_match = set(segments_to_match)
    for arg in arguments:
        for segment in list(segments_to_match):
            if segment in arg:
                segments_to_match.remove(segment)
                if not segments_to_match:
                    return True
    return not segments_to_match


class NativeConfig(AppConfig):

    name = "transifex.native.django"

    def ready(self):
        if not native_settings.TRANSIFEX_TOKEN:
            logger.warning(
                'Credentials for Transifex not found. Retrieving localized '
                'content will not be available; instead, source strings will'
                ' be displayed.'
            )
            fetch_translations = False
        else:
            # Start when forced
            if os.getenv('FORCE_TRANSLATIONS_SYNC', False) == 'true':
                fetch_translations = True
            elif native_settings.SKIP_TRANSLATIONS_SYNC:
                logger.info('Automatic translation syncing skipped')
                fetch_translations = False
            else:
                fetch_translations = any(
                    [
                        # Start for local development
                        _segments_match(['manage.py', 'runserver'], sys.argv),
                        # Start for gunicorn
                        _segments_match(['gunicorn'], sys.argv),
                    ]
                )

        # Convert from [(<lang_code>, <name>), ...]
        # to [<locale>, ...]
        # e.g. from [('en-us', 'English (USA)'), ('fr-fr', 'French (France)')]
        # to ['en_US', 'fr_FR']
        languages = [to_locale(item[0]) for item in native_settings.LANGUAGES]

        # Create lazily to avoid import issues
        # in Django settings files
        missing_policy = parse_rendering_policy(
            native_settings.TRANSIFEX_MISSING_POLICY
        )
        error_policy = parse_error_policy(
            native_settings.TRANSIFEX_ERROR_POLICY
        )
        cache = parse_cache(native_settings.TRANSIFEX_CACHE)
        init(
            native_settings.TRANSIFEX_TOKEN,
            languages,
            secret=native_settings.TRANSIFEX_SECRET,
            cds_host=native_settings.TRANSIFEX_CDS_HOST,
            missing_policy=missing_policy,
            error_policy=error_policy,
            cache=cache,
        )

        if fetch_translations:
            logger.info(
                'Fetching translations for languages: {}'.format(
                    ', '.join(languages)
                )
            )
            tx.fetch_translations()

            if native_settings.TRANSIFEX_SYNC_INTERVAL != 0:
                logger.info('Starting daemon for OTA translations update')
                sync_interval = (
                    native_settings.TRANSIFEX_SYNC_INTERVAL
                    or 30*60
                )
                daemon.start_daemon(interval=sync_interval)
                request_finished.connect(daemon.is_daemon_running)
            else:
                logger.info('Syncing daemon will not be started')
        else:
            logger.info(
                'Starting up without fetching translations or OTA updates'
            )
