from __future__ import absolute_import, unicode_literals

import json
from copy import deepcopy

import responses
from transifex.api.jsonapi import JsonApi, Resource

from .constants import host


class ATestApi(JsonApi):
    HOST = host


@ATestApi.register
class Foo(Resource):
    TYPE = "foos"


test_api = ATestApi(host=host, auth="test_api_key")


SIMPLE_PAYLOAD = {'type': "foos", 'id': "1", 'attributes': {'hello': "world"}}


def make_simple_assertions(foo):
    assert isinstance(foo, Foo)
    assert foo.TYPE == "foos"
    assert foo.id == "1"
    assert foo.attributes == {'hello': "world"}
    assert foo.relationships == {}
    assert foo.related == {}
    assert foo.hello == "world"


def test_init():
    foo = test_api.Foo(id="1", attributes={'hello': "world"})
    make_simple_assertions(foo)
    foo = test_api.Foo({'data': SIMPLE_PAYLOAD})
    make_simple_assertions(foo)
    foo = test_api.Foo(SIMPLE_PAYLOAD)
    make_simple_assertions(foo)
    foo = test_api.Foo(id="1", hello="world")
    make_simple_assertions(foo)


def test_new():
    foo = test_api.new(type="foos", id="1", attributes={'hello': "world"})
    make_simple_assertions(foo)
    foo = test_api.new({'data': SIMPLE_PAYLOAD})
    make_simple_assertions(foo)
    foo = test_api.new(SIMPLE_PAYLOAD)
    make_simple_assertions(foo)
    foo = test_api.new(type="foos", id="1", hello="world")
    make_simple_assertions(foo)


def test_as_resource():
    foo = test_api.Foo(SIMPLE_PAYLOAD)
    assert (test_api.as_resource(foo).as_resource_identifier() ==
            {'type': "foos", 'id': "1"})
    assert (test_api.as_resource({'data': SIMPLE_PAYLOAD}).
            as_resource_identifier() == {'type': "foos", 'id': "1"})
    assert (test_api.as_resource(SIMPLE_PAYLOAD).
            as_resource_identifier() ==
            {'type': "foos", 'id': "1"})


def test_setattr():
    foo = test_api.Foo(SIMPLE_PAYLOAD)
    foo.hello = "WORLD"
    assert foo.hello == "WORLD"
    assert foo.attributes == {'hello': "WORLD"}


@responses.activate
def test_reload():
    foo = test_api.Foo(SIMPLE_PAYLOAD)

    new_payload = deepcopy(SIMPLE_PAYLOAD)
    new_payload['attributes']['hello'] = "WORLD"
    responses.add(responses.GET, "{}/foos/1".format(host),
                  json={'data': new_payload})

    foo.reload()
    assert foo.hello == "WORLD"
    assert foo.attributes == {'hello': "WORLD"}


@responses.activate
def test_get_one():
    responses.add(responses.GET, "{}/foos/1".format(host),
                  json={'data': SIMPLE_PAYLOAD})

    foo = test_api.Foo.get('1')

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call.request.headers['Content-Type'] == "application/vnd.api+json"
    assert call.request.headers['Authorization'] == "Bearer test_api_key"

    make_simple_assertions(foo)


@responses.activate
def test_get_one_with_filters():
    responses.add(responses.GET, "{}/foos?filter[hello]=world".format(host),
                  json={'data': [SIMPLE_PAYLOAD]}, match_querystring=True)

    foo = test_api.Foo.get(hello="world")

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call.request.headers['Content-Type'] == "application/vnd.api+json"
    assert call.request.headers['Authorization'] == "Bearer test_api_key"

    make_simple_assertions(foo)


