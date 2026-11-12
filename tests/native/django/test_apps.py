from django.apps import apps
from mock import patch
from transifex.native.django import settings as native_settings
from transifex.native.django.apps import NativeConfig


def _native_config():
    return next(config for config in apps.get_app_configs()
                if isinstance(config, NativeConfig))


@patch.object(native_settings, 'TRANSIFEX_REQUEST_TIMEOUT', (1, 2))
@patch.object(native_settings, 'TRANSIFEX_FETCH_TIMEOUT', 7)
@patch('transifex.native.django.apps.init')
def test_ready_passes_timeout_settings(mock_init):
    _native_config().ready()

    kwargs = mock_init.call_args[1]
    assert kwargs['fetch_timeout'] == 7
    assert kwargs['request_timeout'] == (1, 2)
