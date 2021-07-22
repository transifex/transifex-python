from __future__ import absolute_import, unicode_literals

import json
from copy import deepcopy

import responses
from transifex.api.jsonapi import JsonApi, Resource

from .constants import host
from .payloads import Payloads


class ATestApi(JsonApi):
    HOST = host


@ATestApi.register
class Child(Resource):
    TYPE = "children"


@ATestApi.register
class Parent(Resource):
    TYPE = "parents"


test_api = ATestApi(auth="test_api_key")


child_payloads = Payloads(
    'children', 'child',
    extra={'relationships': {
        'parent': {'data': {'type': "parents", 'id': "1"},
                   'links': {'self': "/children/1/relationships/parent",
                             'related': "/parents/1"}},
    }}
)
parent_payloads = Payloads(
    'parents',
    extra={'relationships': {
        'children': {'links': {'self': "/parents/1/relationships/children",
                               'related': "/parents/1/children"}},
    }}
)


@responses.activate
def test_initialization():
    responses.add(responses.GET, "{}/parents/1".format(host),
                  json={'data': {'type': "parents", 'id': "1"}})
    parents = [test_api.Parent.get('1'),
               test_api.Parent(id='1'),
               {'data': {'type': "parents", 'id': '1'}},
               {'type': "parents", 'id': '1'}]
    children = [test_api.Child(relationships={'parent': parent})
                for parent in parents]
    assert all((children[i] == children[i + 1]
                for i in range(len(children) - 1)))
    assert all((children[i].__dict__ == children[i + 1].__dict__
                for i in range(len(children) - 1)))
    assert all((children[i].parent.__dict__ == children[i + 1].parent.__dict__
                for i in range(len(children) - 1)))

    child = test_api.Child(relationships={'parent': None})
    assert child.relationships == child.related == {'parent': None}


@responses.activate
def test_singular_fetch():
    responses.add(responses.GET, "{}/parents/1".format(host),
                  json={'data': parent_payloads[1]})

    child = test_api.Child(child_payloads[1])

    assert (child.relationships ==
            {'parent': {'data': {'type': "parents", 'id': "1"},
                        'links': {'self': "/children/1/relationships/parent",
                                  'related': "/parents/1"}}})
    assert (child.related['parent'] ==
            child.parent ==
            test_api.Parent(id="1"))
    assert child.parent.attributes == child.parent.attributes == {}

    child.fetch('parent')

    assert len(responses.calls) == 1
    assert (child.related['parent'] ==
            child.parent ==
            test_api.Parent(id="1"))
    assert child.parent.attributes == {'name': "parent 1"}
    assert child.parent.name == "parent 1"


@responses.activate
def test_fetch_plural():
    responses.add(responses.GET, "{}/parents/1/children".format(host),
                  json={'data': child_payloads[1:4],
                        'links': {'next': "/parents/1/children?page=2"}},
                  match_querystring=True)
    responses.add(responses.GET, "{}/parents/1/children?page=2".format(host),
                  json={'data': child_payloads[4:7],
                        'links': {'previous': "/parents/1/children?page=1"}},
                  match_querystring=True)

    parent = test_api.Parent(parent_payloads[1])
    assert 'children' not in parent.related
    parent.fetch('children')
    list(parent.children)

    assert len(responses.calls) == 1
    assert 'children' in parent.related
    assert len(parent.children) == 3
    assert isinstance(parent.children[0], Child)
    assert parent.children[1].id == "2"
    assert parent.children[2].name == "child 3"

    assert parent.children.has_next()
    assert not parent.children.has_previous()
    assert len(list(parent.children.all())) == 6


@responses.activate
def test_change_parent_with_save():
    response_body = deepcopy(child_payloads[1])
    relationship = response_body['relationships']['parent']
    relationship['data']['id'] = 2
    relationship['links']['related'] = relationship['links']['related'].\
        replace('1', '2')

    responses.add(responses.PATCH, "{}/children/1".format(host),
                  json={'data': response_body})

    child = test_api.Child(child_payloads[1])
    child.parent = test_api.Parent(parent_payloads[2])

    assert child.relationships['parent']['data']['id'] == "2"
    assert child.related['parent'].id == child.parent.id == "2"

    child.save()

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert (json.loads(call.request.body.decode())['data']
            ['relationships']['parent']['data']['id'] ==
            "2")


@responses.activate
def test_change_parent_with_change():
    responses.add(responses.PATCH,
                  "{}/children/1/relationships/parent".format(host))

    child = test_api.Child(child_payloads[1])
    new_parent = test_api.Parent(id="2")
    child.change('parent', new_parent)

    assert child.relationships['parent']['data']['id'] == "2"
    assert child.parent.id == "2"
    assert child.parent == new_parent

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert (json.loads(call.request.body.decode()) ==
            new_parent.as_relationship())


@responses.activate
def test_add():
    responses.add(responses.POST,
                  "{}/parents/1/relationships/children".format(host))

    parent = test_api.Parent(parent_payloads[1])
    children = [test_api.Child(payload) for payload in child_payloads[1:4]]
    parent.add('children', [children[0],
                            children[1].as_relationship(),
                            children[2].as_resource_identifier()])

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert (json.loads(call.request.body.decode())['data'] ==
            [{'type': "children", 'id': str(i)} for i in range(1, 4)])
