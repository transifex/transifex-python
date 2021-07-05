from __future__ import absolute_import, unicode_literals

from copy import copy

from django.conf import settings
from django.template import Library, Node, TemplateSyntaxError
from django.template.base import (BLOCK_TAG_END, BLOCK_TAG_START,
                                  COMMENT_TAG_END, COMMENT_TAG_START,
                                  VARIABLE_TAG_END, VARIABLE_TAG_START)
from django.template.defaulttags import token_kwargs
from django.utils.html import escape as escape_html
from django.utils.safestring import SafeData, mark_safe
from django.utils.translation import get_language, to_locale
from transifex.common._compat import string_types
from transifex.native import tx
from transifex.native.django.compat import (TOKEN_BLOCK, TOKEN_COMMENT,
                                            TOKEN_TEXT, TOKEN_VAR)

from .utils import get_icu_keys

try:
    from django.utils.safestring import EscapeData
except ImportError:
    class EscapeData(object):
        pass


register = Library()


def do_t(parser, token):
    """ Parse a transifex translation tag.

        Inline syntax:
          {% t/ut <source>[|filter...] [key=param[|filter...]...] [as <var>] %}

          <source> can either be a literal string or a variable containing a
          string. In each case, the string will be considered an ICU template
          whose parameters will be rendered against the parameters of the tag
          and the context of the template.

        Block syntax:
          {% t/ut [|filter...] [key=param[|filter...]...] [as <var>] %}
            <source>
          {% endt/ut %}

          <source> can be anything. Django template tokens will not be parsed,
          but captured verbatim (which will most likely mess up with ICU
          formatting).

        Arguments:

        :param parser: A django Parser object. Has information about how the
                       templating engine is setup, what filters and tags are
                       available and the tokens that haven't yet been processed

        :param token:  A django Token instance. Has information about the
                       contents of the token we are currently processing
    """

    # We will gradually "consume" bits left-to-right. At any given moment, the
    # leftmost bit is the one we need to be processing
    bits = list(token.split_contents())

    # {% t ... %}
    #    ^
    tag_name = bits.pop(0)

    # not {% t %}
    has_args = bool(bits)
    # {% t |escapejs ... %} ... {% endt %}
    first_arg_is_filter = has_args and bits[0].startswith('|')
    # {% t "hello world" ... %}
    first_arg_is_string_literal = (has_args and
                                   bits[0][0] in ('"', "'") and
                                   bits[0][0] == bits[0][-1])
    # {% t var=var ... %}
    first_arg_is_param = (has_args and
                          not first_arg_is_string_literal and
                          '=' in bits[0])
    # {% t as text %}
    first_arg_is_as = has_args and bits[0] == "as"

    is_block = (not has_args or
                first_arg_is_filter or
                first_arg_is_param or
                first_arg_is_as)

    if not is_block:
        # Treat the source string as a full filter expression. Proper
        # exceptions will be raised if it is not formatted properly
        source_string = parser.compile_filter(bits.pop(0))
    else:
        block = []
        while True:
            try:
                # `next_token` removes the first token from the parser's list
                token = parser.next_token()
            except IndexError:
                # We ran out of tokens
                raise TemplateSyntaxError("'{tag_name}' tag not closed with "
                                          "'end{tag_name}'".
                                          format(tag_name=tag_name))
            if (token.token_type == TOKEN_BLOCK and
                    token.contents == "end{}".format(tag_name)):
                break

            # Here we capture the contents of the block verbatim.
            # Unfortunately, there is some loss of information here: When
            # django captures a token, it saves the content as
            # `text[2:-2].strip()`, which means that the size of the
            # surrounding spaces is lost. This means that we end up capturing
            # `{%     tag%}` as `{% tag %}`
            if token.token_type == TOKEN_VAR:
                block.append(''.join((VARIABLE_TAG_START, ' ', token.contents,
                                      ' ', VARIABLE_TAG_END)))
            elif token.token_type == TOKEN_BLOCK:
                block.append(''.join((BLOCK_TAG_START, ' ', token.contents,
                                      ' ', BLOCK_TAG_END)))
            elif token.token_type == TOKEN_COMMENT and token.contents:
                block.append(''.join((COMMENT_TAG_START, ' ', token.contents,
                                      ' ', COMMENT_TAG_END)))
            elif token.token_type == TOKEN_TEXT:
                block.append(token.contents)
            else:  # pragma: no cover
                # Unreachable code
                raise TemplateSyntaxError("Could not parse body of '{}' tag "
                                          "block".format(tag_name))
        block = ''.join(block)

        # Create a dummy filter expression with the provided filters and then
        # replace its 'var' attribute with the captured text. This effectively
        # makes
        # `{% t %}text{% endt %}` equivalent to `{% t "text" %}` and
        # `{% t |filter %}text{% endt %}` equivalent to `{% t "text"|filter %}`
        # while allowing the text to contain characters that would be invalid
        # with the inline syntax, like newlines and `"`
        if first_arg_is_filter:
            source_string = parser.compile_filter('""' + bits.pop(0))
        else:
            source_string = parser.compile_filter('""')
        source_string.var = block

    # {% t "string" var=value var2=value2 ... %}
    #               ^^^^^^^^^
    params_list = []
    while bits and '=' in bits[0]:
        params_list.append(bits.pop(0))
    # Proper exceptions will be raised if the params are not formatted properly
    params = token_kwargs(params_list, parser, support_legacy=False)

    # {% t "string" as var %}
    #               ^^^^^^
    asvar = None
    if bits:
        if len(bits) != 2 or bits[0] != "as":
            raise TemplateSyntaxError("Unrecognized tail: {}".
                                      format(' '.join(bits)))
        else:
            asvar = bits[1]
            del bits[:2]

    if bits:
        raise TemplateSyntaxError("Unrecognized tail: {}".
                                  format(' '.join(bits)))

    return TNode(tag_name, source_string, params, asvar)


