# -*- coding: utf-8 -*-
from transifex.native.cache import MemoryCache


class TestMemoryCache(object):
    """Tests the functionality of the MemoryCache class."""

    def test_returns_none_if_not_exists(self):
        cache = MemoryCache()
        assert cache.get('missing_key', 'en') is None

    def test_returns_entry_if_exists(self):
        cache = MemoryCache()
        cache.update(
            {
                'en': (True, {
                    'table': {
                        'string': u'A table'
                    },
                    'chair': {
                        'string': u'A chair'
                    },
                }),
                'el': (True, {
                    'table': {
                        'string': u'Ένα τραπέζι'
                    },
                    'chair': {
                        'string': u'Μια καρέκλα'
                    },
                }),
            },
        )
        assert cache.get('table', 'en') == u'A table'
        assert cache.get('chair', 'en') == u'A chair'
        assert cache.get('table', 'el') == u'Ένα τραπέζι'
        assert cache.get('chair', 'el') == u'Μια καρέκλα'
        assert cache.get('invalid', 'en') is None
        assert cache.get('invalid', 'el') is None
