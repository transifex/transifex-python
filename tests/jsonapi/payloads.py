from __future__ import absolute_import, unicode_literals

from copy import deepcopy


class Payloads(object):
    """ Usage:

        >>> payloads = Payloads('items')
        >>> payloads[1]
        <<< {'type': "items", 'id': "1", 'attributes': {'name': "item 1"}}
        >>> payloads[1:4]
        <<< [{'type': "items", 'id': "1", 'attributes': {'name': "item 1"}},
        ...  {'type': "items", 'id': "2", 'attributes': {'name': "item 2"}},
        ...  {'type': "items", 'id': "3", 'attributes': {'name': "item 3"}}]
    """

    def __init__(self, plural_type, singular_type=None, extra=None):
        if singular_type is None:
            singular_type = plural_type[:-1]  # items => item
        if extra is None:
            extra = {}

        self.plural_type = plural_type
        self.singular_type = singular_type
        self.extra = deepcopy(extra)

    def __getitem__(self, index):
        if isinstance(index, slice):
            start = index.start if index.start is not None else 1
            stop = index.stop
            step = index.step if index.step is not None else 1
            return [self._payload(i) for i in range(start, stop, step)]
        else:
            return self._payload(index)

    def _payload(self, i):
        result = {'type': self.plural_type,
                  'id': str(i),
                  'attributes': {'name': ("{} {}".
                                          format(self.singular_type, i))}}
        result.update(self.extra)
        return result
