from __future__ import absolute_import, unicode_literals

from transifex.api.jsonapi import JsonApi, Resource
from transifex.api.jsonapi.auth import ULFAuthentication

from .constants import host


class ATestApi(JsonApi):
    HOST = host


@ATestApi.register
class GlobalTest(Resource):
    TYPE = "globaltests"


test_api = ATestApi()


def reset_setup():
    test_api.setup(host=host, auth="test_api_key")
    assert (test_api.make_auth_headers() ==
            {'Authorization': "Bearer test_api_key"})
    assert test_api.host == host


def test_registries():
    assert issubclass(test_api.type_registry["globaltests"], GlobalTest)
    assert issubclass(test_api.globaltests, GlobalTest)
    assert issubclass(test_api.GlobalTest, GlobalTest)


def test_setup_plaintext():
    test_api.setup(host="http://some.host", auth="another_key")
    assert (test_api.make_auth_headers() ==
            {'Authorization': "Bearer another_key"})
    assert test_api.host == "http://some.host"
    reset_setup()


def test_setup_ulf():
    test_api.setup(auth=ULFAuthentication('public'))
    assert test_api.make_auth_headers() == {'Authorization': "ULF public"}

    test_api.setup(auth=ULFAuthentication('public', 'secret'))
    assert (test_api.make_auth_headers() ==
            {'Authorization': "ULF public:secret"})

    reset_setup()


def test_setup_any_callable():
    test_api.setup(host="http://some.host2",
                   auth=lambda: {'Authorization': "Another key2"})
    assert test_api.make_auth_headers() == {'Authorization': "Another key2"}
    assert test_api.host == "http://some.host2"
    reset_setup()
