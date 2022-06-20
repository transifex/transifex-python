from __future__ import absolute_import, unicode_literals

import json

# `requests` is somewhat inconsistent with how it raises this exception.
# (https://github.com/psf/requests/issues/5794)
#
# Depending on the environment, the following can happen during
# `response.json`:
#
#   - Python2 and no `simplejson`, a `ValueError` will be raised
#   - Python2 and `simplejson`, a `simplejson.JSONDecodeError` will be raised
#   - Python3 and no `simplejson`, a `json.JSONDecodeError` will be raised
#   - Python3 and `simplejson`, a `simplejson.JSONDecodeError` will be raised
#
# The following wil make sure that catching
# `transifex.api.jsonapi.compat.JSONDecodeError` in a `try: response.json()`
# block will always work
JSONDecodeError = []
try:
    JSONDecodeError.append(json.JSONDecodeError)
except AttributeError:
    pass
try:
    import simplejson

    JSONDecodeError.append(simplejson.JSONDecodeError)
except ImportError:
    pass
if not JSONDecodeError:
    JSONDecodeError = [ValueError]
JSONDecodeError = tuple(JSONDecodeError)

try:
    import collections.abc as abc
except ImportError:
    import collections as abc  # noqa
try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse  # noqa
