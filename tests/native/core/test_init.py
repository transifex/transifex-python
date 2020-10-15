from transifex.native import tx
from transifex.native.rendering import PseudoTranslationPolicy


class TestModuleInit(object):
    """Test __init__.py of root native module."""

    def test_init_uses_given_params(self, reset_tx):
        tx.setup(token='mytoken',
                 languages=['lang1', 'lang2'],
                 cds_host='myhost',
                 missing_policy=PseudoTranslationPolicy())
        assert tx._cds_handler._token == 'mytoken'
        assert tx._cds_handler._host == 'myhost'
        assert tx._hardcoded_language_codes == ['lang1', 'lang2']
        assert isinstance(tx._missing_policy, PseudoTranslationPolicy)
