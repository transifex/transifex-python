from __future__ import absolute_import, unicode_literals

from copy import deepcopy

import requests
import six

from .auth import BearerAuthentication
from .compat import JSONDecodeError
from .exceptions import JsonApiException
from .resources import Resource

type_ = type  # alias to avoid naming conflicts


class _JsonApiMetaclass(type_):
    """Simple metaclass that overwrites the `registry` class variable on
    `JsonApi` subclasses. This is so that if multiple API connection types
    are defined on the same application, one won't "contaminate" the other.

        eg

        >>> class API_A(jsonapi.JsonApi):
        ...     HOST = "..."

        >>> @API_A.register
        ... class ResourceA(jsonapi.Resource):
        ...     TYPE = "resource_a"

        >>> class API_AA(API_A):
        ...     HOST = "..."

        >>> @API_AA.register
        ... class ResourceAA(jsonapi.Resource):
        ...     TYPE = "resource_aa"

        >>> class API_B(jsonapi.JsonApi):
        ...     HOST = "..."

        >>> @API_B.register
        ... class ResourceB(jsonapi.Resource):
        ...     TYPE = "resource_b"

        >>> API_A.registry
        <<< [ResourceA]

        >>> API_AA.registry
        <<< [ResourceA, ResourceAA]

        >>> API_B.registry
        <<< [ResourceB]
    """

    def __new__(cls, *args, **kwargs):
        result = super(_JsonApiMetaclass, cls).__new__(cls, *args, **kwargs)

        # Use a copy, not reference to parent's registry
        result.registry = list(getattr(result, "registry", []))

        return result


class JsonApi(six.with_metaclass(_JsonApiMetaclass, object)):
    """Inteface for a new {json:api} API connection. Initialization
    parameters:

    - host: The URL of the API
    - headers: A dict of HTTP headers that will be included in every
               request to the server
    - auth: The authentication method. Can either be:

      1. A callable, whose return value should be a dictionary which will
         be merged with the headers of all HTTP request sent to the API
      2. A string, in which case the 'Authorization' header will be
         `Bearer <auth>`

        >>> class API(jsonapi.JsonApi):
        ...     HOST = "..."
        >>> api = API(host=..., auth=...)

    The arguments are optional and can be edited later with `.setup()`

        >>> api = API()
        >>> api.setup(host=..., auth=...)

    All Resource classes that use this API should be registered to this API
    class:

        >>> @API.register
        ... class Foo(jsonapi.Resource):
        ...     TYPE = "foos"
    """

    HOST = None
    HEADERS = None

    def __init__(self, **kwargs):
        """Create a new API connection instance. It will use the class's
        registry to build the instance's registries in order to be able to
        lookup API resource classes from their class names or API types.

        Delegates configuration to `setup` method.
        """

        self.type_registry = {}

        for base_class in self.__class__.registry:
            # Dynamically create a subclass adding 'self' (the API connection
            # instance) as a class variable to it
            child_class = type_(base_class.__name__, (base_class,), {"API": self})

            # Lookup the new class by it's name or its TYPE class attribute
            setattr(self, base_class.TYPE, child_class)
            setattr(self, base_class.__name__, child_class)

            self.type_registry[base_class.TYPE] = child_class

        self.host = self.HOST
        if self.HEADERS is None:
            self.headers = {}
        else:
            self.headers = deepcopy(self.HEADERS)
        self.setup(**kwargs)

    def setup(self, host=None, auth=None, headers=None):
        if host is not None:
            self.host = host

        if auth is not None:
            if callable(auth):
                self.make_auth_headers = auth
            else:
                self.make_auth_headers = BearerAuthentication(auth)

        if headers is not None:
            self.headers.update(headers)

    @classmethod
    def register(cls, klass):
        """Register a API resource type with this API connection *type* (since
        this is a classmethod). When a new API connection *instance* is
        created (see `__init__`), it will use this to build its own
        registry in order to identify class names or API types with the
        relevant API resource classes.
        """

        cls.registry.append(klass)
        return klass

    #                 Required args
    def request(
        self,
        method,
        url,
        # Not passed to requests, used to determine Content-Type
        bulk=False,
        # Forwarded to requests
        headers=None,
        data=None,
        files=None,
        allow_redirects=False,
        **kwargs
    ):
        if url.startswith("/"):
            url = "{}{}".format(self.host, url)

        if bulk:
            content_type = 'application/vnd.api+json;profile="bulk"'
        elif (data, files) == (None, None):
            content_type = "application/vnd.api+json"
        else:
            # If data and/or files are set, requests will determine
            # Content-Type on its own
            content_type = None

        actual_headers = dict(self.headers)

        if headers is not None:
            actual_headers.update(headers)
        actual_headers.update(self.make_auth_headers())
        if content_type is not None:
            actual_headers.setdefault("Content-Type", content_type)

        response = requests.request(
            method,
            url,
            headers=actual_headers,
            data=data,
            files=files,
            allow_redirects=allow_redirects,
            **kwargs
        )

        if not response.ok:
            try:
                exc = JsonApiException.new(
                    response.status_code, response.json()["errors"], response
                )
            except Exception:
                response.raise_for_status()
            else:
                raise exc
        try:
            return response.json()
        except JSONDecodeError:
            # Most likely empty response when deleting
            return response

    def new(self, data=None, type=None, **kwargs):
        """Return a new resource instance, using the appropriate Resource
        subclass, provided that it has been registered with this API
        instance.

            >>> _api = jsonapi.JsonApi(...)
            >>> @_api.register
            ... class Foo(jsonapi.Resource):
            ...     TYPE = "foos"
            >>> obj = _api.new(type="foos", ...)

            >>> isinstance(obj, Foo)
            <<< True
        """

        if data is not None:
            if "data" in data:
                data = data["data"]
            return self.new(**data)
        else:
            if type in self.type_registry:
                klass = self.type_registry[type]
            else:
                # Lets make a new class on the fly
                klass = type_(
                    type.capitalize(), (Resource,), {"API": self, "TYPE": type}
                )
            return klass(**kwargs)

    def as_resource(self, data):
        """Little convenience function when we don't know if we are dealing
        with a Resource instance or a dict describing a relationship. Will
        use the appropriate Resource subclass.
        """

        try:
            return self.new(data)
        except Exception:
            return data
