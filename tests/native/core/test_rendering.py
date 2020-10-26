# -*- coding: utf-8 -*-
from mock import patch

from transifex.native.rendering import (ChainedMissingPolicy,
                                        ExtraLengthMissingPolicy,
                                        SourceStringErrorPolicy,
                                        WrappedStringMissingPolicy,
                                        html_escape, parse_missing_policy,
                                        pseudo_translation_missing_policy,
                                        source_string_missing_policy)

COMPLEX_STRINGS = u"""{gender_of_host, select,
  female {
    {total_guests, plural, offset:1
      =0 {{host} does not give a party.}
      =1 {{host} invites {guest} to her party.}
      =2 {{host} invites {guest} and one other person to her party.}
      other {{host} invites {guest} and # other people to her party.}}}
  male {
    {total_guests, plural, offset:1
      =0 {{host} does not give a party.}
      =1 {{host} invites {guest} to his party.}
      =2 {{host} invites {guest} and one other person to his party.}
      other {{host} invites {guest} and # other people to his party.}}}
  other {
    {total_guests, plural, offset:1
      =0 {{host} does not give a party.}
      =1 {{host} invites {guest} to their party.}
      =2 {{host} invites {guest} and one other person to their party.}
      other {{host} invites {guest} and # other people to their party.}}}
}"""

JS_SCRIPT = u'<script type="text/javascript">alert(1)</script>'


class TestMissingPolicies(object):
    """ Tests the functionality of the various StringRenderer callables."""

    def test_source_string_policy(self):
        assert (source_string_missing_policy(u'Source-String') ==
                u'Source-String')

    def test_pseudo_translation_policy(self):
        assert pseudo_translation_missing_policy(u'Source') == u'Șøüȓċê'

    def test_wrapped_string(self):
        missing = WrappedStringMissingPolicy(start='[[', end=']]')(u'Source')
        assert missing == u'[[Source]]'

        missing = WrappedStringMissingPolicy()(u'Source')
        assert missing == u'[Source]'

    def test_extra_length(self):
        missing = ExtraLengthMissingPolicy()(u'Source')
        assert missing == u'Source~e'

        missing = ExtraLengthMissingPolicy(extra_percentage=0.8,
                                           extra_str=u'$')(u'Source')
        assert missing == u'Source$$$$$'

    def test_chained(self):
        policy = ChainedMissingPolicy(
            pseudo_translation_missing_policy,
            ExtraLengthMissingPolicy(extra_percentage=0.5),
            WrappedStringMissingPolicy(start='>>', end='<<'),
        )
        missing = policy(u'This is a long sentence')
        assert missing == u'>>Ťȟıš ıš à ĺøñğ šêñťêñċê~extra~~extr<<'

        # Test again with different order
        policy = ChainedMissingPolicy(
            ExtraLengthMissingPolicy(extra_percentage=0.5),
            WrappedStringMissingPolicy(start='>>', end='<<'),
            pseudo_translation_missing_policy,
        )
        missing = policy(u'This is a long sentence')
        assert missing == u'>>Ťȟıš ıš à ĺøñğ šêñťêñċê~êẋťȓà~~êẋťȓ<<'


class TestErrorPolicies(object):
    """Tests the functionality of the various ErrorPolicy callables."""

    def test_source_string_policy(self):
        assert (SourceStringErrorPolicy()(source_string='Source-String',
                                          translation_template=None,
                                          language_code='a',
                                          escape=html_escape) ==
                'Source-String')

    def test_source_string_policy_with_error(self):
        assert (SourceStringErrorPolicy()(source_string='{',
                                          translation_template=None,
                                          language_code='a',
                                          escape=html_escape) ==
                'ERROR')


class TestParsing(object):
    """Tests the parse_missing_policy() method."""

    def test_none_returns_none(self):
        assert parse_missing_policy(None) is None

    def test_policy_object_returns_the_object(self):
        policy = WrappedStringMissingPolicy()
        assert parse_missing_policy(policy) == policy

    def test_list(self):
        """Test a list of policy objects, string paths and path/param tuples."""
        parsed = parse_missing_policy([
            WrappedStringMissingPolicy('{{', '}}'),
            'transifex.native.rendering.pseudo_translation_missing_policy',
            (
                'transifex.native.rendering.ExtraLengthMissingPolicy',
                {'extra_percentage': 0.5, 'extra_str': 'foo'},
            )
        ])
        assert isinstance(parsed, ChainedMissingPolicy)
        assert len(parsed._policies) == 3
        assert parsed._policies[0].__dict__ == {'end': '}}', 'start': '{{'}
        assert parsed._policies[1] == pseudo_translation_missing_policy
        assert parsed._policies[2].__dict__ == {
            'extra_percentage': 0.5, 'extra_str': 'foo',
        }
