from __future__ import absolute_import, unicode_literals

from copy import deepcopy

import responses
import transifex.jsonapi
from transifex.jsonapi.compat import abc

from .constants import host
from .payloads import Payloads

_api = transifex.jsonapi.JsonApi(host=host, auth="test_api_key")


@_api.register
class Child(transifex.jsonapi.Resource):
    TYPE = "children"


@_api.register
class Parent(transifex.jsonapi.Resource):
    TYPE = "parents"


child_payloads = Payloads('children', singular_type="child")


PAYLOAD = {'data': {
    'type': "parents",
    'id': "1",
    'attributes': {'name': "parent 1"},
    'relationships': {'children': {
        'data': [{'type': "children", 'id': "1"},
                 {'type': "children", 'id': "2"}],
        'links': {'related': "/parents/1/children"},
    }},
}}


def make_simple_assertions(parent):
    assert isinstance(parent.children, abc.Sequence)
    assert parent.children[0].id == "1"
    assert parent.children[1].id == "2"


def test_plural_list():
    parent = Parent(PAYLOAD)
    make_simple_assertions(parent)
    parent = Parent(PAYLOAD['data'])
    make_simple_assertions(parent)
    parent = Parent(**PAYLOAD['data'])
    make_simple_assertions(parent)


def test_included():
    payload = deepcopy(PAYLOAD)
    payload['included'] = child_payloads[1:3]
    parent = Parent(payload)
    make_simple_assertions(parent)

    assert parent.children[0].name == "child 1"
    assert parent.children[1].name == "child 2"


@responses.activate
def test_refetch():
    responses.add(responses.GET, "{}/parents/1/children".format(host),
                  json={'data': child_payloads[1:4]})

    parent = Parent(PAYLOAD)
    assert len(parent.children) == 2

    parent.fetch('children')
    assert len(parent.children) == 3
    assert ([child.name for child in parent.children] ==
            ["child {}".format(i) for i in range(1, 4)])


@responses.activate
def test_save_with_included():
    payload = deepcopy(PAYLOAD)
    payload['included'] = child_payloads[1:3]
    responses.add(responses.PATCH, "{}/parents/1".format(host), json=payload)
    parent = Parent(PAYLOAD)
    parent.save(name="parent 1")
    assert [child.name for child in parent.children] == ["child 1", "child 2"]
