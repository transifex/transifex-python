from __future__ import unicode_literals

from django.template.base import Lexer, Parser
from django.utils.encoding import force_text
from transifex.common._compat import string_types
from transifex.native.django.compat import TOKEN_BLOCK
from transifex.native.django.templatetags.transifex import do_t
from transifex.native.parsing import SourceString

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


# hack to make the identity function
# signature compatible to all template filters
def identity(obj, var1=None, var2=None, var3=None, var4=None, var5=None):  # pragma no cover
    return obj  # pragma no cover


def find_filter_identity(filter_name):
    """Return a filter that does no filtering, i.e always returns all items.

    This function supposedly returns a filter object, which in this case
    does nothing other than returning the variable as is.

    :param str filter_name:
    :return: a callable that represents a filter that does not filtering
    :rtype: callable
    """
    return identity


def tnode_to_source_string(tnode):
    """ Convert a parsed TNode to a SourceString instance.

        TNode is what the template tag implementation will return having
        processed the contents from the template. A SourceString is a data
        object which exposes information in a useful way for pushing to
        transifex.
    """
    if not isinstance(tnode.source_string.var, string_types):
        return None
    meta = {}
    for key, value in tnode.params.items():
        if len(value.filters) != 0:
            continue
        if isinstance(value.var, string_types):
            meta[key] = value.var
        elif getattr(value.var, 'literal', None) is not None:
            meta[key] = value.var.literal
    _context = meta.pop('_context', None)
    return SourceString(tnode.source_string.var, _context, **meta)


def extract_transifex_template_strings(src, origin=None, charset='utf-8'):
    """Parse the given template and extract translatable content
    based on the syntax supported by Transifex Native.

    Supports the {% t %} and {% ut %} template tags.

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
    # of the Parser class. The overridden function returns the object as given.
    # Without the override, a KeyError is raised inside the parser.
    parser.find_filter = find_filter_identity

    strings = []
    while parser.tokens:
        token = parser.next_token()
        if (token.token_type == TOKEN_BLOCK and
                token.split_contents()[0] in ('t', 'ut')):
            tnode = do_t(parser, token)
            source_string = tnode_to_source_string(tnode)
            if source_string is None:
                continue
            if token.lineno and origin:
                source_string.occurrences = [
                    "{}:{}".format(origin, token.lineno)]

            strings.append(source_string)

    return strings
