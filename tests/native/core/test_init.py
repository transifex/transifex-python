from transifex import native
from transifex.native import tx as _tx
from transifex.native.cache import AbstractCache, MemoryCache
from transifex.native.rendering import (AbstractErrorPolicy,
                                        PseudoTranslationPolicy,
                                        SourceStringErrorPolicy,
                                        SourceStringPolicy)


class DummyErrorPolicy(AbstractErrorPolicy):
    pass


class DummyCache(AbstractCache):
    pass


class TestModuleInit(object):
    """Test __init__.py of root native module."""

    def test_init_uses_given_params(self, reset_tx):
        native.init(
            'mytoken', ['lang1', 'lang2'], cds_host='myhost',
            missing_policy=PseudoTranslationPolicy(),
            error_policy=DummyErrorPolicy(),
            cache=DummyCache(),
        )
        assert _tx.initialized is True
        assert _tx._cds_handler.token == 'mytoken'
        assert _tx._cds_handler.host == 'myhost'
        assert _tx._languages == ['lang1', 'lang2']
        assert isinstance(_tx._missing_policy, PseudoTranslationPolicy)
        assert isinstance(_tx._error_policy, DummyErrorPolicy)
        assert isinstance(_tx._cache, DummyCache)

    def test_initialized_only_once(self, reset_tx):
        # Even if native.init() is called multiple times, only the first one matters
        native.init(
            'mytoken', ['lang1', 'lang2'], cds_host='myhost',
        )
        native.init(
            'another_token',
            ['lang3', 'lang4'],
            'another_host',
            missing_policy=PseudoTranslationPolicy(),
            error_policy=DummyErrorPolicy(),
            cache=DummyCache(),
        )
        assert _tx._cds_handler.token == 'mytoken'
        assert _tx._cds_handler.host == 'myhost'
        assert _tx._languages == ['lang1', 'lang2']
        assert isinstance(_tx._missing_policy, SourceStringPolicy)
        assert isinstance(_tx._error_policy, SourceStringErrorPolicy)
        assert isinstance(_tx._cache, MemoryCache)
