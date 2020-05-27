# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from transifex.native.django.tools.migrations.templatetags import \
    DjangoTagMigrationBuilder

DJANGO_TEMPLATE = """
{% extends 'base.html' %}
{% load i18n %}

{# Translators: This is an amazing comment #}
{% trans "Hello!" %}

{% comment %}Translators: This is another amazing comment{% endcomment %}
{% trans "May" context "month name" %}

{% with first=events.first %}
    {% with second=events.second %}
        {% blocktrans with third=events.third|title another='foo' %}
        The following events were found:
          1. {{ first }}
          2. {{ second }}
          3. {{ third }}
        And this is {{ another }}.
        {% endblocktrans %}
    {% endwith %}
{% endwith %}

{% blocktrans count counter='something'|length %}
There is only one {{ name }} object.
{% plural %}
There are {{ counter }} {{ name }} objects.
{% endblocktrans %}

{% blocktrans trimmed %}
  First sentence.
  Second paragraph.
{% endblocktrans %}

<a href="{{ url }}">Text</a>
{{ _(some_other_var) }}
{% trans some_other_var|some_filter %}
{% trans "try as" as try %}
{% trans "try with <xml>xml</xml>" %}
{% blocktrans %}
    try with <xml>xml</xml>
{% endblocktrans %}
{% blocktrans with organization_name=organization.name %}Help "{{organization_name}}" translate content {% endblocktrans %}
{% blocktrans %}To download, please click <a href="https://{{ site_domain }}{{ url }}">here</a>.{% endblocktrans %}

{% comment "Optional note" %}
    <p>Commented out text with {{ create_date|date:"c" }}</p>
{% endcomment %}
{# This is not related to translations #}
{% something %}
{% comment %}This is a non-translator comment{% endcomment %}
{% comment %}Translators: This is an orphan translator comment{% endcomment %}
"""

TRANSIFEX_TEMPLATE = """
{% extends 'base.html' %}
{% load i18n %}
{% load transifex %}


{% t "Hello!" _comment="This is an amazing comment" %}


{% t "May" _comment="This is another amazing comment" _context="month name" %}

{% with first=events.first %}
    {% with second=events.second %}
        {% t another='foo' third=events.third|title %}
        The following events were found:
          1. {first}
          2. {second}
          3. {third}
        And this is {another}.
        {% endt %}
    {% endwith %}
{% endwith %}

{% t counter='something'|length %}
{counter, plural, one {
There is only one {name} object.
} other {
There are {counter} {name} objects.
}}
{% endt %}

{% t |trimmed %}
  First sentence.
  Second paragraph.
{% endt %}

<a href="{{ url }}">Text</a>
{% t some_other_var %}
{% t some_other_var|some_filter %}
{% t "try as" as try %}
{% ut "try with <xml>xml</xml>" %}
{% ut %}
    try with <xml>xml</xml>
{% endut %}
{% ut 'Help "{organization_name}" translate content ' organization_name=organization.name %}
{% ut 'To download, please click <a href="https://{site_domain}{url}">here</a>.' %}

{% comment "Optional note" %}
    <p>Commented out text with {{ create_date|date:"c" }}</p>
{% endcomment %}
{# This is not related to translations #}
{% something %}
{% comment %}This is a non-translator comment{% endcomment %}
"""


def test_compiled_string_is_expected():
    """Test all known migration cases."""
    builder = DjangoTagMigrationBuilder()
    file_migration = builder.build_migration(DJANGO_TEMPLATE)
    compiled = file_migration.compile()
    assert compiled == TRANSIFEX_TEMPLATE

    # Make sure the migration is idempotent
    file_migration = builder.build_migration(compiled)
    assert file_migration.compile() == TRANSIFEX_TEMPLATE
