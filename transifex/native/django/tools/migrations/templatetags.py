"""Contains code used to migrate Django i18n syntax to Transifex Native syntax.

For Django syntax see:
https://docs.djangoproject.com/en/1.11/topics/i18n/translation/
"""

from __future__ import unicode_literals

from django.template.base import (TOKEN_BLOCK, TOKEN_COMMENT, TOKEN_TEXT,
                                  TOKEN_VAR, TRANSLATOR_COMMENT_MARK,
                                  DebugLexer, Lexer, Parser)
from django.template.defaulttags import token_kwargs
from django.templatetags.i18n import do_block_translate, do_translate
from django.utils.encoding import force_text
from django.utils.translation import trim_whitespace
from transifex.native.django.utils import templates
from transifex.native.django.utils.templates import find_filter_identity
from transifex.native.tools.migrations.models import (Confidence,
                                                      FileMigration,
                                                      StringMigration)

COMMENT_FOUND = object()


def _render_native(str_format, content, params):
    """Return a string with syntax compatible to Transifex Native template
    tags.

    The given `params` will be serialized and will be added to the final
    string, together with `content`, using specific placeholders
    ('__tx_native_content__' and '__tx_native_params__').

    Usage:
    >>> _render_native(
    >>>     '{% t __tx_native_content__ __tx_native_params__%}',
    >>>     '"Call {name} at {phone_num}"',
    >>>     {'username': 'john', 'phone_num': '(650) 111-1111'}
    >>> )
    <<< {% t "Call {name} at {phone_num}" username="john" phone_num="(650) 111-1111" %}

    This function does not know anything else about how to structure the
    template tag, so the caller needs to provide a suitable and valid
    `str_format`.

    :param unicode str_format: the structure of the template tag,
        as described above
    :param unicode content: the actual translatable content, that will
        replace the `__tx_native_content__` placeholder inside `str_format`
    :param dict params: a dictionary with parameters, that will
        replace the `__tx_native_params__` placeholder inside `str_format`
    :return: a new string that follows Transifex Native syntax for template
        tags
    :rtype: unicode
    """
    rendered_params = {}
    for key, value in params.items():
        if value and value != COMMENT_FOUND:
            rendered_params[key] = value

    serialized_params = ' '.join(
        sorted([
            '{key}={value}'.format(key=key, value=value)
            for key, value in rendered_params.items()
        ])
    )
    return str_format.replace(
        '__tx_native_content__', content
    ).replace(
        '__tx_native_params__',
        ('{} ' if serialized_params else '{}').format(serialized_params)
    )


def _make_plural(singular, plural, count_var):
    """Create a pluralized string representation, compatible with ICU
    message format.

    Usage:
    >>> _make_plural('{msg} message found', '{msg} messages found', 'msg')
    <<< '{msg, plural, one {{msg} message found} other {{msg} messages found}}'

    :param unicode singular: the translatable content for plural=one
    :param unicode plural: the translatable content for plural=other
    :param str count_var: the name of the count variable used in ICU;
        needs to be identical to any related placeholder inside `singular`
        and `plural`
    :return: a new string that uses both plural forms with ICU syntax
    :rtype: unicode
    """
    if plural:
        # Using '%' syntax of formatting because the various braces
        # in the format would confuse the `'...'.format()` syntax
        return '\n{%s, plural, one {%s} other {%s}}\n' % (
            count_var, singular, plural
        )

    return singular


def _get_variable_names(token_list):
    """Get a list of all unique variable names found in the given tokens.

    Usage:
    >>> # assume tokens was created by parsing the following string:
    >>> # 'This is a {{ var }} and this is {{ another_var }}'
    >>> _get_variable_names(tokens)
    <<< ['var', 'another_var']

    :param list token_list: a list of Token objects
    :return: a list of the names of all variables found
    :rtype: list
    """
    variables = set()
    for token in token_list:
        if token.token_type == TOKEN_VAR:
            variables.add(token.contents)
    return list(variables)


def _render_var_tokens(token_list):
    """Serialize the given token list, creating Transifex Native syntax,
    while properly transforming variable placeholders.

    Example:
    >>> src = "The following events were found:" +
    >>>       " 1. {{ first }}" +
    >>>       " 2. {{ second }}" +
    >>>       " 3. {{ third }}" +
    >>>       "And this is {{ another }}."
    >>> tokens = DebugLexer(src).tokenize()
    >>> _render_var_tokens(tokens)
    Returns:
        The following events were found:
          1. {first}
          2. {second}
          3. {third}
        And this is {another}.

    :param list token_list: a list of Token objects
    :return: a serialize string with proper Transifex Native format
    :rtype: unicode
    """
    return ''.join(
        [
            (
                '{var}'.replace('var', token.contents)
                if token.token_type == TOKEN_VAR
                else token.contents
            )
            for token in token_list
        ]
    )