@responses.activate
def test_get_one_with_include():
    responses.add(
        responses.GET,
        "{}/foos/1".format(host),
        json={'data': {'type': "foos",
                       'id': "1",
                       'attributes': {'name': "Foo1"},
                       'relationships': {'sibling': {'data': {'type': "foos",
                                                              'id': "2"}}}},
              'included': [{'type': "foos",
                            'id': "2",
                            'attributes': {'name': "Foo2"}}]},
    )

    foo = test_api.Foo.get('1', include=['sibling'])

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call.request.headers['Content-Type'] == "application/vnd.api+json"
    assert call.request.headers['Authorization'] == "Bearer test_api_key"

    assert isinstance(foo, Foo)
    assert foo.TYPE == "foos"
    assert foo.id == "1"
    assert foo.attributes == {'name': "Foo1"}
    assert foo.name == "Foo1"
    assert isinstance(foo.sibling, Foo)
    assert foo.sibling.TYPE == "foos"
    assert foo.sibling.id == "2"
    assert foo.sibling.attributes == {'name': "Foo2"}
    assert foo.sibling.name == "Foo2"


@responses.activate
def test_save_existing():
    foo = test_api.Foo(SIMPLE_PAYLOAD)

    new_payload = deepcopy(SIMPLE_PAYLOAD)
    new_payload['attributes']['hello'] = "WORLD"
    responses.add(responses.PATCH, "{}/foos/1".format(host),
                  json={'data': new_payload})

    foo.hello = "WORLD"
    foo.save()

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert json.loads(call.request.body.decode()) == {'data': new_payload}

    foo.hello = "something else"
    foo.save(hello="WORLD")

    assert len(responses.calls) == 2
    call = responses.calls[1]
    assert json.loads(call.request.body.decode()) == {'data': new_payload}


@responses.activate
def test_save_new():
    new_payload = deepcopy(SIMPLE_PAYLOAD)
    new_payload['attributes']['created'] = "NOW!!!"
    responses.add(responses.POST, "{}/foos".format(host),
                  json={'data': new_payload})

    foo = test_api.Foo(attributes={'hello': "world"})
    foo.save()

    assert foo.id == "1"
    assert foo.created == "NOW!!!"
    assert foo.attributes == {'hello': "world", 'created': "NOW!!!"}


@responses.activate
def test_create():
    new_payload = deepcopy(SIMPLE_PAYLOAD)
    new_payload['attributes']['created'] = "NOW!!!"
    responses.add(responses.POST, "{}/foos".format(host),
                  json={'data': new_payload})

    foo = test_api.Foo.create(attributes={'hello': "world"})

    assert foo.created == "NOW!!!"
    assert foo.attributes == {'hello': "world", 'created': "NOW!!!"}


@responses.activate
def test_create_with_id():
    new_payload = deepcopy(SIMPLE_PAYLOAD)
    new_payload['attributes']['created'] = "NOW!!!"
    responses.add(responses.POST, "{}/foos".format(host),
                  json={'data': new_payload})

    foo = test_api.Foo.create(id="2", attributes={'hello': "world"})

    assert len(responses.calls) == 1
    assert json.loads(responses.calls[0].request.body.decode()) == {'data': {
        'type': "foos",
        'id': "2",
        'attributes': {'hello': "world"},
    }}
    assert foo.created == "NOW!!!"
    assert foo.attributes == {'hello': "world", 'created': "NOW!!!"}
    assert foo.id == "1"


@responses.activate
def test_delete():
    responses.add(responses.DELETE, "{}/foos/1".format(host))

    foo = test_api.Foo(SIMPLE_PAYLOAD)
    foo.delete()

    assert len(responses.calls) == 1
    assert foo.id is None


def test_eq():
    foo = test_api.Foo(SIMPLE_PAYLOAD)
    assert foo == {'type': "foos", 'id': "1"}
    assert {'type': "foos", 'id': "1"} == foo
    assert foo == {'data': {'type': "foos", 'id': "1"}}
    assert {'data': {'type': "foos", 'id': "1"}} == foo
    assert foo == test_api.Foo(id="1")
    assert test_api.Foo(id="1") == foo


def test_as_resource_identifier():
    foo = test_api.Foo(SIMPLE_PAYLOAD)
    assert foo.as_resource_identifier() == {'type': "foos", 'id': "1"}


def test_as_relationship():
    foo = test_api.Foo(SIMPLE_PAYLOAD)
    assert foo.as_relationship() == {'data': {'type': "foos", 'id': "1"}}
