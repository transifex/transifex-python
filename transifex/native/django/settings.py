from django.conf import settings

TRANSIFEX_TOKEN = getattr(settings, 'TRANSIFEX_TOKEN', '')
TRANSIFEX_SECRET = getattr(settings, 'TRANSIFEX_SECRET', '')
TRANSIFEX_CDS_HOST = getattr(settings, 'TRANSIFEX_CDS_HOST', None)
TRANSIFEX_MISSING_POLICY = getattr(settings, 'TRANSIFEX_MISSING_POLICY', None)
TRANSIFEX_ERROR_POLICY = getattr(settings, 'TRANSIFEX_ERROR_POLICY', None)
TRANSIFEX_CACHE = getattr(settings, 'TRANSIFEX_CACHE', None)
LANGUAGES = getattr(settings, 'LANGUAGES', [])
SKIP_TRANSLATIONS_SYNC = getattr(settings, 'SKIP_TRANSLATIONS_SYNC', False)
TRANSIFEX_SYNC_INTERVAL = getattr(settings,
                                  'TRANSIFEX_SYNC_INTERVAL',
                                  30*60)
