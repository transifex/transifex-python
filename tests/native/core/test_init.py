from transifex import native
from transifex.native import tx as _tx
from transifex.native.rendering import PseudoTranslationPolicy


class TestModuleInit(object):
    """Test __init__.py of root native module."""

    def test_init_uses_given_params(self):
        native.init(
            'mytoken', ['lang1', 'lang2'], cds_host='myhost',
            missing_policy=PseudoTranslationPolicy(),
        )
        assert _tx._cds_handler.token == 'mytoken'
        assert _tx._cds_handler.host == 'myhost'
        assert _tx._languages == ['lang1', 'lang2']
        assert isinstance(_tx._missing_policy, PseudoTranslationPolicy)
