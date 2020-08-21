from __future__ import absolute_import, unicode_literals

import transifex.jsonapi
from transifex.jsonapi.auth import ULFAuthentication

from .constants import host

_api = transifex.jsonapi.JsonApi()


def reset_setup():
    _api.setup(host, "test_api_key")
    assert _api.make_auth_headers() == {'Authorization': "Bearer test_api_key"}
    assert _api.host == host


@_api.register
class GlobalTest(transifex.jsonapi.Resource):
    TYPE = "globaltests"


def test_class_registry():
    assert _api.registry['globaltests'] is GlobalTest


def test_setup_plaintext():
    _api.setup("http://some.host", "another_key")
    assert _api.make_auth_headers() == {'Authorization': "Bearer another_key"}
    assert _api.host == "http://some.host"
    reset_setup()


def test_setup_ulf():
    _api.setup(host, ULFAuthentication('public'))
    assert _api.make_auth_headers() == {'Authorization': "ULF public"}

    _api.setup(host, ULFAuthentication('public', 'secret'))
    assert _api.make_auth_headers() == {'Authorization': "ULF public:secret"}

    reset_setup()


def test_setup_any_callable():
    _api.setup("http://some.host2", lambda: {'Authorization': "Another key2"})
    assert _api.make_auth_headers() == {'Authorization': "Another key2"}
    assert _api.host == "http://some.host2"
    reset_setup()
