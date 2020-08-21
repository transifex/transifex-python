from __future__ import absolute_import, unicode_literals

import requests

from .auth import BearerAuthentication
from .compat import JSONDecodeError
from .exceptions import JsonApiException
from .resources import Resource


class JsonApi(object):
    """ Inteface for a new {json:api} API.

        - host: The URL of the API
        - auth: The authentication method. Can either be:

          1. A callable, whose return value should be a dictionary which will
             be merged with the headers of all HTTP request sent to the API
          2. A string, in which case the 'Authorization' header will be
             `Bearer <auth>`

            >>> _api = jsonapi.JsonApi(host=..., auth=...)

        The arguments are optional and can be edited later with `.setup()`

            >>> _api = jsonapi.JsonApi()
            >>> _api.setup(host=..., auth=...)

        All Resource classes that use this API should be registered to this API
        instance:

            >>> @_api.register
            ... class Foo(jsonapi.Resource):
            ...     TYPE = "foos"
    """

    def __init__(self, host=None, auth=None):
        self.registry = {}
        self.setup(host, auth)

    def setup(self, host=None, auth=None):
        if host is not None:
            self.host = host

        if auth is not None:
            if callable(auth):
                self.make_auth_headers = auth
            else:
                self.make_auth_headers = BearerAuthentication(auth)

    def register(self, klass):
        if klass.TYPE is not None:
            self.registry[klass.TYPE] = klass
        klass.API = self
        return klass

    #                 Required args
    def request(self, method, url,
                # Not passed to requests, used to determine Content-Type
                bulk=False,
                # Forwarded to requests
                headers=None, data=None, files=None,
                allow_redirects=False,
                **kwargs):
        if url.startswith('/'):
            url = "{}{}".format(self.host, url)

        if bulk:
            content_type = 'application/vnd.api+json;profile="bulk"'
        elif (data, files) == (None, None):
            content_type = "application/vnd.api+json"
        else:
            # If data and/or files are set, requests will determine
            # Content-Type on its own
            content_type = None

        if headers is None:
            headers = {}
        headers.update(self.make_auth_headers())
        if content_type is not None:
            headers.setdefault('Content-Type', content_type)

        response = requests.request(method, url, headers=headers,
                                    data=data, files=files,
                                    allow_redirects=allow_redirects,
                                    **kwargs)

        if not response.ok:
            try:
                exc = JsonApiException(response.status_code,
                                       response.json()['errors'])
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
        """ Return a new resource instance, using the appropriate Resource
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
            if 'data' in data:
                included = data.get('included')
                data = data['data']
                if included is not None and 'included' not in data:
                    data['included'] = included
            return self.new(**data)
        else:
            if type in self.registry:
                klass = self.registry[type]
            else:
                # Lets make a new class on the fly
                class klass(Resource):
                    API = self
            return klass(**kwargs)

    def as_resource(self, data):
        """ Little convenience function when we don't know if we are dealing
            with a Resource instance or a dict describing a relationship. Will
            use the appropriate Resource subclass.
        """

        try:
            return self.new(data)
        except Exception:
            return data
