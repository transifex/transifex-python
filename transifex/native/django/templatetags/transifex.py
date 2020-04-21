from __future__ import absolute_import, unicode_literals

from copy import copy

import six
from django.conf import settings
from django.template import Library, Node, TemplateSyntaxError
from django.template.base import TOKEN_BLOCK, TOKEN_COMMENT, TOKEN_TEXT
from django.template.defaulttags import token_kwargs
from django.utils.html import escape as escape_html
from django.utils.safestring import EscapeData, SafeData, mark_safe
from django.utils.translation import get_language, to_locale
from transifex.native import tx
from transifex.native.parsing import SourceString

register = Library()


def do_t(parser, token):
    bits = list(token.split_contents())

    # {% t ... %}
    #    ^
    tag_name = bits.pop(0)

    # not {% t %}
    has_args = bool(bits)
    # {% t |escapejs ... %} ... {% endt %}
    first_arg_is_filter = has_args and bits[0].startswith('|')
    # {% t var=var ... %}
    first_arg_is_param = has_args and '=' in bits[0]
    # {% t as text %}
    first_arg_is_as = has_args and bits[0] == "as"

    is_block = (not has_args or
                first_arg_is_filter or
                first_arg_is_param or
                first_arg_is_as)

    params = {}
    if not is_block:
        source_string = parser.compile_filter(bits.pop(0))
    else:
        block_tokens = []
        if parser.tokens and parser.tokens[0].token_type == TOKEN_COMMENT:
            # {% t ... %}{# comment #} ... {% endt %}
            params['_comment'] = parser.next_token().contents
        while parser.tokens:
            token = parser.tokens[0]
            if token.token_type == TOKEN_TEXT:
                block_tokens.append(parser.next_token())
            else:
                if (token.token_type == TOKEN_BLOCK and
                        token.split_contents()[0] == "end{}".format(tag_name)):
                    parser.delete_first_token()
                    break
                raise TemplateSyntaxError(
                    "No template tags allowed within a '{}' block".
                    format(tag_name)
                )
        block = ''.join((token.contents for token in block_tokens))
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
    params.update(token_kwargs(params_list, parser, support_legacy=False))

    # {% t "string" as var %}
    #               ^^^^^^
    asvar = None
    if bits:
        if len(bits) != 2 or bits[0] != "as":
            raise TemplateSyntaxError("Unrecognized tail: {}".
                                      format(' '.join(bits)))
        else:
            asvar = bits[1]

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
        if isinstance(self.source_string.var, six.string_types):
            source_icu_template = self.source_string.var
        else:
            safe_context = copy(context)
            safe_context.autoescape = False
            source_icu_template = self.source_string.var.resolve(safe_context)

        params = context.flatten()
        params.update({key: value.resolve(context)
                       for key, value in self.params.items()})
        for key, value in list(params.items()):
            should_escape = (
                isinstance(value, six.string_types) and
                ((context.autoescape and not isinstance(value, SafeData)) or
                 (not context.autoescape and isinstance(value, EscapeData)))
            )
            if should_escape:
                params[key] = escape_html(value)

        is_source = get_language() == settings.LANGUAGE_CODE
        locale = to_locale(get_language())  # e.g. from en-us to en_US
        translation_icu_template = tx.get_translation(
            source_icu_template, locale, params.get('_context', None),
            is_source,
        )
        if translation_icu_template is None:
            translation_icu_template = source_icu_template
        if self.tag_name == "t":
            translation_icu_template = escape_html(translation_icu_template)

        result = tx.render_translation(translation_icu_template, params,
                                       source_icu_template, locale,
                                       escape=False)

        self.source_string.var = mark_safe(result)
        result = self.source_string.resolve(context)

        if self.asvar is not None:
            context[self.asvar] = result
            return ""
        else:
            return result

    def _to_source_string(self):
        if not isinstance(self.source_string.var, six.string_types):
            return None
        meta = {}
        for key, value in self.params.items():
            if len(value.filters) != 0:
                continue
            if isinstance(value.var, six.string_types):
                meta[key] = value.var
            elif getattr(value.var, 'literal', None) is not None:
                meta[key] = value.var.literal
        _context = meta.pop('_context', None)
        return SourceString(self.source_string.var, _context, **meta)


@register.filter
def trimmed(value):
    return ' '.join((line.strip()
                     for line in value.splitlines()
                     if line.strip()))
