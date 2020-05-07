# -*- coding: utf-8 -*-
import pytest
from django.template import TemplateSyntaxError
from transifex.native.django.utils.templates import \
    extract_transifex_template_strings
from transifex.native.parsing import SourceString

# A template to use for tests
# The `anyparenttag` tag is added so that we make sure the t/ut tags
# work properly when nested
TEMPLATE = u"""
{% load transifex %}

{% anyparenttag content_main %}
    <p>{{string1}}</p>
    <p>{{string2}}</p>
{% anyparenttag %}
"""


class TestTemplates(object):
    """Test the utils.extract_transifex_template_strings() method."""

    def test_basic(self):
        src = TEMPLATE.replace(
            u'{{string1}}',
            u'{% t "A very important sentence" %}'
        ).replace(
            u'{{string2}}',
            u'{% t "I will look for {total} items" total=bucket.items|length %}'
        )
        strings = extract_transifex_template_strings(src)
        assert strings == [
            SourceString(u"A very important sentence"),
            SourceString(u"I will look for {total} items"),
        ]

    def test_all_string_params(self):
        src = TEMPLATE.replace(
            u'{{string1}}',
            u'{%t "Le canapé" '
            u'_context="furniture" _comment="_comment" _charlimit=10 '
            u'_tags="t1,t2" %}'
        )
        strings = extract_transifex_template_strings(src)
        assert strings == [
            SourceString(
                u"Le canapé", _context=u'furniture', _comment=u'_comment',
                _charlimit=10, _tags=['t1', 't2']
            ),
        ]

    def test_multiline(self):
        src = TEMPLATE.replace(
            u'{{string1}}',
            u"""
{% t visit_type='first' username=user.name _context="stuff" _charlimit=10 %}
{visit_type, select,
    first {Welcome, {username}}
    returning {Welcome back, {username}}
}
{% endt %}"""
        )
        strings = extract_transifex_template_strings(src)
        assert strings[0] == SourceString(
            u"""
{visit_type, select,
    first {Welcome, {username}}
    returning {Welcome back, {username}}
}
""",
            _context='stuff',
            _charlimit=10,
        )

    def test_raises_exception_if_matching_end_tag_not_found(self):
        src = TEMPLATE.replace(
            u'{{string1}}',
            u"""
            {% t %}
            Test
            {% endut %}"""  # `endt` is expected instead
        )
        with pytest.raises(TemplateSyntaxError):
            extract_transifex_template_strings(src)

        src = TEMPLATE.replace(
            u'{{string1}}',
            u"""
            {% ut %}
            Test
            {% endt %}"""  # `endut` is expected instead
        )
        with pytest.raises(TemplateSyntaxError):
            extract_transifex_template_strings(src)
