from __future__ import absolute_import, unicode_literals

import json

import responses
from transifex.api.jsonapi import JsonApi, Resource

from .constants import host
from .payloads import Payloads


class ATestApi(JsonApi):
    HOST = host


@ATestApi.register
class BulkItem(Resource):
    TYPE = "bulk_items"


test_api = ATestApi(host=host, auth="test_api_key")


payloads = Payloads('bulk_items')


@responses.activate
def test_bulk_delete():
    responses.add(responses.DELETE, "{}/bulk_items".format(host))

    items = [test_api.BulkItem(payload) for payload in payloads[1:6]]
    test_api.BulkItem.bulk_delete([items[0],
                                   items[1].as_resource_identifier(),
                                   items[2].as_relationship(),
                                   items[3].id])

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert (call.request.headers['Content-Type'] ==
            'application/vnd.api+json;profile="bulk"')
    assert (json.loads(call.request.body.decode())['data'] ==
            [{'type': "bulk_items", 'id': str(i)} for i in range(1, 5)])


@responses.activate
def test_bulk_create():
    response_payload = payloads[1:5]
    for item, when in zip(response_payload, range(1, 5)):
        item['attributes']['created'] = "now + {}".format(when)
    responses.add(responses.POST, "{}/bulk_items".format(host),
                  json={'data': response_payload})

    result = test_api.BulkItem.bulk_create([
        BulkItem(attributes={'name': "bulk_item 1"}),
        {'attributes': {'name': "bulk_item 2"}},
        ({'name': "bulk_item 3"}, None),
        {'name': "bulk_item 4"},
    ])

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert (call.request.headers['Content-Type'] ==
            'application/vnd.api+json;profile="bulk"')
    assert (json.loads(call.request.body.decode()) ==
            {'data': [{'type': "bulk_items",
                       'attributes': {'name': "bulk_item {}".format(i)}}
                      for i in range(1, 5)]})

    assert isinstance(result[0], BulkItem)
    assert result[1].id == "2"
    assert result[2] == test_api.BulkItem(id="3")

    for i in range(4):
        assert result[i].id == str(i + 1)
        assert (result[i].name ==
                result[i].attributes['name'] ==
                "bulk_item {}".format(i + 1))
        assert (result[i].created ==
                result[i].attributes['created'] ==
                "now + {}".format(i + 1))


@responses.activate
def test_bulk_update():
    response_payload = payloads[1:6]
    for item, when in zip(response_payload, range(1, 6)):
        item['attributes'].update({'last_update': "now + {}".format(when),
                                   'name': "modified name {}".format(when)})
    responses.add(responses.PATCH, "{}/bulk_items".format(host),
                  json={'data': response_payload})

    result = test_api.BulkItem.bulk_update([
        test_api.BulkItem(id="1", attributes={'name': "modified name 1"}),
        {'id': "2", 'attributes': {'name': "modified name 2"}},
        ("3", {'name': "modified name 3"}, None),
        ("4", {'name': "modified name 4"}),
        "5",
    ])

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert (call.request.headers['Content-Type'] ==
            'application/vnd.api+json;profile="bulk"')
    assert (json.loads(call.request.body.decode()) ==
            {'data': ([{'type': "bulk_items",
                        'id': str(i),
                        'attributes': {'name': "modified name {}".format(i)}}
                       for i in range(1, 5)] +
                      [{'type': "bulk_items", 'id': "5"}])})

    assert isinstance(result[0], BulkItem)
    assert result[1].id == "2"
    assert result[2] == test_api.BulkItem(id="3")
    assert result[3].name == "modified name 4"

    for i in range(5):
        assert result[i].id == str(i + 1)
        assert (result[i].name ==
                result[i].attributes['name'] ==
                "modified name {}".format(i + 1))
        assert (result[i].last_update ==
                result[i].attributes['last_update'] ==
                "now + {}".format(i + 1))