register.tag('t')(do_t)
register.tag('ut')(do_t)


class TNode(Node):
    def __init__(self, tag_name, source_string, params, asvar):
        self.tag_name = tag_name
        self.source_string = source_string
        self.params = params
        self.asvar = asvar

    def render(self, context):
        if isinstance(self.source_string.var, string_types):
            # Tag had a string literal or used block syntax
            source_icu_template = self.source_string.var
        else:
            # We resolve the *variable* of the filter expression, not the
            # expression itself, because we want to apply the filters to the
            # *translation* afterwards. Also, we use autoescape=False in order
            # to ignore django's attempts to escape the source string at this
            # point because we want to use the raw string to look for a
            # translation
            safe_context = copy(context)
            safe_context.autoescape = False
            source_icu_template = self.source_string.var.resolve(safe_context)

        # The values of self.params are filter expressions that can be resolved
        params = {key: value.resolve(context)
                  for key, value in self.params.items()}

        # Perform the translation in two steps: First, we get the translation
        # ICU template. Then we perform ICU rendering against 'params'.
        # In between the two steps, if the tag used was 't' and not 'ut', we
        # perform escaping on the ICU template.
        is_source = get_language() == settings.LANGUAGE_CODE
        locale = to_locale(get_language())  # e.g. from en-us to en_US
        translation_icu_template = tx.get_translation(
            source_string=source_icu_template,
            language_code=locale,
            _context=params.get('_context', None),
            is_source=is_source,
            _key=params.get('_key', None),
        )

        # The ICU template can compile against explicitly passed params as well
        # as any context variable. In order to avoid passing and potentially
        # escaping *every* variable in the context for optimization reasons, we
        # need to filter down to the ones that the ICU template will actually
        # need
        keys = get_icu_keys(source_icu_template)
        if translation_icu_template is not None:
            keys.update(get_icu_keys(translation_icu_template))
        for key in keys:
            if key in params:
                continue
            try:
                params[key] = context[key]
            except KeyError:
                pass

        for key, value in params.items():
            # Django doesn't escape strings until the last moment. For now,
            # escaped strings are "marked" as escaped, using the EscapeData
            # class. Because the low-level transifex toolkit doesn't know about
            # django's escape marking, we perform the escaping manually, if
            # needed.
            should_escape = (
                isinstance(value, string_types) and
                ((context.autoescape and not isinstance(value, SafeData)) or
                 (not context.autoescape and isinstance(value, EscapeData)))
            )
            if should_escape:
                params[key] = escape_html(value)

        if self.tag_name == "t":
            source_icu_template = escape_html(source_icu_template)
            if translation_icu_template is not None:
                translation_icu_template = escape_html(
                    translation_icu_template
                )

        result = tx.render_translation(translation_icu_template, params,
                                       source_icu_template, locale,
                                       escape=False)

        # `self` is not supposed to mutate between invocations of `render`
        # because Django may parse the template once per thread and reuse the
        # nodes between renders ("parse" = "process text into nodes"). To that
        # end, let's safekeep the old value of `self.source_string.var` to put
        # it back in place before returning from render.
        # https://docs.djangoproject.com/en/1.11/howto/custom-template-tags/#thread-safety-considerations  # noqa
        old_source_string_var = self.source_string.var

        # Now we resolve the full source filter expression, after having
        # replaced its text with the outcome of the translation, in order to
        # apply the expression's filters to the translation. The translation is
        # marked as safe in order to prevent further escaping attempts that
        # would introduce the danger of double escaping (eg `<` => `&amp;lt;`)
        self.source_string.var = mark_safe(result)
        result = self.source_string.resolve(context)
        self.source_string.var = old_source_string_var

        if self.asvar is not None:
            # Save the translation outcome to a context variable
            context[self.asvar] = result
            return ""
        else:
            return result


@register.filter
def trimmed(value):
    """ Join a multiline string into a single line

            '\n\n  one\ntwo\n\n  three\n  \n   ' => 'one two three'
    """

    return ' '.join((line.strip()
                     for line in value.splitlines()
                     if line.strip()))
