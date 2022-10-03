from __future__ import absolute_import, unicode_literals

import responses
from transifex.api.jsonapi import JsonApi, Resource
from transifex.api.jsonapi.exceptions import JsonApiException

from .constants import host


class ATestApi(JsonApi):
    HOST = host


@ATestApi.register
class Foo(Resource):
    TYPE = "foos"


test_api = ATestApi(auth="test_api_key")


@responses.activate
def test_exception_during_create():
    responses.add(
        responses.POST,
        "{}/foos".format(host),
        json={
            "errors": [
                {
                    "status": "409",
                    "code": "conflict",
                    "title": "Conflict error",
                    "detail": "username 'Foo' is already taken",
                    "source": {"pointer": "/data/attributes/username"},
                }
            ]
        },
        status=409,
    )

    exc = None
    try:
        test_api.Foo.create(attributes={"username": "Foo"})
    except JsonApiException as e:
        exc = e

    assert exc.status_code == 409

    assert exc.errors[0]["status"] == "409"
    assert exc.errors[0]["code"] == "conflict"
    assert exc.errors[0]["title"] == "Conflict error"
    assert exc.errors[0]["detail"] == "username 'Foo' is already taken"
    assert exc.errors[0]["source"] == {"pointer": "/data/attributes/username"}

    assert exc.filter("409") == [exc.errors[0]]
    assert exc.filter("conflict") == [exc.errors[0]]
    assert exc.filter("400") == []


def test_exception_grouping():
    errors = [
        {"status": "400", "code": "bad_request", "detail": "error 1"},
        {"status": "400", "code": "bad_request", "detail": "error 2"},
        {"status": "401", "code": "unauthorized", "detail": "error 3"},
        {"status": "403", "code": "permission_denied", "detail": "error 4"},
    ]

    try:
        raise JsonApiException.new(400, errors, None)
    except JsonApiException.get("bad_request") as exc:
        assert exc.errors == errors
        assert exc.filter(400) == errors[:2]
        assert exc.filter("unauthorized") == [errors[2]]
        assert exc.filter(403) == [errors[3]]
        assert exc.exclude(400) == errors[2:]

    caught = False
    try:
        raise JsonApiException.new(400, errors, None)
    except JsonApiException.get(401, 404):
        caught = True

    assert caught

    caught = False
    try:
        raise JsonApiException.new(400, errors, None)
    except JsonApiException.get(404):
        caught = True
    except JsonApiException.get("not_found"):
        caught = True
    except Exception:
        pass
    assert not caught
