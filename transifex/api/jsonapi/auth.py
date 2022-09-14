from __future__ import absolute_import, unicode_literals

import datetime


class SimpleAuthentication:
    def __init__(self, token):
        self.token = token

    def __call__(self):
        return {"Authorization": f"{self.KEY} {self.token}"}


class BearerAuthentication(SimpleAuthentication):
    """
    You can use this as an alternative to the 'auth' keyword argument to JsonApi's
    '__init__' or 'setup'. Instead of:

        >>> transifex_api.setup(auth="TOKEN")

    You can use:

        >>> from transifex.api.jsonapi.auth import BearerAuthentication
        >>> transifex_api.setup(BearerAuthentication("Token"))

    This has the exact same effect, but is more verbose.
    """

    KEY = "Bearer"


class OAuthAuthentication(SimpleAuthentication):
    """
    You can use this to set up the SDK to work with OAuth applications:

        >>> from transifex.api.jsonapi.auth import OAuthAuthentication
        >>> transifex_api.setup(OAuthAuthentication("Token"))
    """

    KEY = "OAuth"


class ULFAuthentication(object):
    def __init__(self, public, secret=None):
        self.public = public
        self.secret = secret

    def __call__(self):
        if self.secret is None:
            return {"Authorization": "ULF {}".format(self.public)}
        else:
            return {"Authorization": ("ULF {}:{}".format(self.public, self.secret))}


class JWTAuthentication(object):
    """
    Usage:

        >>> from jsonapi import setup
        >>> setup(host="https://some.host.com",
        ...       auth=JWTAuthentication(payload={'username': "username"},
        ...                              secret="SHARED_SECRET",
        ...                              duration=300))
    """

    def __init__(self, payload, secret, duration, algorithm="HS256", get_now=None):
        self.payload = dict(payload)
        self.secret = secret
        self.duration = duration
        self.algorithm = algorithm

        # Dependency injection for getting the current timestamp; maybe it will
        # make testing easier
        if get_now is None:
            get_now = datetime.datetime.utcnow
        self.get_now = get_now

    def __call__(self):
        import jwt  # Optional requirement, don't require at top level

        exp = self.get_now() + datetime.timedelta(seconds=self.duration)
        payload = dict(self.payload)
        payload["exp"] = exp
        token = jwt.encode(
            payload=payload, secret=self.secret, algorithm=self.algorithm
        )
        return {"Authorization": "JWT {}".format(token)}
