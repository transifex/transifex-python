from __future__ import absolute_import, unicode_literals


class JsonApiException(Exception):
    """Assuming a JSON-API error response generated with:

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
        >>> exc.errors[0]['title']
        <<< 'Invalid JSON'
        >>> exc.errors[1]['code']
        <<< 'Forbidden'
        >>> exc.errors[2]['detail']
        <<< 'There is already a project with the same name'
    """

    def __init__(self, status_code, errors, response):
        super().__init__(status_code, errors, response)

    status_code = property(lambda self: self.args[0])
    errors = property(lambda self: self.args[1])
    response = property(lambda self: self.args[2])

    EXCEPTION_CLASSES = {}

    @classmethod
    def new(cls, status_code, errors, response):
        """Get-or-create a new JsonApiException subclass for the status codes
        in the exception's errors and use that to create the exception
        instance. Usage:

        >>> response = ...
        >>> if not response.ok:
        ...     raise JsonApiException.new(
        ...         response.status_code, response.json()['errors']
        ...     )
        """

        codes = set()
        for error in errors:
            codes |= {str(error["status"]).lower(), str(error["code"]).lower()}
        codes = tuple(sorted(codes))

        if codes not in cls.EXCEPTION_CLASSES:
            # `type` creates the subclass
            # https://docs.python.org/3/library/functions.html#type
            cls.EXCEPTION_CLASSES[codes] = type(
                f"JsonApiException_{'_'.join(codes)}", (cls,), {}
            )
        return cls.EXCEPTION_CLASSES[codes](status_code, errors, response)

    class _NeverRaisedException(Exception):
        pass

    @classmethod
    def get(cls, *codes):
        """Get all JsonApiException subclasses that have been already created
        whose status codes contain the argument. Can be used in except or
        isinstance calls. Usage:

        >>> try:
        ...     project.save(name="New name")
        ... except JsonApiException.get(400):
        ...     print("The request is malformed")
        ... except JsonApiException.get(401):
        ...     print("You are not authorized")
        ... except JsonApiException.get(403):
        ...     print("You do not have permissions")
        ... except JsonApiException.get("conflict"):
        ...     print("Another project with the same name already exists")

        If there hasn't been a JsonApiException subclass already created for
        this status code, then the except clause will be
        `except (_NeverRaisedException, ):` which will never be caught, which
        is OK.
        """

        codes = {str(code).lower() for code in codes}
        return tuple(
            (value for key, value in cls.EXCEPTION_CLASSES.items() if set(key) & codes)
        )

    def filter(self, *codes):
        """Convenience function to manage {json:api} errors. Usage:

        >>> try:
        ...     project.save(name="New name")
        ... except JsonApiException as exc:
        ...     if exc.filter("not_found"):
        ...         print("Project not found")
        ...     elif exc.filter(409):
        ...         print("Project name is already taken")
        ...     elif exc.filter("permission_denied"):
        ...         print("You do not have permission to edit this project")
        ...     else:
        ...         print("Some other error occurred")

        Can be used alongside `JsonApiException.get`:

        >>> try:
        ...     project.save(name="New name")
        ... except JsonApiException.get(400, 401) as exc:
        ...     errors = exc.filter(400)
        ...     print(
        ...         "Permission denied:",
        ...         ", ".join((error["detail"] for error in errors)),
        ...     )
        ...     errors = exc.filter(401)
        ...     print(
        ...         "Unauthorized:",
        ...         ", ".join((error["detail"] for error in errors)),
        ...     )
        """

        codes = {str(code).lower() for code in codes}
        return [
            error
            for error in self.errors
            if str(error["status"]).lower() in codes
            or str(error["code"]).lower() in codes
        ]

    def exclude(self, *codes):
        """Convenience function to manage {json:api} errors. Usage:

        >>> try:
        ...     project.save(name="New name")
        ... except JsonApiException as exc:
        ...     bad_request_errors = exc.filter(400)
        ...     print(
        ...         "Bad request errors:",
        ...         ", ".join((error['detail'] for error in bad_request_errors))
        ...     )
        ...     other_errors = exc.exclude(400)
        ...     print(
        ...         "Other errors:",
        ...         ", ".join((error['detail'] for error in other_errors))
        ...     )
        """

        codes = {str(code).lower() for code in codes}
        return [
            error
            for error in self.errors
            if str(error["status"]).lower() not in codes
            and str(error["code"]).lower() not in codes
        ]


class NotSingleItem(Exception):
    pass


class DoesNotExist(NotSingleItem):
    pass


class MultipleObjectsReturned(NotSingleItem):
    def __init__(self, count):
        super().__init__(count)

    @property
    def count(self):
        return self.args[0]
