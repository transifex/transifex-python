from __future__ import unicode_literals

from django.template import Context, Template
from django.utils import translation
from transifex.common.utils import generate_key
from transifex.native import tx
from transifex.native.django.templatetags.utils import get_icu_keys
from transifex.native.rendering import SourceStringPolicy


def do_test(template_str, context_dict=None, autoescape=True,
            lang_code="en-us"):
    """ Use django's templating engine to render a template against a context

        Arguments:

        :param template_str: The template to render
        :param context_dict: The context to render the template against
        :param autoescape:   Pretend the django templating engine was setup
                             with autoescape or not (in most real use-cases, it
                             will have been set up with autoescape=True)
        :param lang_code:    The language to translate to

        :return:             The compilation result

        Information about (auto)escaping in django:
        https://docs.djangoproject.com/en/3.0/ref/templates/language/#automatic-html-escaping  # noqa
    """

    translation.activate(lang_code)
    if context_dict is None:
        context_dict = {}
    context = Context(dict(context_dict), autoescape=autoescape)
    template = ('{% load transifex %}' + template_str)
    return Template(template).render(context)


def test_simple():
    assert do_test('{% t "hello world" %}') == "hello world"


def test_equal_sign():
    # '=' in first arg means parameter and thus block syntax
    assert do_test('{% t var="world" %}hello {var}{% endt %}') == "hello world"

    # '=' in first arg when first arg is a string literal means it is not a
    # parameter and thus inline syntax
    assert do_test('{% t "hello=world" %}') == "hello=world"


