from __future__ import absolute_import, unicode_literals

import transifex.native.consts as consts
from django.template import Library, Node, TemplateSyntaxError, Variable
from django.template.base import TOKEN_BLOCK, Variable
from django.template.defaulttags import token_kwargs
from django.utils.safestring import SafeData, mark_safe
from transifex.native.django import t
from transifex.native.parsing import SourceString

register = Library()

# These keys have special meaning and cannot be used as placeholders
# inside the source strings

TRANSLATE_TAG = 't'
TRANSLATE_TAG_END = 'endt'
TRANSLATE_TAG_UNESCAPED = 'ut'
TRANSLATE_TAG_UNESCAPED_END = 'endut'


def parse_translatable_tag(parser, token):
    """Parse the given `t`/`ut` token and return its information.

    If the token is not of {% t %} type, it returns (None, None).

    See `do_translate()` for more information about supported string structure.

    :param django.template.base.Parser parser: the parser object that holds
        information on the whole template document
    :param django.template.base.Token token: holds information on a
        specific line in the template
    :param str tag: the name of the tag, i.e. 't' or 'ut'
    :return: a node object with the necessary parameters for later rendering
        a specific part of the template document, or None if the given token
        is not a `t` tag
    :return: a tuple (SourceString, dict) with the full source string information
        and the necessary parameters for rendering it, or (None, None) if the given
        token is not a `t`/`ut` tag
    :rtype: tuple
    """
    # Split the given token into its parts (includes the template tag name)
    bits = token.split_contents()

    tag_name = bits[0]
    if tag_name not in (TRANSLATE_TAG, TRANSLATE_TAG_UNESCAPED):
        return None, None

    # See if this is a multi-line or a single-line block
    # Retrieve the next lines in the template until another block is found
    # or the document ends
    next_token = None
    tokens_processed = 0
    while parser.tokens:
        if len(parser.tokens) == tokens_processed:
            break
        next_token = parser.tokens[tokens_processed]
        tokens_processed += 1
        if next_token.token_type == TOKEN_BLOCK:
            break

    is_block = False
    string = None
    params = None

    end_tag_name = (
        TRANSLATE_TAG_END if tag_name == TRANSLATE_TAG
        else TRANSLATE_TAG_UNESCAPED_END
    )
    # If `next_token` is defined, it will be of type BLOCK
    # It could be an `endt`/`endut` or any other block
    if next_token:
        # Found an `endt`/`endut` block
        if next_token.contents.strip() == end_tag_name:
            # Get the multi-line string and use it as the source string
            # Note: parser.next_token() advances the cursor in the parser
            # and shifts one item from parser.tokens
            lines = []
            for _ in range(tokens_processed):
                # Content currently looks like "\nfirst_line\nsecond_line",
                # so remove the newline char from start and end
                lines.append(parser.next_token().contents.strip('\n'))
            lines = lines[:-1]  # remove the `endt`/`endut` text
            string = '\n'.join(lines)
            params = bits[1:]
            is_block = True

    # No `endt`/`endut` block was found, so this is a one-line tag
    if not is_block:
        if len(bits) < 2:
            raise TemplateSyntaxError(
                "One-line `{start}` blocks must include a string as their first "
                "parameter, whereas multi-line `{start}` blocks should end with their "
                "respective `{end}` tags".format(
                    start=tag_name, end=end_tag_name)
            )
        string = bits[1][1:-1]  # Remove the enclosing quotes
        params = bits[2:]

    # `support_legacy=False` means we only accept "key=value" format,
    # not "<value> as <key>"
    # Provide a copy of the `params` list, because it will be consumed internally
    values_by_key = token_kwargs(list(params), parser, support_legacy=False)

    string_context = values_by_key.get('_context')
    if string_context and isinstance(string_context.var, Variable):
        raise TemplateSyntaxError(
            "Context in `{start}` blocks can only be a string, not a variable, "
            "string='{string}...', tag parameters='{params}'".format(
                start=tag_name, string=string[:40], params=' '.join(params),
            )
        )
    string_context = string_context.var if string_context else None

    # Separate the reserved keys from the user-defined ones
    extra_context = {}
    meta = {}
    for key, value in values_by_key.items():
        if key in consts.ALL_KEYS:
            if key != consts.KEY_CONTEXT:  # context is already in a variable on its own
                # We don't need the overall context for resolving,
                # we just want string and int values to get unpacked
                # without any dynamic object fetching
                # Note: the `context` argument here is Django's
                #       and has nothing to do with Transifex Native `_context`
                meta[key] = value.resolve(context=None)
        else:
            extra_context[key] = value

    return SourceString(string, string_context, **meta), extra_context


