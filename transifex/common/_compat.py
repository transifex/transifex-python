import sys

PYVER = sys.version_info[0]
PY3 = PYVER == 3
PY2 = PYVER == 2

if PY3:
    string_types = (str,)
    text_type = str
    binary_type = bytes
else:
    string_types = basestring,
    text_type = unicode
    binary_type = str
