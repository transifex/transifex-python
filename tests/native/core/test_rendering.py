# -*- coding: utf-8 -*-
from mock import patch

from transifex.native.rendering import (ChainedPolicy, ExtraLengthPolicy,
                                        PseudoTranslationPolicy,
                                        SourceStringErrorPolicy,
                                        SourceStringPolicy,
                                        WrappedStringPolicy, html_escape,
                                        parse_rendering_policy)

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
    """Tests the functionality of the various StringRenderer subclasses
    of AbstractRenderingPolicy."""

    def test_source_string_policy(self):
        assert SourceStringPolicy().get(u'Source-String') == u'Source-String'

    def test_pseudo_translation_policy(self):
        assert PseudoTranslationPolicy().get(u'Source') == u'Șøüȓċê'

    def test_wrapped_string(self):
        missing = WrappedStringPolicy(start='[[', end=']]').get(u'Source')
        assert missing == u'[[Source]]'

        missing = WrappedStringPolicy().get(u'Source')
        assert missing == u'[Source]'

    def test_extra_length(self):
        missing = ExtraLengthPolicy().get(u'Source')
        assert missing == u'Source~e'

        missing = ExtraLengthPolicy(extra_percentage=0.8, extra_str=u'$')\
            .get(u'Source')
        assert missing == u'Source$$$$$'

    def test_chained(self):
        policy = ChainedPolicy(
            PseudoTranslationPolicy(),
            ExtraLengthPolicy(extra_percentage=0.5),
            WrappedStringPolicy(start='>>', end='<<'),
        )
        missing = policy.get(u'This is a long sentence')
        assert missing == u'>>Ťȟıš ıš à ĺøñğ šêñťêñċê~extra~~extr<<'

        # Test again with different order
        policy = ChainedPolicy(
            ExtraLengthPolicy(extra_percentage=0.5),
            WrappedStringPolicy(start='>>', end='<<'),
            PseudoTranslationPolicy(),
        )
        missing = policy.get(u'This is a long sentence')
        assert missing == u'>>Ťȟıš ıš à ĺøñğ šêñťêñċê~êẋťȓà~~êẋťȓ<<'


class TestErrorPolicies(object):
    """Tests the functionality of the various ErrorPolicy subclasses
    of AbstractErrorPolicy."""

    def test_source_string_policy(self):
        assert (SourceStringErrorPolicy().
                get(source_string='Source-String',
                    translation_template=None,
                    language_code='a',
                    escape=html_escape) ==
                'Source-String')

    def test_source_string_policy_with_error(self):
        assert (SourceStringErrorPolicy().
                get(source_string='{',
                    translation_template=None,
                    language_code='a',
                    escape=html_escape) ==
                'ERROR')


class TestParsing(object):
    """Tests the parse_rendering_policy() method."""

    def test_none_returns_none(self):
        assert parse_rendering_policy(None) is None

    def test_policy_object_returns_the_object(self):
        policy = WrappedStringPolicy()
        assert parse_rendering_policy(policy) == policy

    def test_list(self):
        """Test a list of policy objects, string paths and path/param tuples."""
        parsed = parse_rendering_policy([
            WrappedStringPolicy('{{', '}}'),
            'transifex.native.rendering.PseudoTranslationPolicy',
            (
                'transifex.native.rendering.ExtraLengthPolicy',
                {'extra_percentage': 0.5, 'extra_str': 'foo'},
            )
        ])
        assert isinstance(parsed, ChainedPolicy)
        assert len(parsed._policies) == 3
        assert parsed._policies[0].__dict__ == {'end': '}}', 'start': '{{'}
        assert isinstance(parsed._policies[1], PseudoTranslationPolicy)
        assert parsed._policies[2].__dict__ == {
            'extra_percentage': 0.5, 'extra_str': 'foo',
        }