def _retrieve_comment(token_contents):
    """Retrieve the developer comment from the given string.

    Usage:
    >>> _retrieve_comment('Translators: This is a great comment')
    <<< 'This is a great comment'
    >>> _retrieve_comment('This is not actually a Django i18n comment')
    <<< None

    :param unicode token_contents: a string
    :return: the actual comment, or None if the given string does not
        follow the proper Django i18n syntax for comments
    :rtype: unicode
    """
    mark = '{}:'.format(TRANSLATOR_COMMENT_MARK)
    if token_contents.startswith(mark):
        return '"{}"'.format(token_contents.replace(mark, '').strip())


class DjangoTagMigrationBuilder(object):
    """Parses Django templates and creates test_migrations for each template.

    A migration is an object that describes the changes that need to be made
    in order to change a template file that uses the Django i18n syntax
    to a file that uses the Transifex Native syntax.

    This class is stateful, but it can be reused. The reason it is created
    this way is for optimization, i.e. for not having to create new instances
    of the class for each migrated file.
    """

    def __init__(self):
        self._reset()

    def _reset(self):
        """Reset some state parameters, so that a new migration can be created.

        The reason this method exists is for optimization, i.e. not having
        to create new instances of the class for each file.
        """
        # Each entry is a dictionary with var_name/var_value items,
        # each representing a {% with var_name=var_value %} tag.
        # Since {% with %} tags can be nested, this list is LIFO.
        self._with_kwargs = []

        # The current (developer) comment that was parsed, if any
        # Comments in Django templates preceed the actual string token,
        # so when we find one we need to keep it aside in order to use it
        # when we parse the actual translatable string
        self._comment = None
        self._current_string_migration = None

        # Sometimes, like when a comment is available, we cannot parse
        # a translatable string in one go, so we need to create
        # a StringMigration object and amend it as soon as we have all its
        # information.
        self._current_string_migration = None

    def build_migration(self, src, filename=None, charset='utf-8'):
        """Create a migration for a Django template file to Transifex Native syntax.

        The returned object contains every change separately, so that
        it can be reviewed string by string.

        :param unicode src: the whole Django template
        :param str filename: the filename of the original template
        :param str charset: the character set to use
        :return: a FileMigration instance
        :rtype: FileMigration
        """
        self._reset()

        src = force_text(src, charset)
        # Using the DebugLexer because we need the positional information
        # of each token (start/end pos). It is slower than Lexer, but Lexer
        # doesn't provide that information
        tokens = DebugLexer(src).tokenize()
        parser = Parser(tokens, libraries={}, builtins=[], origin=filename)

        # Since no template libraries are loaded when this code is running,
        # we need to override the find function in order to use the functionality
        # of the Parser class. The overridden function returns the object as given.
        # Without the override, a KeyError would be raised inside the parser.
        parser.find_filter = find_filter_identity

        # Create a migration object for this template; we'll add stuff to it
        # as we go
        migration = FileMigration(filename, src)
        while parser.tokens:
            token = parser.next_token()
            start, end = token.position

            # Parse the current token. This may or may not return a migration.
            # Also it may return a list of tokens that were consumed,
            # additionally to the current token. If this happens, `_parse_token()`
            # will have made sure that `parser` has moved forward, consuming those
            # tokens, so that they don't appear again in the while loop.
            string_migration, extra_consumed_tokens = self._parse_token(
                token, parser, original_string=src[start:end]
            )
            if not string_migration:
                continue

            # If additional tokens were consumed, we need to add
            # them in the migration, so that the StringMigration object
            # includes the information of what part of the original template
            # was migrated to the new syntax, for this particular translatable
            # string
            if extra_consumed_tokens:
                for extra_token in extra_consumed_tokens:
                    start, end = extra_token.position
                    string_migration.update(src[start:end], '')

            migration.add_string(string_migration)

        return migration

    def _parse_token(self, token, parser, original_string):
        """Parse the given token and create a migration object for a particular
        substring of the whole template code.

        :param django.template.base.Token token: holds information on a
            specific line in the template, e.g. contains 'trans "A string"'
        :param django.template.base.Parser parser: the parser object that holds
            information on the whole template document
        :param unicode original_string: the full string matched in the template,
            e.g. '{% trans "A string" %}'

        :return: a StringMigration object that contains information about
            the Django and Transifex Native syntax of a specific set of strings
            matched in the template
        :rtype: StringMigration
        """
        # Simple text found
        if token.token_type == TOKEN_TEXT:
            return self._parse_text(token, original_string)

        # A comment tag was found, so we need to retrieve the comment text
        # e.g. {# Translators: Do this and that #}
        elif token.token_type == TOKEN_COMMENT:
            self._comment = _retrieve_comment(token.contents)
            self._current_string_migration = StringMigration(
                original_string, '')
            return None, None

        # A variable was found; copy as is
        elif token.token_type == TOKEN_VAR:
            return StringMigration(original_string, original_string), None

        return self._parse_block(token, parser, original_string)

    def _parse_text(self, token, original_string):
        """Parse a text token and return a migration object.

        Text tokens are those that are not inside special syntax.
        For example in the following template:
            '''
            <a href="...">Link</a>

            {% anytag %}Some text{% endanytag %}
            '''
        there are 2 text tokens:
         - '<a href="...">Link</a>\n\n'
         - 'Some text'

        :param django.template.base.token: the token object
        :param unicode original_string: the string found in the template
        :return: a tuple containing a StringMigration instance, if applicable,
            and a list of extra tokens that were consumed
        :rtype: Tuple[StringMigration, List[Token]]
        """
        # If the previous tag was an opening {% comment %} tag,
        # and now we have the text inside, e.g.
        # {% comment %}My comment{% endcomment %}
        #  we're here: ^--------^
        # so now we need to retrieve the actual comment
        if self._comment == COMMENT_FOUND:
            self._comment = _retrieve_comment(token.contents)

            # Make sure to record that the tag is removed from the migrated result
            if self._current_string_migration:
                self._current_string_migration.update(original_string, '')
            return None, None
        # In any other case, just copy the content as is
        else:
            # String migration was already open, make sure to record
            # that the tag is removed from the migrated result
            if self._current_string_migration:
                self._current_string_migration.update(
                    original_string, original_string)
                return None, None
            # No open string migration, return a new one
            else:
                return StringMigration(original_string, original_string), None

    def _parse_block(self, token, parser, original_string):
        """Parse any {% ... %} token and return a migration object.

        :param django.template.base.Token token: the token object
        :param django.template.base.parser: the parser object
        :param unicode original_string: the string found in the template
        """
        # Split the given token into its parts (includes the template tag name),
        # e.g. "{% trans "This is the title" context "Some context" %}" returns:
        # ['trans', '"This is the title"', 'context', '"Some context"']
        bits = token.split_contents()

        tag_name = bits[0]

        # Right after {% load i18n %} append a {% load transifex %} tag
        if tag_name == templates.LOAD_TAG and bits[1] == templates.DJANGO_i18n_TAG_NAME:
            # Make sure there is not already a tag that loads "transifex"
            # by checking all remaining nodes
            for t in parser.tokens:
                if (
                    templates.LOAD_TAG in t.contents
                    and templates.TRANSIFEX_TAG_NAME in t.contents
                ):
                    return StringMigration(original_string, original_string), None

            string_migration = StringMigration(
                original_string,
                'original\n{% load transifex %}'.replace(
                    'original', original_string
                ),
            )
            return string_migration, None

        # A {% with %} tag was found
        elif tag_name == templates.WITH_TAG:
            with_kwargs = token_kwargs(
                bits[1:], parser, support_legacy=True
            )
            self._with_kwargs.append(
                {k: v.var for k, v in with_kwargs.items()})
        # An {% endwith %} tag was found
        elif tag_name == templates.ENDWITH_TAG:
            self._with_kwargs.pop()

        # A {% comment %} tag was found; expect the actual
        # comment text to follow shortly
        elif tag_name == templates.COMMENT_TAG:
            self._comment = COMMENT_FOUND
            # Create a string migration and start keeping track
            # of all the strings that will be migrated
            # within the following set of tokens that apply
            self._current_string_migration = StringMigration(
                original_string, '')
            return None, None
        # An {% endcomment %} tag was found; no need to do anything special,
        # just make sure to record that the tag is removed from the migrated result
        elif tag_name == templates.ENDCOMMENT_TAG:
            if self._current_string_migration:
                self._current_string_migration.update(original_string, '')
            return None, None

        # A {% trans %} tag was found
        elif tag_name in templates.TRANSLATE_TAGS:
            return self._parse_trans(token, parser, original_string)

        # A {% blocktrans %} tag was found
        elif tag_name in templates.BLOCK_TRANSLATE_TAGS:
            return self._parse_blocktrans(token, parser, original_string)

        # This is the default case; any other block tag that wasn't
        # explicitly covered above, which means that it doesn't need migration
        return StringMigration(original_string, original_string), None

    def _parse_trans(self, token, parser, original_string):
        """Parse a {% trans %} token and return a migration object.

        :param django.template.base.Token token: the token object
        :param django.template.base.parser: the parser object
        :param unicode original_string: the string found in the template
        """
        # Use Django's do_translate() method to parse the token
        trans_node = do_translate(parser, token)

        message_context = trans_node.message_context
        text = trans_node.filter_expression.var.literal
        # {% trans "Some text" %}
        if text:
            text = '"{}"'.format(text)
        # {% trans some_var %}
        else:
            # Our SDK currently does not support variables outside strings,
            # but we can simulate the same behavior using a placeholder
            text = '"{var}" var=var'.replace(
                'var', trans_node.filter_expression.var.var
            )

        params = {
            '_context': message_context,
            '_comment': self._comment,
        }

        # Reset the stored comment, so that it doesn't leak to the next token
        self._comment = None

        return self._final_string_migration(
            original_string,
            _render_native(
                '{% t __tx_native_content__ __tx_native_params__%}',
                text,
                params,
            ),
        )

    def _parse_blocktrans(self, token, parser, original_string):
        """Parse a {% blocktrans %} token and return a migration object.

        :param django.template.base.Token token: the token object
        :param django.template.base.parser: the parser object
        :param unicode original_string: the string found in the template
        """
        # Use Django's blocktranslate tag function to actually parse
        # the whole tag, so that we easily get all information
        # Internally, the do_block_translate() call will make the parser
        # go forward, so the call to parser.next_token() will skip
        # all tokens until {% endblocktrans %} (inclusive).
        consumed_tokens = []
        for t in parser.tokens:  # these are just the remaining tokens
            consumed_tokens.append(t)
            if t.contents in templates.ENDBLOCK_TRANSLATE_TAGS:
                break  # we assume there will be a {% endblocktrans %} token

        blocktrans_node = do_block_translate(parser, token)

        message_context = blocktrans_node.message_context
        singular_text = _render_var_tokens(blocktrans_node.singular)
        plural_text = _render_var_tokens(blocktrans_node.plural)

        # Support the "trimmed" option of {% blocktrans %}
        if blocktrans_node.trimmed:
            singular_text = trim_whitespace(singular_text)
            plural_text = trim_whitespace(plural_text)

        # Start building the parameters supported by Transifex Native
        params = {
            '_context': message_context,
            '_comment': self._comment,
        }

        # Plural support in Django works by using the "count" keyword
        counter_var = blocktrans_node.countervar
        if blocktrans_node.countervar:
            params[counter_var] = blocktrans_node.counter.token

        # Add any key/value pairs that hold placeholder/variable information
        # e.g. {% blocktrans user.name as username %}
        params.update({
            key: value.token
            for key, value in blocktrans_node.extra_context.items()
        })

        # Retrieve any variables inside text, e.g.
        # "This is a {{ var }} and this is {{ another_var }}"
        variables_in_text = (
            _get_variable_names(blocktrans_node.singular) +
            _get_variable_names(blocktrans_node.plural)
        )
        for variable in variables_in_text:
            params.setdefault(variable, variable)

        # Reset the stored comment, so that it doesn't leak to the next token
        self._comment = None

        # Build the template of the tag for Transifex Native syntax
        is_multiline = '\n' in singular_text or plural_text
        block_format = (
            '{% t __tx_native_params__%}__tx_native_content__{% endt %}'
            if is_multiline
            else '{% t "__tx_native_content__" __tx_native_params__%}'
        )
        # Determine the confidence of the migration
        confidence = Confidence.HIGH if not variables_in_text else Confidence.LOW

        # Create the actual migration
        return self._final_string_migration(
            original_string,
            _render_native(
                block_format,
                _make_plural(singular_text, plural_text, counter_var),
                params,
            ),
            consumed_tokens=consumed_tokens,
            confidence=confidence
        )

    def _final_string_migration(
        self,
        original_string,
        new_string,
        confidence=Confidence.HIGH,
        consumed_tokens=None,
    ):
        """Create a migration object, taking into account any open comments.

        :param unicode original_string:
        :param unicode new_string:
        :param int confidence: the confidence level of the migration
        :param List[Token] consumed_tokens: a list of extra tokens that were
            consumed for this migration; e.g. in a {% blocktrans %} token
            it will contain all text inside this up to {% endblocktrans %}
        """
        consumed_tokens = consumed_tokens or []
        if self._current_string_migration:
            self._current_string_migration.update(original_string, new_string)
            string_migration = self._current_string_migration
            self._current_string_migration = None
            return string_migration, consumed_tokens

        return (
            StringMigration(original_string, new_string,
                            confidence=confidence),
            consumed_tokens
        )
