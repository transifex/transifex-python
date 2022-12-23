from __future__ import absolute_import, unicode_literals

from copy import deepcopy

import requests

from .collections import Collection
from .utils import (
    has_data,
    has_links,
    is_collection,
    is_dict,
    is_fetched,
    is_list,
    is_null,
    is_related,
    is_related_list,
    is_resource,
    is_resource_identifier,
)


class Resource(object):
    """Subclass like this:

        >>> class Foo(jsonapi.Resource):
        ...     TYPE = "foos"
        ...     EDITABLE = ['name', 'age', 'parent']

    EDITABLE values can either be names of attributes or relationships.
    """

    TYPE = None
    EDITABLE = None

    # Creation
    def __init__(self, data=None, **kwargs):
        """Initialize an API resource instance when you know the type."""

        if "type" in kwargs and kwargs["type"] != self.TYPE:
            raise ValueError("Invalid type")

        if data is not None:
            # Maybe a HTTP response body was passed:
            # - Parent(requests.get('http://api.com/parents/1').json())
            # - Parent(requests.get('http://api.com/parents/1').json()['data'])
            # Or a relationship:
            # - `Parent(user.relationships['parent'])`
            # - `Parent({'data': {'type': "parents", 'id': "1"}})`
            if "data" in data:
                included = data.get("included")
                data = data["data"]
                if included is not None and "included" not in data:
                    data["included"] = included
            self._overwrite(**data)
        else:
            self._overwrite(**kwargs)

    def _overwrite(
        self,
        # Copied from response to the instance
        id=None,
        attributes=None,
        relationships=None,
        links=None,
        # Used to overwrite 'related'
        included=None,
        # Used in case of redirect responses
        redirect=None,
        # Ignored
        type=None,
        # Magic
        **kwargs
    ):
        """Write to the basic attributes of Resource. Used by '__init__',
        'reload', '__copy__' and 'save'
        """

        # Handle "magic" kwargs
        if attributes is None:
            attributes = {}
        if relationships is None:
            relationships = {}
        for key, value in kwargs.items():
            if is_related(value) or is_related_list(value):
                relationships[key] = value
            else:
                attributes[key] = value

        # Copy from response
        self.id = id

        self.attributes = deepcopy(attributes)

        if links is not None:
            self.links = deepcopy(links)
        else:
            self.links = {}

        self.redirect = redirect

        # Relationships
        self.relationships, self.related = {}, {}
        for key, value in relationships.items():
            self._set_relationship(key, value)
            relationship = self.relationships[key]
            if is_null(relationship) or has_data(relationship):
                self.set_related(key, value)

        if included is not None:
            included = {(item["type"], item["id"]): item for item in included}
            for relationship_name, relationship in self.relationships.items():
                if is_null(relationship) or not has_data(relationship):
                    continue
                if is_list(relationship["data"]):  # Plural with data
                    new_items = [
                        included.get(
                            (r["type"], r["id"]), self.related[relationship_name][i]
                        )
                        for i, r in enumerate(relationship["data"])
                    ]
                    self.set_related(relationship_name, new_items)
                else:  # Singular
                    key = (relationship["data"]["type"], relationship["data"]["id"])
                    if key in included:
                        self.set_related(relationship_name, included[key])

    def _set_relationship(self, key, value):
        """Set 'value' as 'key' relationship. For value we accept:

        - A Resource object
        - A relationship (a dict with either 'data', 'links' or both)
        - A resource identifier (a dict with 'type' and 'id')
        - A list of a combination of the above
        - A dict with a 'data' field which is a list of a combination of
          the above
        - None

        Regardless, in the end `self.relationships` will resemble an API
        response's relationships.
        """

        if is_related_list(value):
            if has_data(value):
                data = value["data"]
            else:
                data = value
            self.relationships[key] = {
                "data": [
                    self.API.as_resource(item).as_resource_identifier() for item in data
                ]
            }
            if has_links(value):
                self.relationships[key]["links"] = value["links"]
        elif is_resource(value):
            self.relationships[key] = value.as_relationship()
        else:
            value = deepcopy(value)
            if not is_null(value) and is_resource_identifier(value):
                value = {"data": value}
            if is_null(value) or has_data(value) or has_links(value):
                self.relationships[key] = value
            else:
                raise ValueError(
                    "Invalid type '{}' for relationship '{}'".format(value, key)
                )

    def set_related(self, key, value):
        """Set 'value' as 'key' relationship's value. Works only with singular
        relationships. For value we accept:

        - A Resource object
        - A JSON representation of a Resource object
        - A full API response of a Resource object
        - A relationship (a dict with a 'data' field)
        - A resource identifier (a dict with 'type' and 'id')
        - A list of a combination of the above
        - A dict with a 'data' field with a list of a combination of the
          above as value
        - None

        Regardless, in the end `self.related[key]` will be a Resource
        instance or None.
        """

        if key not in self.relationships:
            raise ValueError(
                "Cannot change relationship '{}' because it's "
                "not an existing relationship.".format(key)
            )

        relationship = self.relationships[key]

        if is_list(value) or (has_data(value) and is_list(value["data"])):
            # Plural
            if has_data(value):
                value = value["data"]
            self.related[key] = Collection.from_data(self.API, {"data": []})
            for item in value:
                self.related[key].append(self.API.as_resource(item))
            new_relationship = [
                item.as_resource_identifier() for item in self.related[key]
            ]
            if new_relationship != relationship["data"]:
                relationship["data"] = new_relationship
        else:
            # Singular
            value = self.API.as_resource(value)
            null_to_not_null = is_null(relationship) and not is_null(value)
            not_null_to_null = not is_null(relationship) and is_null(value)
            data_changed = (
                not is_null(relationship)
                and not is_null(value)
                and (relationship["data"] != value.as_resource_identifier())
            )
            if null_to_not_null or not_null_to_null or data_changed:
                if value is None:
                    self.relationships[key] = None
                else:
                    self.relationships[key] = value.as_relationship()
            self.related[key] = value

    @classmethod
    def as_resource(cls, data):
        """Little convenience function when we don't know if we are dealing
        with a Resource instance or a dict describing a relationship.
        """

        try:
            return cls(data)
        except Exception:
            return data

    def to_dict(self):
        if self.redirect:
            return self.redirect

        result = {"type": self.TYPE}
        if self.id:
            result["id"] = self.id
        if self.attributes:
            result["attributes"] = self.attributes
        if self.relationships:
            result["relationships"] = self.relationships
        if self.links:
            result["links"] = self.links
        return result

    # Shortcuts
    def __getattr__(self, attr):
        if attr in (
            "a",
            "attributes",
            "R",
            "relationships",
            "r",
            "related",
            "id",
            "links",
            "redirect",
            "API",
        ):
            return super(Resource, self).__getattribute__(attr)
        elif attr in self.attributes:
            return self.attributes[attr]
        elif attr in self.related:
            return self.related[attr]
        else:
            return super(Resource, self).__getattribute__(attr)

    def __setattr__(self, attr, value):
        if attr in (
            "id",
            "attributes",
            "relationships",
            "related",
            "links",
            "redirect",
            "API",
        ):
            super(Resource, self).__setattr__(attr, value)
        elif attr in self.attributes:
            self.attributes[attr] = value
        elif attr in self.relationships:
            try:
                self.set_related(attr, value)
            except ValueError as e:
                raise AttributeError(str(e))
        else:
            super(Resource, self).__setattr__(attr, value)

    # Fetching
    def reload(self, include=None):
        """Fetch fresh data from the server for the object."""

        params = None
        if include is not None:
            params = {"include": ",".join(include)}
        url = self.links.get("self", self.get_item_url())
        response_body = self.API.request("get", url, params=params)
        if (
            isinstance(response_body, requests.Response)
            and response_body.status_code == 303
        ):
            self._overwrite(id=self.id, redirect=response_body.headers["Location"])
        else:
            self._overwrite(
                included=response_body.get("included"), **response_body["data"]
            )

    @classmethod
    def get(cls, id=None, include=None, **filters):
        """Get a resource object by its ID."""

        if id is not None:
            instance = cls(id=id)
            instance.reload(include=include)
            return instance
        else:
            result = cls.list()
            if include is not None:
                result = result.include(*include)
            return result.get(**filters)

    def fetch(self, *relationship_names, **kwargs):
        """Fetches 'relationship', if it wasn't included when fetching 'self';
        `force=True` supported. Usage:

            >>> foo.fetch('parent')

        Related object will be available after that:

            >>> print(foo.related['parent'].attributes['name'])

        Supports plural relationships, but only one page will be available:

            >>> foo.fetch('children')
            >>> # Only first page
            >>> print([child.attributes['name']
            ...        for child in foo.related['children']])
            >>> # All pages
            >>> print([child.attributes['name']
            ...        for child in foo.related['children'].all()])

        If only one positional argument is supplied, it will return the
        related object or collection:

            >>> print(child.fetch('parent').name)

            Equivalent to:

            >>> child.fetch('parent')
            >>> print(child.parent.name)
        """

        force = kwargs.pop("force", False)

        for relationship_name in relationship_names:
            if relationship_name not in self.relationships:
                raise ValueError(
                    "{} doesn't have relationship '{}'".format(
                        repr(self), relationship_name
                    )
                )

        for relationship_name in relationship_names:
            relationship = self.relationships[relationship_name]

            if is_null(relationship):
                continue

            related = self.related.get(relationship_name)
            is_singular_fetched = is_fetched(related)
            is_plural_fetched = is_collection(related) and all(
                (is_fetched(item) for item in related)
            )
            if (is_singular_fetched or is_plural_fetched) and not force:
                # Has been fetched already
                continue

            if has_data(relationship) and not is_list(relationship["data"]):
                # Singular relationship
                self.related[relationship_name].reload()
            else:
                # Plural relationship
                url = relationship.get("links", {}).get(
                    "related", "/{}/{}/{}".format(self.TYPE, self.id, relationship_name)
                )
                self.related[relationship_name] = Collection(self.API, url)

        if len(relationship_names) == 1:
            # This way you can do `project.fetch('languages').filter(...)`
            return self.related[relationship_names[0]]

    @classmethod
    def list(cls):
        return Collection(cls.API, "/{}".format(cls.TYPE))

    def _collection_method(method):
        def _method(cls, *args, **kwargs):
            return getattr(cls.list(), method)(*args, **kwargs)

        return classmethod(_method)

    filter = _collection_method("filter")
    page = _collection_method("page")
    include = _collection_method("include")
    limit = _collection_method("limit")
    sort = _collection_method("sort")
    fields = _collection_method("fields")
    extra = _collection_method("extra")
    all_pages = _collection_method("all_pages")
    all = _collection_method("all")

    # Editing
    def save(self, *fields, **kwargs):
        """For new instances (that have `.id == None`), everything will be
        saved and 'id' and other server-generated fields will be set.

        For existing instances, if `fields` or `cls.EDITABLE` is set, then
        only these fields will be saved.

        Usage:
            >>> class Foo(Resource):
            ...     type = 'foos'
            ...     EDITABLE = ['name']

            >>> foo = Foo.get(1)
            >>> foo.attributes['name'] = 'footastic'
            >>> foo = foo.save()
            >>> # or
            >>> foo = foo.save('name', ...)
        """

        fields = set(fields)

        for key, value in kwargs.items():
            setattr(self, key, value)
            fields.add(key)

        if self.id is not None:
            self._save_existing(*fields)
        else:
            self._save_new(*fields)

    def _save_existing(self, *fields):
        payload = self.as_resource_identifier()
        payload.update(self._generate_data_for_saving(*fields))
        response_body = self.API.request(
            "patch", self.get_item_url(), json={"data": payload}
        )
        self._post_save(response_body)

    def _save_new(self, *fields):
        payload = {"type": self.TYPE}
        if self.id is not None:
            payload["id"] = self.id
        payload.update(self._generate_data_for_saving(*fields))
        response_body = self.API.request(
            "post", self.get_collection_url(), json={"data": payload}
        )
        self._post_save(response_body)

    def _generate_data_for_saving(self, *fields):
        result = {}
        editable_fields = fields or self.EDITABLE
        if editable_fields is not None:
            for field in editable_fields:
                if field in self.attributes:
                    result.setdefault("attributes", {})[field] = self.attributes[field]
                elif field in self.relationships:
                    result.setdefault("relationships", {})[field] = self.relationships[
                        field
                    ]
                else:
                    raise ValueError("Unknown field '{}'".format(field))
        else:
            if self.attributes:
                result["attributes"] = self.attributes
            if self.relationships:
                result["relationships"] = self.relationships
        return result

    def _post_save(self, response_body):
        if isinstance(
            response_body, requests.Response
        ) and response_body.status_code in (202, 204):
            # Success, but the server did not return any new data so our object
            # is considered sufficiently populated with data
            return

        data = response_body["data"]

        related = dict(self.related)
        for relationship_name, related_instance in list(related.items()):
            if is_collection(related_instance):
                continue  # Plural relationship

            try:
                current_id = related_instance.id
            except Exception:
                current_id = None
            try:
                new_id = data["relationships"][relationship_name]["data"]["id"]
            except Exception:
                new_id = None
            if current_id != new_id:
                if new_id is not None:
                    # Relationship changed, reset
                    related[relationship_name] = self.API.new(
                        data["relationships"][relationship_name]
                    )
                else:
                    # Relationship removed
                    del related[relationship_name]

        relationships = data.pop("relationships", {})
        relationships.update(related)

        self._overwrite(
            relationships=relationships, included=response_body.get("included"), **data
        )

    @classmethod
    def create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        instance._save_new()
        return instance

    # Handling files
    @classmethod
    def create_with_form(cls, type=None, **kwargs):
        """Simply fowrard kwargs to requests, for non
        'application/vnd.api+json' requests (eg file uploads)
        """

        if type is None and cls.TYPE is not None:
            type = cls.TYPE
        response_body = cls.API.request("post", cls.get_collection_url(), **kwargs)
        return cls.API.new(response_body)

    def follow(self):
        if self.redirect is None:
            raise ValueError("Cannot follow a non-redirect response")
        response_body = self.API.request("get", self.redirect)
        if is_list(response_body["data"]):
            return Collection.from_data(self.API, response_body)
        elif is_dict(response_body["data"]):
            return self.API.new(response_body)
        else:  # Unreachable code
            raise ValueError("Unknown format while following redirect")

    def delete(self):
        """Deletes a resource from the API. Usage:

        >>> foo.delete()
        """

        self.API.request("delete", self.get_item_url())
        self.id = None

    # Editing relationshps
    def change(self, field, value):
        """Change a singular relationship. Usage:

            >>> # Change `child`'s parent from `parent_a` to `parent_b`
            >>> parent_a, parent_b = Parent.list()[:2]
            >>> child = Child.get(XXX)
            >>> assert child.relationships['parent'] == parent_a
            >>> child.change('parent', parent_b)

        Also works with resource identifiers in case we don't have the full
        Resource instance:

            >>> # Make sure `child_a` and `child_b` have the same parent,
            >>> # without fetching the parent
            >>> child_a, child_b = Child.list()[:2]
            >>> child_b.change('parent',
            ...                child_a.relationships['parent']['data'])

        Note: Depending on the API implementation, this can probably be
        also achieved by changing the relationship and saving:

            >>> # Change `child`'s parent from `parent_a` to `parent_b`
            >>> parent_a, parent_b = Parent.list()[:2]
            >>> child = Child.get(XXX)
            >>> assert (child.relationships['parent']['data']['id'] ==
            ...         parent_a.id)
            >>> child.relationships['parent'] = {
            ...     'data': parent_b.as_resource_identifier(),
            ... }
            >>> child.save('parent')
        """

        value = self.API.as_resource(value)
        self._edit_relationship("patch", field, value.as_resource_identifier())
        self.relationships[field]["data"] = value.as_resource_identifier()
        if self.related[field] != value:
            self.related[field] = value

    def add(self, field, values):
        """Adds items to a plural relationship. Usage:

            >>> # Lets add 3 new children to `parent`
            >>> parent = Parent.get(XXX)
            >>> child_a, child_b, child_c = Child.list(
            ...     filters={'parent[ne]': parent.id},
            ... )[:3]
            >>> parent.add('children', [child_a, child_b, child_c])

        Also works with resource identifiers in case we don't have the
        Resource instances:

            >>> # Make sure parents of `child_a` and `child_b` become
            ...  # children of `grandparent`
            >>> grandparent.add('children',
            ...                 [child_a.relationships['parent']['data'],
            ...                  child_b.relationships['parent']['data']])

        If the plural relationship was previously fetched, it must be
        refetched for the changes to appear.

            >>> parent.add('children', ...)
            >>> parent.fetch('children', force=True)
        """

        self._edit_plural_relationship("post", field, values)

    def remove(self, field, values):
        """Removes items from a plural relationship. Usage:

            >>> parent = Parent.get(XXX)
            >>> child_a, child_b = Child.list(
            ...     filters={'parent': parent.id},
            ... )[:2]
            >>> parent.remove('children', [child_a, child_b])

        Also works with resource identifiers in case we don't have the
        Resource instances:

            >>> # Make sure parents of `child_a` and `child_b` are no
            ... # longer children of `grandparent`
            >>> grandparent.remove(
            ...     'children',
            ...     [child_a.relationships['parent']['data'],
            ...      child_b.relationships['parent']['data']]
            ... )

        If the plural relationship was previously fetched, it must be
        refetched for the changes to appear.

            >>> parent.remove('children', ...)
            >>> parent.fetch('children', force=True)
        """

        self._edit_plural_relationship("delete", field, values)

    def reset(self, field, values):
        """Completely rewrites a plural relationship. Usage:

            >>> parent = Parent.get(XXX)
            >>> child_a, child_b, child_c = Child.list()[:3]
            >>> assert (child_a.relationships['parent']['data']['id'] ==
            ...         parent.id)
            >>> assert (child_b.relationships['parent']['data']['id'] !=
            ...         parent.id)
            >>> assert (child_c.relationships['parent']['data']['id'] !=
            ...         parent.id)

            >>> parent.reset('children', [child_b, child_c])

        If the plural relationship was previously fetched, it must be
        refetched for the changes to appear.

            >>> parent.reset('children', ...)
            >>> parent.fetch('children', force=True)
        """

        self._edit_plural_relationship("patch", field, values)

    def _edit_relationship(self, method, field, value):
        url = (
            self.relationships[field]
            .get("links", {})
            .get("self", "/{}/{}/relationships/{}".format(self.TYPE, self.id, field))
        )
        self.API.request(method, url, json={"data": value})

    def _edit_plural_relationship(self, method, field, values):
        payload = [
            self.API.as_resource(item).as_resource_identifier() for item in values
        ]
        self._edit_relationship(method, field, payload)

    # Bulk actions
    @classmethod
    def bulk_delete(cls, items):
        """Delete API resource instances in bulk. The server needs to support
        this using the 'bulk' profile with the
        'application/vnd.api+json;profile="bulk"' Content-Type header.

        Accepts a list of:

          - Full JSON responses representing a resource object
          - Resource objects
          - Resource identifiers
          - Relationships
          - IDs

        Doesn't return anything, but will raise an exception if something
        went wrong.

        Usage:

            >>> foos = Foo.list(...)
            >>> Foo.bulk_delete(foos)
        """

        payload = []

        for item in items:
            item = cls.as_resource(item)
            if not is_resource(item):
                item = cls(id=item)
            payload.append(item.as_resource_identifier())

        cls.API.request(
            "delete", cls.get_collection_url(), json={"data": payload}, bulk=True
        )
        return len(payload)

    @classmethod
    def bulk_create(cls, items):
        """Create API resource instances in bulk. The server needs to support
        this using the 'bulk' profile with the
        'application/vnd.api+json;profile="bulk"' Content-Type header.

        Accepts a list of:
            - (Unsaved) API resource instances
            - Dictionaries with (optional) 'attributes' and 'relationships'
              fields
            - 2-tuples of 'attributes', 'relationships'
            - 'attributes'

        Returns a list of the created instances.

        Usage:

            >>> # Only attributes
            >>> result = Foo.bulk_create([{'username': "username1"},
            ...                           {'username': "username2"},
            ...                           {'username': "username3"}])
            >>> result[0].id
            <<< 1
            >>> result[0].attributes['username']
            <<< 'username1'

            >>> # attributes and relationships
            >>> parent = ...
            >>> result = Child.bulk_create([({'username': "username1"},
            ...                              {'parent': parent}),
            ...                             ...])
        """

        payload = []
        for item in items:
            if is_list(item):
                attributes, relationships = item
                item = cls(attributes=attributes, relationships=relationships)
            else:
                item = cls.as_resource(item)
                if not isinstance(item, Resource):
                    item = cls(attributes=item)

            payload.append({"type": cls.TYPE})
            if item.attributes:
                payload[-1]["attributes"] = item.attributes
            if item.relationships:
                payload[-1]["relationships"] = item.relationships
            if item.id:
                payload[-1]["id"] = item.id

        response_body = cls.API.request(
            "post", cls.get_collection_url(), json={"data": payload}, bulk=True
        )
        return Collection.from_data(cls.API, response_body)

    @classmethod
    def bulk_update(cls, items, fields=None):
        """Update API resource instances in bulk. The server needs to support
        this using the 'bulk' profile with the
        'application/vnd.api+json;profile="bulk"' Content-Type header.

        Accepts a list of:
            - API resource instances (with IDs)
            - Dictionaries with (optional) 'attributes', 'relationships'
              and (required) 'id' fields
            - 3-tuples of 'id', 'attributes', 'relationships'
            - 2-tuples of 'id', 'attributes'
            - 'ids' (maybe we just want the server to update a timestamp)

        Returns a list of the updated instances.

        Usage:

            >>> foos = Foo.list(...)
            >>> for foo in foos:
            ...     foo.attributes['approved'] = True
            >>> foos = Foo.bulk_update(foos, ['approved'])
        """

        if fields is None:
            fields = cls.EDITABLE

        payload = []
        for item in items:

            if is_list(item):
                try:
                    id, attributes, relationships = item
                except ValueError:
                    id, attributes = item
                    relationships = None
                item = cls(id=id, attributes=attributes, relationships=relationships)
            else:
                item = cls.as_resource(item)
                if not isinstance(item, Resource):
                    item = cls(id=item)

            if item.id is None:
                raise ValueError("'id' not supplied as part of an update " "operation")

            attributes, relationships = item.attributes, item.relationships
            if fields:
                if attributes is not None:
                    attributes = {
                        key: value for key, value in attributes.items() if key in fields
                    }
                if relationships is not None:
                    relationships = {
                        key: value
                        for key, value in relationships.items()
                        if key in fields
                    }

            payload.append(item.as_resource_identifier())
            if attributes:
                payload[-1]["attributes"] = attributes
            if relationships:
                payload[-1]["relationships"] = {
                    key: cls.API.as_resource(value).as_relationship()
                    for key, value in relationships.items()
                }

        response_body = cls.API.request(
            "patch", cls.get_collection_url(), json={"data": payload}, bulk=True
        )
        return Collection.from_data(cls.API, response_body)

    # Utils
    def __eq__(self, other):
        other = self.API.as_resource(other)
        return self.as_resource_identifier() == other.as_resource_identifier()

    def __repr__(self):
        if self.__class__ is Resource:
            class_name = "Unknown Resource"
        else:
            class_name = self.__class__.__name__

        if self.id is not None:
            details = self.id
        else:
            details = "Unsaved"

        if self.redirect is not None:
            details += " (redirect ready)"

        if not self.attributes and not self.relationships:
            details += " (Unfetched)"

        return repr("<{}: {}>".format(class_name, details))

    def __copy__(self):
        # Will eventually call `_overwrite` so `deepcopy` will be used
        relationships = deepcopy(self.relationships)
        relationships.update(self.related)
        return self.__class__(
            id=self.id,
            attributes=self.attributes,
            relationships=relationships,
            links=self.links,
            redirect=self.redirect,
        )

    def as_resource_identifier(self):
        return {"type": self.TYPE, "id": self.id}

    def as_relationship(self):
        return {"data": self.as_resource_identifier()}

    @classmethod
    def get_collection_url(cls):
        return "/{}".format(cls.TYPE)

    def get_item_url(self):
        if "self" in self.links:
            return self.links["self"]
        else:
            return "/{}/{}".format(self.TYPE, self.id)
