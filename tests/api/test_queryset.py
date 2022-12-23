from __future__ import absolute_import, unicode_literals

import responses
from transifex.api.jsonapi import JsonApi, Resource
from transifex.api.jsonapi.collections import Collection

from .constants import host
from .payloads import Payloads


class ATestApi(JsonApi):
    HOST = host


@ATestApi.register
class Item(Resource):
    TYPE = "items"


@ATestApi.register
class Tag(Resource):
    TYPE = "tags"


test_api = ATestApi(host=host, auth="test_api_key")


payloads = Payloads('items')


@responses.activate
def test_collection():
    responses.add(responses.GET, "{}/items".format(host),
                  json={'data': payloads[1:4]})

    collection = Collection(test_api, '/items')
    list(collection)

    assert len(collection) == 3
    assert isinstance(collection[0], Item)
    assert collection[1].id == "2"
    assert collection[2].name == "item 3"

    assert not collection.has_next()
    assert not collection.has_previous()

    assert list(collection) == list(collection.all())


def test_from_data():
    collection = Collection.from_data(test_api, {'data': payloads[1:4]})

    assert len(collection) == 3
    assert isinstance(collection[0], Item)
    assert collection[1].id == "2"
    assert collection[2].name == "item 3"

    assert not collection.has_next()
    assert not collection.has_previous()

    assert list(collection) == list(collection.all())


@responses.activate
def test_pagination():
    responses.add(responses.GET, "{}/items?page=2".format(host),
                  json={'data': payloads[4:7],
                        'links': {'previous': "/items?page=1"}})

    first_page = Collection.from_data(test_api,
                                      {'data': payloads[1:4],
                                       'links': {'next': "/items?page=2"}})
    assert first_page.has_next()
    second_page = first_page.next()
    list(second_page)

    assert len(responses.calls) == 1

    assert len(second_page) == 3
    assert isinstance(second_page[0], Item)
    assert second_page[1].id == "5"
    assert second_page[2].name == "item 6"

    assert not second_page.has_next()
    assert second_page.has_previous()

    assert list(first_page.all()) == list(first_page) + list(second_page)
    assert ([list(page) for page in first_page.all_pages()] ==
            [list(first_page), list(second_page)])


@responses.activate
def test_all():
    responses.add(responses.GET, "{}/items".format(host),
                  json={'data': payloads[1:4]})
    collection = test_api.Item.list()

    assert len(collection) == 3
    assert isinstance(collection[0], Item)
    assert collection[1].id == "2"
    assert collection[2].name == "item 3"

    assert not collection.has_next()
    assert not collection.has_previous()

    assert list(collection) == list(collection.all())


@responses.activate
def test_all_with_pagination():
    responses.add(responses.GET, "{}/items".format(host),
                  json={'data': payloads[1:4],
                        'links': {'next': "/items?page=2"}},
                  match_querystring=True)
    responses.add(responses.GET, "{}/items?page=2".format(host),
                  json={'data': payloads[4:7],
                        'links': {'previous': "/items?page=1"}},
                  match_querystring=True)

    first_page = test_api.Item.list()

    assert first_page.has_next()
    second_page = first_page.next()
    list(second_page)

    assert len(responses.calls) == 2

    assert len(second_page) == 3
    assert isinstance(second_page[0], Item)
    assert second_page[1].id == "5"
    assert second_page[2].name == "item 6"

    assert not second_page.has_next()
    assert second_page.has_previous()

    assert list(first_page.all()) == list(first_page) + list(second_page)
    assert ([list(page) for page in first_page.all_pages()] ==
            [list(first_page), list(second_page)])


@responses.activate
def test_filter():
    responses.add(responses.GET, "{}/items".format(host),
                  json={'data': payloads[1:5]}, match_querystring=True)
    responses.add(responses.GET, "{}/items?filter[odd]=1".format(host),
                  json={'data': payloads[1:5:2]}, match_querystring=True)

    all_items = test_api.Item.list()
    odd_items = test_api.Item.filter(odd=1)

    assert len(all_items) == 4
    assert len(odd_items) == 2

    assert list(odd_items) == [all_items[0], all_items[2]]

    assert (list(test_api.Item.filter(odd=1)) ==
            list(test_api.Item.list().filter(odd=1)) ==
            list(test_api.Item.filter(odd=2).filter(odd=1)))


@responses.activate
def test_include():
    responses.add(responses.GET, "{}/items".format(host), json={
        'data': [{'type': "items",
                  'id': "1",
                  'relationships': {'tag': {'data': {'type': "tags",
                                                     'id': "1"}}}},
                 {'type': "items",
                  'id': "2",
                  'relationships': {'tag': {'data': {'type': "tags",
                                                     'id': "2"}}}}],
        'included': [{'type': "tags",
                      'id': "1",
                      'attributes': {'name': "tag1"}},
                     {'type': "tags",
                      'id': "2",
                      'attributes': {'name': "tag2"}}],
    })

    item1, item2 = test_api.Item.list()
    assert item1.tag.name == "tag1"
    assert item2.tag.name == "tag2"


@responses.activate
def test_limit():
    responses.add(
        responses.GET,
        "{}/items".format(host),
        json={"data": payloads[1:5]},
        match_querystring=True,
    )
    responses.add(
        responses.GET,
        "{}/items?limit=2".format(host),
        json={"data": payloads[1:3]},
        match_querystring=True,
    )

    all_items = test_api.Item.list()
    limited_items = test_api.Item.limit(2)

    assert len(all_items) == 4
    assert len(limited_items) == 2

    assert list(limited_items) == all_items[:2]

    assert (
        list(test_api.Item.limit(2))
        == list(test_api.Item.list().limit(2))
        == list(test_api.Item.list().limit(5).limit(2))
    )
