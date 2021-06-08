# -*- coding: utf-8 -*-
import pytest
from mock import patch
from transifex.native.rendering import (ChainedPolicy, ExtraLengthPolicy,
                                        PseudoTranslationPolicy,
                                        SourceStringErrorPolicy,
                                        SourceStringPolicy, StringRenderer,
                                        WrappedStringPolicy)
from transifex.native.settings import parse_rendering_policy

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


class TestStringRenderer(object):
    """Tests the functionality of the StringRenderer class."""

    def test_simple_render_escaped(self):
        translation = StringRenderer.render(
            JS_SCRIPT,
            JS_SCRIPT,
            'en',
            escape=True,
            missing_policy=SourceStringPolicy(),
            params={'cnt': 2},
        )
        assert translation == (
            u'&lt;script type=&quot;text/javascript&quot;&gt;alert(1)&lt;/script&gt;'
        )

    def test_simple_render_unescaped(self):
        translation = StringRenderer.render(
            JS_SCRIPT,
            JS_SCRIPT,
            'en',
            escape=False,
            missing_policy=SourceStringPolicy(),
            params={'cnt': 2},
        )
        assert translation == JS_SCRIPT

    def test_simple_render_with_translation(self):
        translation = StringRenderer.render(
            u'{cnt, plural, one {{cnt} table} other {{cnt} tables}}',
            u'{cnt, plural, one {{cnt} τραπέζι} other {{cnt} τραπέζια}}',
            'en',
            escape=True,
            missing_policy=SourceStringPolicy(),
            params={'cnt': 2},
        )
        assert translation == u'2 τραπέζια'

    def test_simple_render_with_missing_translation(self):
        translation = StringRenderer.render(
            u'{cnt, plural, one {{cnt} table} other {{cnt} tables}}',
            None,
            'en',
            escape=True,
            missing_policy=SourceStringPolicy(),
            params={'cnt': 2},
        )
        # Should fall back to source
        assert translation == u'2 tables'

        translation = StringRenderer.render(
            u'{cnt, plural, one {{cnt} table} other {{cnt} tables}}',
            None,
            'en',
            escape=True,
            missing_policy=PseudoTranslationPolicy(),
            params={'cnt': 2},
        )
        # Should use the proper missing policy
        assert translation == u'2 ťàƀĺêš'

    def test_simple_render_escaped_with_missing_translation(self):
        translation = StringRenderer.render(
            JS_SCRIPT,
            None,
            'en',
            escape=True,
            missing_policy=SourceStringPolicy(),
            params={'cnt': 2},
        )
        assert translation == (
            u'&lt;script type=&quot;text/javascript&quot;&gt;alert(1)&lt;/script&gt;'
        )

    def test_simple_render_unescaped_with_missing_translation(self):
        translation = StringRenderer.render(
            JS_SCRIPT,
            None,
            'en',
            escape=False,
            missing_policy=SourceStringPolicy(),
            params={'cnt': 2},
        )
        assert translation == JS_SCRIPT

    def test_complex_message_format(self):
        translation = self._complex(gender_of_host='female', total_guests=1)
        assert translation == u'Jane does not give a party.'

        translation = self._complex(gender_of_host='female', total_guests=2)
        assert translation == u'Jane invites Joe to her party.'

        translation = self._complex(gender_of_host='female', total_guests=3)
        assert translation == u'Jane invites Joe and one other person to her party.'

        translation = self._complex(gender_of_host='female', total_guests=10)
        assert translation == u'Jane invites Joe and 9 other people to her party.'

    def _complex(self, **params):
        params = dict(params)
        params.update({'host': "Jane", 'guest': "Joe"})
        return StringRenderer.render(
            COMPLEX_STRINGS,
            None,
            'en',
            escape=True,
            missing_policy=SourceStringPolicy(),
            params=params,
        )

    @patch('transifex.native.rendering.html_escape')
    @patch('transifex.native.rendering.logger')
    def test_error_raises_exception(self, mock_logger, mock_escape):

        mock_escape.side_effect = Exception
        with pytest.raises(Exception):
            translation = StringRenderer.render(
                'Source String',
                'Translation',
                'en',
                escape=True,
                missing_policy=SourceStringPolicy(),
            )
        mock_logger.error.assert_called_with(
            'RenderingError: Could not render string `%s` in language `%s` '
            'with parameters `%s` (Error: %s, Source String: %s)',
            'Translation', 'en', '{}', '', 'Source String'
        )

    def test_no_missing_policy_and_error_raises_exception(self):
        with pytest.raises(Exception) as exc_info:
            translation = StringRenderer.render(
                'source',
                '',
                'en',
                escape=True,
                missing_policy=None,
            )
        assert str(exc_info.value) == (
            'No string to render and no missing policy defined! '
            '(Source String: `source`)'
        )


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
        assert SourceStringErrorPolicy().get(
            source_string='Source-String',
            translation=None,
            language_code='a',
            escape=True
        ) == 'Source-String'

    @patch('transifex.native.rendering.logger')
    @patch('transifex.native.rendering.StringRenderer')
    def test_source_string_policy(self, mock_renderer, mock_logger):
        mock_renderer.render.side_effect = Exception
        assert SourceStringErrorPolicy().get(
            source_string='Source-String',
            translation=None,
            language_code='a',
            escape=True
        ) == 'ERROR'
        mock_logger.error.assert_called_with(
            'ErrorPolicyError: Could not render string `Source-String` with parameters `{}`'
        )


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