def test_escaping_with_t_tag_and_autoescape():
    # t-tag and autoescape means both XMLs are escaped
    assert (do_test('{% t "<xml>hello</xml> {var}" %}',
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')


def test_escaping_with_t_tag_and_no_autoescape():
    # t-tag and no autoescape means only template XML is escaped
    assert (do_test('{% t "<xml>hello</xml> {var}" %}',
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')


def test_escaping_with_t_tag_and_param():
    # With `var=var`, we have the same outcome as before
    assert (do_test('{% t "<xml>hello</xml> {var}" var=var %}',
                    #                              ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')

    assert (do_test('{% t "<xml>hello</xml> {var}" var=var %}',
                    #                              ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')


def test_escaping_with_t_tag_and_safe_param():
    # With `var=var|safe`, `autoescape` is ignored and context XML is not
    # escaped
    assert (do_test('{% t "<xml>hello</xml> {var}" var=var|safe %}',
                    #                                     ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')

    assert (do_test('{% t "<xml>hello</xml> {var}" var=var|safe %}',
                    #                                     ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')


def test_escaping_with_t_tag_and_escaped_param():
    # With `var=var|escape`, `autoescape` is ignored and context XML is always
    # escaped
    assert (do_test('{% t "<xml>hello</xml> {var}" var=var|escape %}',
                    #                                     ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')

    assert (do_test('{% t "<xml>hello</xml> {var}" var=var|escape %}',
                    #                                     ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')


def test_escaping_with_ut_tag_and_autoescape():
    # ut-tag and autoescape means only context XML is escaped
    assert (do_test('{% ut "<xml>hello</xml> {var}" %}',
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')


def test_escaping_with_ut_tag_and_no_autoescape():
    # ut-tag and no autoescape means no XML is escaped
    assert (do_test('{% ut "<xml>hello</xml> {var}" %}',
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> <xml>world</xml>')


def test_escaping_with_ut_tag_and_param():
    # With `var=var`, we have the same outcome as before
    assert (do_test('{% ut "<xml>hello</xml> {var}" var=var %}',
                    #                               ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')

    assert (do_test('{% ut "<xml>hello</xml> {var}" var=var %}',
                    #                               ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> <xml>world</xml>')


def test_escaping_with_ut_tag_and_safe_param():
    # With `var=var|safe`, `autoescape` is ignored and context XML is not
    # escaped
    assert (do_test('{% ut "<xml>hello</xml> {var}" var=var|safe %}',
                    #                                      ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> <xml>world</xml>')

    assert (do_test('{% ut "<xml>hello</xml> {var}" var=var|safe %}',
                    #                                      ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> <xml>world</xml>')


def test_escaping_with_ut_tag_and_escaped_param():
    # With `var=var|escape`, `autoescape` is ignored and context XML is always
    # escaped
    assert (do_test('{% ut "<xml>hello</xml> {var}" var=var|escape %}',
                    #                                      ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')

    assert (do_test('{% ut "<xml>hello</xml> {var}" var=var|escape %}',
                    #                                      ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')


def test_filters_on_source_string():
    assert (do_test('{% t "<xml>hello</xml> {var}"|upper %}',
                    #                             ^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&LT;XML&GT;HELLO&LT;/XML&GT; &LT;XML&GT;WORLD&LT;/XML&GT;')
    assert (do_test('{% t "<xml>hello</xml> {var}"|upper %}',
                    #                             ^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&LT;XML&GT;HELLO&LT;/XML&GT; <XML>WORLD</XML>')
    assert (do_test('{% ut "<xml>hello</xml> {var}"|upper %}',
                    #                              ^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<XML>HELLO</XML> &LT;XML&GT;WORLD&LT;/XML&GT;')
    assert (do_test('{% ut "<xml>hello</xml> {var}"|upper %}',
                    #                              ^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<XML>HELLO</XML> <XML>WORLD</XML>')


def test_escape_and_safe_filters_on_source_string_ignored():
    assert (do_test('{% t "<xml>hello</xml> {var}"|escape %}',
                    #                             ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t "<xml>hello</xml> {var}"|safe %}',
                    #                             ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% ut "<xml>hello</xml> {var}"|escape %}',
                    #                              ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% ut "<xml>hello</xml> {var}"|safe %}',
                    #                              ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')


def test_asvar():
    assert (do_test('{% ut "<xml>hello</xml> {var}" as text %}{{ text }}',
                    #                               ^^^^^^^   ^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> <xml>world</xml>')
    assert (do_test('{% ut "<xml>hello</xml> {var}" as text %}{{ text }}',
                    #                               ^^^^^^^   ^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t "<xml>hello</xml> {var}" as text %}{{ text }}',
                    #                               ^^^^^^^   ^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')
    assert (do_test('{% t "<xml>hello</xml> {var}" as text %}{{ text }}',
                    #                              ^^^^^^^   ^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')


def test_filter_on_asvar():
    assert (
        do_test(
            '{% t "<xml>hello</xml> {var}" as text %}{{ text|upper|safe }}',
            #                                               ^^^^^^^^^^^
            {'var': "<xml>world</xml>"},
            autoescape=True,
        ) ==
        '&LT;XML&GT;HELLO&LT;/XML&GT; &LT;XML&GT;WORLD&LT;/XML&GT;'
    )


def test_escape_and_safe_filter_on_asvar_ignored():
    assert (do_test('{% t "<xml>hello</xml> {var}" as text %}{{ text|safe }}',
                    #                                               ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')
    assert (
        do_test('{% t "<xml>hello</xml> {var}" as text %}{{ text|escape }}',
                #                                               ^^^^^^^
                {'var': "<xml>world</xml>"},
                autoescape=True) ==
        '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;'
    )


def test_translate_variable():
    assert (do_test('{% ut source %}',
                    #      ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% ut source %}',
                    #      ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> <xml>world</xml>')
    assert (do_test('{% t source %}',
                    #     ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t source %}',
                    #     ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')


def test_filter_on_source_variable():
    assert (do_test('{% ut source|upper %}',
                    #            ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<XML>HELLO</XML> &LT;XML&GT;WORLD&LT;/XML&GT;')
    assert (do_test('{% ut source|upper %}',
                    #            ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<XML>HELLO</XML> <XML>WORLD</XML>')
    assert (do_test('{% t source|upper %}',
                    #           ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&LT;XML&GT;HELLO&LT;/XML&GT; &LT;XML&GT;WORLD&LT;/XML&GT;')
    assert (do_test('{% t source|upper %}',
                    #           ^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&LT;XML&GT;HELLO&LT;/XML&GT; <XML>WORLD</XML>')


def test_safe_and_escape_filter_on_source_variable_ignored():
    assert (do_test('{% t source|safe %}',
                    #           ^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t source|escape %}',
                    #           ^^^^^^^
                    {'source': "<xml>hello</xml> {var}",
                     'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')


def test_block():
    assert (do_test('{% t %}hello world{% endt %}') == 'hello world')
    #                       ^^^^^^^^^^^^^^^^^^^^^
    assert (do_test('{% t %}hello {var}{% endt %}', {'var': "world"}) ==
            #               ^^^^^^^^^^^^^^^^^^^^^
            'hello world')
    assert (do_test('{% ut %}<xml>hello</xml> {var}{% endut %}',
                    #       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '<xml>hello</xml> <xml>world</xml>')
    assert (do_test('{% ut %}<xml>hello</xml> {var}{% endut %}',
                    #        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t %}<xml>hello</xml> {var}{% endt %}',
                    #       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=False) ==
            '&lt;xml&gt;hello&lt;/xml&gt; <xml>world</xml>')
    assert (do_test('{% t %}<xml>hello</xml> {var}{% endt %}',
                    #       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')


def test_filter_on_block():
    assert (do_test('{% t |upper %}hello world{% endt %}') == 'HELLO WORLD')
    #                     ^^^^^^


def test_safe_and_escape_filter_on_block_ignored():
    assert (do_test('{% ut |safe %}<xml>hello</xml> {var}{% endut %}',
                    #      ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% ut |escape %}<xml>hello</xml> {var}{% endut %}',
                    #      ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '<xml>hello</xml> &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t |safe %}<xml>hello</xml> {var}{% endt %}',
                    #     ^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')
    assert (do_test('{% t |escape %}<xml>hello</xml> {var}{% endt %}',
                    #     ^^^^^^^
                    {'var': "<xml>world</xml>"},
                    autoescape=True) ==
            '&lt;xml&gt;hello&lt;/xml&gt; &lt;xml&gt;world&lt;/xml&gt;')


def test_translates():
    hello_key = generate_key(string='hello', context=None)
    tx._cache.update({'fr': (True, {hello_key: {'string': "bonjour"}})})
    assert do_test('{% t "hello" %}', lang_code="fr") == "bonjour"


def test_translation_missing():
    old_missing_policy = tx._missing_policy
    tx._missing_policy = SourceStringPolicy()

    tx._cache._translations_by_lang = {}
    assert do_test('{% t "hello" %}', lang_code="fr") == "hello"

    hello_key = generate_key(string='hello', context=None)
    tx._cache.update({'fr': (True, {hello_key: {'string': None}})})
    assert do_test('{% t "hello" %}', lang_code="fr") == "hello"

    tx._missing_policy = old_missing_policy


def test_escaping_is_done_on_translation():
    hello_key = generate_key(string='hello', context=None)
    tx._cache.update(
        {'fr': (True, {hello_key: {'string': "<xml>bonjour</xml>"}})})
    assert (do_test('{% t "hello" %}', lang_code="fr") ==
            '&lt;xml&gt;bonjour&lt;/xml&gt;')


def test_source_filter_is_applied_on_translation():
    # 'hello' => 'bonjour', 'HELLO' => 'I like pancakes'
    hello_key = generate_key(string='hello', context=None)
    HELLO_key = generate_key(string='HELLO', context=None)
    tx._cache.update(
        {'fr': (
            True,
            {
                hello_key: {'string': "bonjour"},
                HELLO_key: {'string': "I like pancakes"}
            }
        )})

    assert do_test('{% t "hello"|upper %}', lang_code="fr") == "BONJOUR"
    # If the filter was applied on the source string, we would get
    # 'I like pancakes'
    translation.activate('en-us')


def test_get_icu_keys():
    assert "username" in get_icu_keys("hello {username}")
    assert "cnt" in get_icu_keys("""
        {cnt, plural,
            one {you have one message}
            other {you have # new messages}}
    """)

    # Nesting
    assert "username" in get_icu_keys("""
        {gender, select,
            male {{username} is a boy}
            female {{username} is a girl}}
    """)

    # Return empty on error
    assert get_icu_keys("{{{") == set()
