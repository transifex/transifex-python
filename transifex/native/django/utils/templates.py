from __future__ import unicode_literals

from django.template.base import (TOKEN_BLOCK, TOKEN_COMMENT, TOKEN_TEXT,
                                  TOKEN_VAR, TRANSLATOR_COMMENT_MARK,
                                  DebugLexer, Lexer, Parser)
from django.utils.encoding import force_text
from transifex.native.django.templatetags.transifex import \
    parse_translatable_tag

# Django template consts
LOAD_TAG = 'load'
WITH_TAG = 'with'
ENDWITH_TAG = 'endwith'
COMMENT_TAG = 'comment'
ENDCOMMENT_TAG = 'endcomment'
TRANSLATE_TAGS = ['trans', 'translate']
BLOCK_TRANSLATE_TAGS = ['blocktrans', 'blocktranslate']
ENDBLOCK_TRANSLATE_TAGS = ['endblocktrans', 'endblocktranslate']
DJANGO_i18n_TAG_NAME = 'i18n'
TRANSIFEX_TAG_NAME = 'transifex'
COMMENT_FOUND = object()
COPY_AS_IS = object()


def find_filter_identity(filter_name):
    """Return a filter that does no filtering, i.e always returns all items.

    This function supposedly returns a filter object, which in this case
    does nothing other than returning the variable as is.

    :param str filter_name:
    :return: a callable that represents a filter that does not filtering
    :rtype: callable
    """
    return lambda obj: obj


def extract_transifex_template_strings(src, origin=None, charset='utf-8'):
    """Parse the given template and extract translatable content
    based on the syntax supported by Transifex Native.

    Supports the {% t %} template tags.

    :param unicode src: the whole Django template
    :param str origin: an optional context for the filename of the source,
        e.g. the file name
    :param str charset: the character set to use
    :return: a list of SourceString objects
    :rtype: list
    """
    src = force_text(src, charset)
    tokens = Lexer(src).tokenize()
    parser = Parser(tokens, {}, [], origin)
    # Since no template libraries are loaded when this code is running,
    # we need to override the find function in order to use the functionality
    # of the Parser class. The overriden function returns the object as given.
    # Without the override, a KeyError is raised inside the parser.
    parser.find_filter = find_filter_identity

    strings = []
    while parser.tokens:
        token = parser.next_token()
        if token.token_type == TOKEN_BLOCK:
            source_string, _ = parse_translatable_tag(parser, token)
            if source_string is None:
                continue

            strings.append(source_string)

    return strings
