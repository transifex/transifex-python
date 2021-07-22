from __future__ import absolute_import, unicode_literals

import json

try:
    JSONDecodeError = json.JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError

try:
    import collections.abc as abc
except ImportError:
    import collections as abc  # noqa
try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse  # noqa
