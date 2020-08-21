from __future__ import absolute_import, unicode_literals


class JsonApiException(Exception):
    """ Assuming a JSON-API error response generated with:

            >>> def do_something():
            ...     response = requests.get(...)
            ...     if not response.ok:
            ...         raise JsonApiException(response.status_code,
            ...                                response.json()['errors'])
            >>> try:
            ...     do_something()
            ... except JsonApiException as e:
            ...     exc = e

        You can access the exception data like:

            >>> exc.status_code
            <<< 400
            >>> len(exc.errors)
            <<< 3
            >>> exc.errors[0].title
            <<< 'Invalid JSON'
            >>> exc.errors[1].code
            <<< 'Forbidden'
            >>> exc.errors[2].detail
            <<< 'There is already a project with the same name'

        The first error's fields are accessible from the main exception; this
        mostly makes sense if `len(exc.errors) == 1`:

            >>> exc.title
            <<< 'Invalid JSON'
    """

    def __init__(self, status_code, errors):
        errors = [JsonApiError(**error) for error in errors]
        super(JsonApiException, self).__init__(status_code, errors)

    status_code = property(lambda self: self.args[0])
    errors = property(lambda self: self.args[1])

    def to_dict(self):
        return {'errors': [error.to_dict() for error in self.errors]}

    # Shortcuts that make sense if len(errors) == 1
    def first_error_property(field):
        def _get(self):
            return getattr(self.errors[0], field)
        return property(_get)

    status = first_error_property('status')
    code = first_error_property('code')
    title = first_error_property('title')
    detail = first_error_property('detail')
    source = first_error_property('source')


class JsonApiError(object):
    def __init__(self, status, code, title, detail, source=None):
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.source = source

    def __repr__(self):  # pragma: no cover
        return repr("<JsonApiError: {} - {}>".format(self.code, self.detail))

    def to_dict(self):
        result = {'status': self.status, 'code': self.code,
                  'title': self.title, 'detail': self.detail}
        if self.source is not None:
            result['source'] = self.source
        return result


class NotSingleItem(Exception):
    pass


class DoesNotExist(NotSingleItem):
    pass


class MultipleObjectsReturned(NotSingleItem):
    @property
    def count(self):
        return self.args[0]