@register.tag("t")
def do_translate(parser, token):
    """Translate a one-line string or block of text using TxNative.

    The source string supports ICU Message Format. The result is HTML-escaped.

    Usage::

    One-line string:
    {% t Hello %}
    {% t "Hello there" %}
    {% t "{cnt, plural, one {One file.} other {{cnt} files.}}" cnt=files|length %}

    Block:
    {% t total_guests=guests|length host="Jenny" guest="Jo" _context="sample" %}
      {total_guests, plural, offset:1
          =0 {{host} does not give a party.}
          =1 {{host} invites {guest} to her party.}
          =2 {{host} invites {guest} and one other person to her party.}
          other {{host} invites {guest} and # other people to her party.}
        }
      }
    {% endt %}

    where `_context` is used for providing additional context to the source string.

    :param django.template.base.Parser parser: the parser object that holds
        information on the whole template document
    :param django.template.base.Token token: holds information on a
        specific line in the template
    :return: a node object with the necessary parameters for later rendering
        a specific part of the template document, or None if the given token
        is not a `t` tag
    :rtype: TranslateNode
    """
    string_obj, extra_context = parse_translatable_tag(parser, token)
    return TranslateNode(
        string=string_obj.string,
        _context=string_obj.context,
        escape=True,
        extra_context=extra_context,
    )


@register.tag("ut")
def do_translate_unescaped(parser, token):
    """Translate a one-line string or block of text using TxNative, unescaped.

    The source string support ICU Message Format. The result is NOT HTML-escaped.

    See do_translate() for usage.

    :param django.template.base.Parser parser: the parser object that holds
        information on the whole template document
    :param django.template.base.Token token: holds information on a
        specific line in the template
    :return: a node object with the necessary parameters for later rendering
        a specific part of the template document, or None if the given token
        is not a `t` tag
    :rtype: TranslateNode
    """
    string_obj, extra_context = parse_translatable_tag(parser, token)
    return TranslateNode(
        string=string_obj.string,
        _context=string_obj.context,
        escape=False,
        extra_context=extra_context,
    )


class TranslateNode(Node):
    """A template node that uses TxNative to translate a source string to
    the current language."""

    def __init__(self, string, _context=None, escape=True, extra_context=None):
        """Constructor.

        :param unicode string: the source string
        :param unicode _context: an optional context that accompanies
            the source string
        :param bool escape: if True, the returned string will be HTML-escaped,
            otherwise it won't
        :param dict extra_context: additional parameters like values
            for variable placeholders
        """
        self.string = string
        self.context = _context
        self.extra_context = extra_context
        self.escape = escape

    def render(self, context):
        """Render the template tag into a string.

        :param django.template.context.RequestContext context: the full context
            to use for applying variables, filters etc in rendering
        :return: the final translation
        :rtype: unicode
        """
        # Resolve localization context e.g. key=value vars
        localization_context = {}
        for var, val in self.extra_context.items():
            localization_context[var] = val.resolve(context)
        context.update(localization_context)

        return t(
            self.string, _context=self.context, escape=self.escape, **localization_context
        )
