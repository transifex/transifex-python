from __future__ import unicode_literals

import ast

import asttokens
from transifex.common.console import Color
from transifex.common.strings import (VAR_FORMAT, alt_quote,
                                      printf_to_format_style)
from transifex.native.consts import KEY_CONTEXT
from transifex.native.parsing import (ENCODING_PATTERN, CallDetectionVisitor,
                                      get_func_parts)
from transifex.native.tools.migrations.mark import MARK_ARGUMENT_FIXME
from transifex.native.tools.migrations.models import (Confidence,
                                                      FileMigration,
                                                      StringMigration)

# Simple string
GETTEXT = 'get'
UGETTEXT = 'uget'

# Pluralized string
NGETTEXT = 'nget'
UNGETTEXT = 'unget'

# String with context
PGETTEXT = 'pget'

# Pluralized string with context
NPGETTEXT = 'npget'

LAZY_SUFFIX = '_lazy'

# Lazy variants
GETTEXT_LAZY = GETTEXT + LAZY_SUFFIX
UGETTEXT_LAZY = UGETTEXT + LAZY_SUFFIX
NGETTEXT_LAZY = NGETTEXT + LAZY_SUFFIX
UNGETTEXT_LAZY = UNGETTEXT + LAZY_SUFFIX
PGETTEXT_LAZY = PGETTEXT + LAZY_SUFFIX
NPGETTEXT_LAZY = NPGETTEXT + LAZY_SUFFIX

LAZY_MAPPING = {
    GETTEXT: GETTEXT_LAZY,
    UGETTEXT: UGETTEXT_LAZY,
    NGETTEXT: NGETTEXT_LAZY,
    UNGETTEXT: UNGETTEXT_LAZY,
    PGETTEXT: PGETTEXT_LAZY,
    NPGETTEXT: NPGETTEXT_LAZY,
}

KEYWORD_STRING = 'string'
KEYWORD_CONTEXT = 'context'
KEYWORD_ONE = 'one'
KEYWORD_OTHER = 'other'
KEYWORD_CNT = 'cnt'

ICU_PLURAL_COUNTER = 'cnt'


class GettextMethods(object):
    """Configuration class that holds paths to gettext wrapper methods
    as well as expected arguments.

    For each 3rd-party framework that uses gettext for localization, we need
    to pass different paths and arguments, so that calls to these methods
    are properly migrated.
    """

    def __init__(self, **kwargs):
        """Constructor.

        Usage:
        >>> GettextMethods(
        >>>     uget=(
        >>>         'path.to.ugettext',
        >>>         [('message', KEYWORD_STRING)],
        >>>     ),
        >>>     nget= (
        >>>         'path.to.ngettext',
        >>>         [
        >>>             ('singular', KEYWORD_ONE),
        >>>             ('plural', KEYWORD_OTHER),
        >>>             ('number', KEYWORD_CNT),
        >>>         ]
        >>>     ),
        >>> )
        """
        self.methods = kwargs

    def gettext_type_from_path(self, full_path):
        """Get the type of gettext method the given import path corresponds to.

        Supported types are UGET, UNGET, etc.

        Usage:
        >>> gettext_type_from_path('django.utils.translation.ngettext')
        'nget'

        :param str full_path: an import path
        :return: a string type
        :rtype: str
        """
        for gettext_type, params in self.methods.items():
            if params[0] == full_path:
                return gettext_type
        return None

    def tx_native_details_from_type(self, gettext_type):
        """Return details on how to structure a Native call of the given
        gettext type.

        Usage:
        >>> tx_native_details_from_type(UGETTEXT)
        <<< (
        <<<     't',
        <<<     (
        <<<         'django.utils.translation.ugettext',
        <<<         [('message', 'string')],
        <<<     )
        <<< )

        :param str gettext_type: e.g. UGET, UNGET, etc
        :return: a tuple like (<new_func_name>, [...])
        :rtype: tuple
        """
        params = self.methods.get(gettext_type)
        if not params:
            raise ValueError(
                'Unregistered or invalid gettext type "{}"'.format(
                    gettext_type
                )
            )
        method_name = params[0]
        native_method_name = (
            'lazyt' if method_name.endswith(LAZY_SUFFIX) else 't'
        )
        return native_method_name, params[1]

    @property
    def all(self):
        """Return a list of the parameters of all registered methods."""
        return self.methods.values()


class GettextMigrationBuilder(object):
    """Parses Python code and creates file migrations for each template.

    A migration is an object that describes the changes that need to be made
    in order to change a Python file that uses the gettext syntax
    to a file that uses the Transifex Native syntax.

    This class is stateful, but it can be reused. The reason it is created
    this way is for optimization, i.e. for not having to create new instances
    of the class for each migrated file.
    """

    def __init__(self, methods, import_statement):
        """Constructor.

        :param GettextMethods methods: the configuration to use
        :param str import_statement: the import statement to use
            in all migrated files
        """
        self._reset()
        self.methods = methods
        self.import_statement = import_statement
        self.transformer = Transformer(self.methods, import_statement)

    def _reset(self):
        """Reset some state parameters, so that a new migration can be created.

        The reason this method exists is for optimization, i.e. not having
        to create new instances of the class for each file.
        """
        # Sometimes, like when a comment is available, we cannot parse
        # a translatable string in one go, so we need to create
        # a StringMigration object and amend it as soon as we have all its
        # information.
        self._current_string_migration = None

    def build_migration(self, src, filename=None):
        """Create a migration for a Django template file to Transifex
        Native syntax.

        The returned object contains every change separately, so that
        it can be reviewed string by string.

        :param unicode src: the whole Django template
        :param str filename: the filename of the original template
        :return: a FileMigration instance
        :rtype: FileMigration
        """
        self._reset()
        file_migration = self.transformer.transform(src, filename)
        return file_migration


class Transformer(object):
    """Transforms source strings inside Python files from gettext syntax
    to Transifex Native syntax.

    It also keeps stats about any errors that have occurred.

    It allows clients to register custom module/function paths in order
    to support gettext module/function wrappers that exist in framework
    implementations that use native, such as a Django or a Flask SDK.
    """

    def __init__(self, methods, import_statement):
        """Constructor.

        :param GettextMethods methods: the gettext methods to transform
        :param str import_statement: the import statement to use
            in all migrated files
        """
        self.errors = []
        self._methods = methods
        if not import_statement.endswith('\n'):
            import_statement = '{}\n'.format(import_statement)
        self.import_statement = import_statement
        self._functions = []
        self.register_functions(*self._methods.all)

    def register_functions(self, *func_details_list):
        """Register a custom function to be detected during extraction.

        Each arg in `func_paths` must be a tuple, with its first item
        a string representing the full path of the function
        (like 'module.deeper_module.func_name') and its second item
        a list of tuples representing the items.

        Example:
        (
            'django.utils.translation.ugettext',
            [('message', 'string')],
        )
        """
        for func_path, argument_pairs in func_details_list:
            nodes = func_path.split('.')
            if len(nodes) < 1:
                raise ValueError(
                    'Function path must contain zero or more modules and '
                    'a function, e.g. "my_module.translate"'
                )

            self._functions.append(
                {
                    'modules': '.'.join(nodes[:-1]),
                    'function': nodes[-1],
                    'arguments': argument_pairs,
                }
            )

    def transform(self, src, filename=None):
        """Parse the given Python file string and extract translatable content.

        :param unicode src: a chunk of Python code
        :param str filename: the filename of the code, i.e. the filename it
            came from
        :return: a list of SourceString objects
        :rtype: list
        """
        # Replace utf-8 magic comment, to avoid getting a
        # "SyntaxError: encoding declaration in Unicode string"
        src = ENCODING_PATTERN.sub('# ', src)
        try:
            tree = ast.parse(src)
            visitor = CallDetectionVisitor(
                [
                    (x['modules'], x['function'])
                    for x in self._functions
                ]
            )
            visitor.visit(tree)

        except Exception as e:
            Color.echo(
                '[error]Error while parsing content '
                'of [file]{}[end]: {}'.format(filename, e)
            )
            # Store an exception for this particular file
            self.errors.append((filename, e))
            return None

        else:
            attree = asttokens.ASTTokens(src, tree=tree)
            file_migration = FileMigration(filename, src)
            last_migrated_char = 0

            def add_in_between(txt_range):
                """Add the simple text found between the last migrated node
                and the current node.

                Ensures that the text that should remain untransformed
                is included in the final file.
                """
                if txt_range[0] > last_migrated_char:
                    try:
                        original_str = src[last_migrated_char:txt_range[0]]
                        file_migration.add_string(
                            StringMigration(
                                original=original_str,
                                new=original_str,
                                confidence=Confidence.HIGH,
                            )
                        )
                    except Exception as e:
                        Color.echo(
                            '[error]Error while adding in-between content '
                            'in [file]{}[end]. last_migrated_char={}.'
                            'Error: {}'.format(
                                filename, last_migrated_char, e)
                        )
                        raise

            # Create a map with the text range for each node to migrate
            # We need this in order to sort the nodes. This way, we can
            # support the migration of imports that appear after function
            # calls (e.g. locally)
            text_ranges = {}
            to_migrate = (
                [x.node for x in visitor.imports] +
                visitor.function_calls
            )
            for node in to_migrate:
                text_ranges[node] = attree.get_text_range(node)

            # Remove duplicates
            to_migrate = sorted(set(to_migrate),
                                key=lambda n: text_ranges[n][0])

            import_added = False

            # Create a migration for adding the import statement
            # of Native. At this moment we don't know if it will need
            # to include t, lazyt or both, but we'll update the instance
            # after all nodes have been processed
            native_import_string_migration = StringMigration(
                '', ''
            )
            native_functions = set()  # will store 't'/'lazyt' if found later

            for node in to_migrate:
                text_range = text_ranges[node]
                add_in_between(text_range)

                try:
                    original = src[text_range[0]:text_range[1]]
                    new = original
                    confidence = Confidence.HIGH

                    # Migrate ImportFrom nodes. Leave Import nodes intact,
                    # as they may have been added in the code for uses other
                    # than gettext calls
                    if isinstance(node, ast.ImportFrom):
                        try:
                            #
                            if not import_added:
                                file_migration.add_string(
                                    native_import_string_migration
                                )
                            new, item_native_functions = self._transform_import(
                                visitor, node)
                            confidence = Confidence.HIGH
                            import_added = True
                            native_functions.update(item_native_functions)

                            # If the whole import statement was about gettext
                            # functions, a new empty line will have been
                            # added to the file. In that case,
                            # this will also remove the empty line completely
                            if new == '' and \
                                    node.first_token.line == original + '\n':
                                text_range = (text_range[0], text_range[1] + 1)
                                original = original + '\n'
                        except Exception as e:
                            raise Exception(
                                'Error while migrating import'
                                '\n{}'.format(str(e))
                            )

                    # Migrate function calls
                    elif isinstance(node, ast.Call):
                        try:
                            new, confidence = self._transform_call(
                                node, visitor, attree)
                        except Exception as e:
                            raise Exception(
                                'Error while migrating call'
                                '\n{}'.format(str(e))
                            )

                        # If this function call was part of a % operation
                        # make sure the right part is also removed
                        modulo_node = visitor.modulos.get(node)
                        if modulo_node:
                            # Override the text range with that of the
                            # modulo operation. This includes the function
                            # call as well
                            text_range = attree.get_text_range(modulo_node)
                            original = src[text_range[0]:text_range[1]]

                    file_migration.add_string(
                        StringMigration(
                            original=original,
                            new=new,
                            confidence=confidence,
                        )
                    )
                    last_migrated_char = text_range[1]

                except Exception as e:
                    Color.echo(
                        '[error]Error while transforming content '
                        'of [file]{}[end]: {}'.format(filename, e)
                    )
                    Color.echo('Original content:\n{}'.format(original))
                    # Store an exception for this particular file
                    self.errors.append((filename, e))
                    return None

            # Add the rest of the file (from the last migrated node
            # to the end)
            if last_migrated_char < len(src):
                original = src[last_migrated_char:]
                file_migration.add_string(
                    StringMigration(original=original, new=original)
                )

            # Update the Native import statement with the proper functions
            if native_functions:
                native_import_string_migration.update(
                    extra_original='',
                    extra_new=self.import_statement.format(
                        ', '.join(sorted(native_functions))
                    )
                )

            return file_migration

    def _transform_import(self, visitor, import_node):
        """Make sure any imports that are not related to gettext
        translations are not removed in the migrated string.

        If `migrated_import_string` is empty, it doesn't do anything.
        Otherwise, it searches to see if the particular ImportFrom node
        included any other imports that are not registered gettext methods
        and should be kept in the migration.

        For example, this:
            from django.utils.translation import ugettext as _, foo, bar as _bar
            from django.utils import translation as _trans
            import django
        will be transformed to this (in 3 consecutive _transform_import calls):
            from transifex.native.django import t
            from django.utils.translation import foo, bar as _bar
            from django.utils import translation as _trans

        :param CallDetectionVisitor visitor: the visitor object
        :param ast.Node import_node: the Import or ImportFrom node
        :return: a new string to be used as the "new" migration string
        :rtype: unicode
        """
        if isinstance(import_node, ast.Import):
            return '', []

        full_registered_paths = ['{}.{}'.format(x['modules'], x['function'])
                                 for x in self._functions]

        imports_per_node = visitor.imports_per_node.get(import_node)
        if not imports_per_node:
            return '', []

        imports = visitor.imports_per_node[import_node]['imports']
        module = visitor.imports_per_node[import_node]['module']
        all_import_units = [
            (unit, '{}.{}'.format(module, unit[0]))
            for unit in imports
        ]
        imports_to_keep = []
        for unit, full_path in all_import_units:
            if full_path not in full_registered_paths:
                imports_to_keep.append(unit)

        method_names = [
            self._methods.gettext_type_from_path(x[1])
            for x in all_import_units
        ]
        function_names = [
            'lazyt' if method_name.endswith(LAZY_SUFFIX) else 't'
            for method_name in method_names
            if method_name is not None
        ]
        if not imports_to_keep:
            return '', function_names

        new_string = 'from {module} import {units}'.format(
            module=module,
            units=', '.join([
                '{} as {}'.format(
                    unit[0], unit[1]
                )
                if unit[1] else unit[0]
                for unit in imports_to_keep
            ])
        )
        return new_string, function_names

    def _transform_call(self, func_call_node, visitor, attree):
        """Transform a function call to Transifex Native format.

        :param ast.Node func_call_node: the source node
        :param CallDetectionVisitor visitor: the visitor object
        :return: a tuple with the new serialized code and the confidence
            level of the migration
        :rtype: Tuple[unicode, int]
        """
        module_path, func_name = get_func_parts(func_call_node)

        for import_obj in visitor.imports:
            if module_path != import_obj.module \
                    or func_name != import_obj.function:
                continue

            for import_unit in import_obj.node.names:
                name = import_unit.name
                asname = import_unit.asname or name
                if func_name == asname:
                    break

            try:
                module = import_obj.node.module
            except AttributeError:
                module = None

            if not module_path:
                full_path = '{module}.{name}'.format(
                    module=module, name=name)
            else:
                full_path = '{module}{path}.{func}'.format(
                    module=('{}.'.format(module) if module else ''),
                    path=module_path.replace(
                        asname,
                        name,
                        1,
                    ),
                    func=func_name
                )

            if not full_path:
                name = import_obj.node.names[0].name
                asname = import_obj.node.names[0].asname or name

            gettext_type = self._methods.gettext_type_from_path(full_path)
            if gettext_type is None:
                continue

            new_func_name, args = self._methods.tx_native_details_from_type(
                gettext_type
            )
            new_arguments_serialized, confidence = self._serialize_arguments(
                func_call_node, gettext_type, args
            )

            # Update the source string to match TX Native syntax
            # and replace it in the arguments list
            new_source_string, placeholders1 = printf_to_format_style(
                new_arguments_serialized[0]
            )

            new_arguments_serialized[0] = new_source_string
            quote = new_source_string[0]

            modulo_node = visitor.modulos.get(func_call_node)
            interpolated_params, placeholders2, modulo_confidence = \
                self._parse_modulo_operation(modulo_node, quote, attree)
            if modulo_confidence == Confidence.LOW:
                confidence = Confidence.LOW

            # If they don't match, it means that we haven't properly
            # detected and migrated the values
            if placeholders1 != placeholders2:
                confidence = Confidence.LOW

            new_call = '{func_name}({args})'.format(
                func_name=new_func_name,
                args=', '.join(new_arguments_serialized + interpolated_params)
            )
            return new_call, confidence

        # Normally we shouldn't reach this point
        return None, Confidence.LOW

    def _parse_modulo_operation(self, modulo_node, quote, attree):
        """Extract all parameters from the given modulo node.

        The returned parameters can be used as is on a serialized
        t() function call.

        :param ast.Node modulo_node: the node to parse
        :param str quote: the quote to use for wrapping strings, i.e. " or '
        :param asttokens.ASTTokens attree: the parsed tree
        :return: a tuple structured like:
            (
                ['var1=var1', 'var2="value"', 'username=username'],
                ['var1', 'var2', 'username'],
                Confidence.HIGH
            )
        :rtype: Tuple[list, list, int]
        """
        if modulo_node is None:
            return [], [], Confidence.HIGH

        def var(num):
            """Generate a name for a variable with unknown name."""
            return VAR_FORMAT.format(cnt=str(num))

        def extract_param(_name, _element):
            """Get a parameter assignment for use with t() syntax,
            depending on the type of the given element"""
            if isinstance(_element, ast.Name):
                # variables: <name>=<value>
                return '{}={}'.format(_name, _element.id)
            elif isinstance(_element, ast.Str):
                # literals: <name>="<value>"
                new_quote = alt_quote(quote, _element.s)
                return ''.join([_name, '=', new_quote, _element.s, new_quote])
            elif isinstance(_element, ast.BinOp):
                # operations: <name>=(<left> <op> <right>)
                return '{}=({})'.format(_name, attree.get_text(_element))
            else:
                # everything else: <name>=<value>
                return '{}={}'.format(_name, attree.get_text(_element))

        def confidence(_element):
            """Return the proper confidence for the given node.

            It returns low confidence if the text includes \\' or \\"
            as these are not being properly handled by alt_quote().
            """
            if isinstance(_element, ast.Name):
                _string = _element.id
            elif isinstance(_element, ast.Str):
                _string = _element.s
            else:
                _string = attree.get_text(_element)
            if r"\\'" in _string or r'\\"' in _string:
                return Confidence.LOW
            return Confidence.HIGH

        right_op = modulo_node.right
        placeholders = []

        # e.g. % something
        #      % 'something'
        if isinstance(right_op, (ast.Name, ast.Str)):
            param = var(1)
            return [extract_param(param, right_op)], [param], confidence(
                right_op)

        # e.g. % (something, "literal")
        if isinstance(right_op, (ast.List, ast.Tuple)):
            cnt = 1
            params = []
            confidences = []
            for element in right_op.elts:
                name = var(cnt)
                params.append(extract_param(name, element))
                placeholders.append(name)
                cnt += 1
                confidences.append(confidence(element))

            final_confidence = (
                Confidence.LOW if Confidence.LOW in confidences
                else Confidence.HIGH
            )
            return params, placeholders, final_confidence

        # e.g. % {'foo': foo, 'bar': 'bar'}
        if isinstance(right_op, ast.Dict):
            params = []
            confidences = []
            for key, element in zip(right_op.keys, right_op.values):
                name = key.s
                params.append(extract_param(name, element))
                placeholders.append(name)
                confidences.append(confidence(element))

            final_confidence = (
                Confidence.LOW if Confidence.LOW in confidences
                else Confidence.HIGH
            )
            return params, placeholders, final_confidence

        # e.g. % dict(foo=foo, bar='bar')
        # NOTE: We could instead parse all values of the dictionary
        # but we chose not to for now
        if (isinstance(right_op, ast.Call)
                and hasattr(right_op.func, 'id')
                and right_op.func.id == 'dict'):
            string = attree.get_text(right_op)
            new_quote = alt_quote(quote, string)
            value = ''.join(
                [MARK_ARGUMENT_FIXME, '=', new_quote, string, new_quote]
            )
            return [value], [MARK_ARGUMENT_FIXME], Confidence.LOW

        # e.g. % (3 * 15)
        if isinstance(right_op, ast.BinOp):
            name = var(1)
            # Wrap in parentheses to make sure it's valid
            return [extract_param(name, right_op)], [name], Confidence.HIGH

        # In any other case, get the node text and use it as is
        # in a variable
        name = var(1)
        return [extract_param(name, right_op)], [name], Confidence.HIGH

    def _serialize_arguments(self, func_call_node, gettext_type, expected_args):
        """Return arguments as a serialized string for the given function call,
        as transformed to fit the syntax of Transifex Native.

        Supports parameters passed in all possible ways:
          - gettext('text')
          - gettext(*['text'])
          - gettext(message='text')
          - gettext(**{'message': 'text'})

        Example return:
        (
            ['This is the {foo} source string', '_context="A context"'],
            Confidence.HIGH
        )

        :param ast.Call func_call_node: the function call node
        :param str gettext_type: the type of method, e.g. NGETTEXT
        :param list expected_args: a list of tuples
        :return: a tuple that contains:
            - a list with strings of all arguments serialized, ready to be used
              in a Native call
            - a Confidence value, based on the parsed arguments
        :rtype: Tuple[list, int]
        """
        def replace_quotes(_string, existing_quote):
            """Return new string with alternate quotes, if necessary.

            Assumes default quotes are double quotes (").
            :rtype: unicode
            """
            if not existing_quote or existing_quote == '"':
                return _string
            return _string.replace('"', "'")

        # Make a copy of all containers, we'll delete items as we go
        args = list(func_call_node.args)
        starargs = (
            list(func_call_node.starargs.elts)
            if hasattr(func_call_node, 'starargs') and func_call_node.starargs
            else None
        )
        keywords = list(func_call_node.keywords)
        kwargs = (
            list(func_call_node.kwargs.keywords)
            if hasattr(func_call_node, 'kwargs') and func_call_node.kwargs
            else {}
        )

        new_arguments = {}
        for arg_name, arg_type in expected_args:
            # Start with normal arguments, e.g. func('value')
            node = args[0] if args else None
            if node:
                args = args[1:]
                new_arguments[arg_type] = (render_keyword(node),
                                           original_quote(node))
                continue

            # If not found, try starargs, e.g. func(*['value'])
            node = starargs[0] if starargs else None
            if node:
                starargs = starargs[1:]
                new_arguments[arg_type] = (render_keyword(node),
                                           original_quote(node))
                continue

            # If not found, try keywords, e.g. func(message='value')
            found = False
            for keyword in keywords:
                # This only happens on Python 3 for calls like:
                # func(**dict(message='value')). In this case we switch
                # the current `keyword` # with that found inside **dict(...)
                # The `if` statement that follows will take care of the actual
                # parsing and rendering
                if keyword.arg is None and isinstance(keyword.value, ast.Call):
                    inner_func_call = keyword.value
                    if inner_func_call.func.id != 'dict':
                        continue
                    for k in inner_func_call.keywords:
                        if k.arg == arg_name:
                            keyword = k
                            break

                if keyword.arg == arg_name:
                    new_arguments[arg_type] = (render_keyword(keyword.value),
                                               original_quote(keyword))
                    if keyword in keywords:
                        keywords.remove(keyword)
                    found = True
                    break
            if found:
                continue

            # Final resort, try kwargs, e.g. func(**{'message': 'value'})
            for keyword in kwargs:
                if keyword.arg == arg_name:
                    new_arguments[arg_type] = (render_keyword(keyword.value),
                                               original_quote(keyword))
                    kwargs.remove(keyword)
                    break

        # Simple string
        if gettext_type in (GETTEXT, UGETTEXT, GETTEXT_LAZY, UGETTEXT_LAZY):
            string, quote = new_arguments[KEYWORD_STRING]
            return [replace_quotes('"{}"', quote).format(string)], \
                Confidence.HIGH

        # Pluralized string
        if gettext_type in (NGETTEXT, UNGETTEXT, NPGETTEXT, NGETTEXT_LAZY, UNGETTEXT_LAZY, NPGETTEXT_LAZY):
            one, quote_one = new_arguments[KEYWORD_ONE]
            other, quote_other = new_arguments[KEYWORD_OTHER]

            confidence = Confidence.HIGH
            if quote_one != quote_other and quote_one in other:
                confidence = Confidence.LOW
                other = other.replace(quote_one, r'\{}'.format(quote_one))

            items = [
                replace_quotes('"{', quote_one), ICU_PLURAL_COUNTER, ', ',
                'one {', one, '} ',
                'other {', other, '}',
                replace_quotes('}"', quote_one)  # end of ICU string
            ]
            # Also includes context
            if gettext_type == NPGETTEXT:
                context, quote_context = new_arguments[KEYWORD_CONTEXT]
                items.extend((
                    ', ', KEY_CONTEXT, replace_quotes('="', quote_context),
                    context, replace_quotes('"', quote_context),
                ))
            items.extend((
                ', ', ICU_PLURAL_COUNTER, '=', new_arguments[KEYWORD_CNT][0]
            ))

            return [''.join([str(x) for x in items])], confidence

        # String with context
        if gettext_type in (PGETTEXT, PGETTEXT_LAZY):
            string, string_quote = new_arguments[KEYWORD_STRING]
            context, quote_context = new_arguments[KEYWORD_CONTEXT]
            string = replace_quotes('"{}"', string_quote).format(string)
            context = replace_quotes('_context="{}"', quote_context).format(
                context
            )
            return [string, context], Confidence.HIGH

        raise ValueError(
            'Invalid gettext type: {}. Cannot serialize arguments'.format(
                gettext_type
            )
        )


def render_keyword(keyword):
    """Render the given keyword to a proper value.

    Processes Keyword objects and returns its value, using the correct property
    depending on its type.

    :param Keyword keyword: the keyword object
    :return: the keyword value (string, number, etc)
    :rtype: object
    """
    if isinstance(keyword, ast.Str):
        return keyword.s
    if isinstance(keyword, ast.Num):
        return keyword.n
    if isinstance(keyword, ast.Name):
        return keyword.id
    return ''


def original_quote(node):
    """Return the quote (' or ") found in the first character of the
    given node.

    :param ast.Node node: the node to check
    :return: a 1-char string, ' or "
    :rtype: str
    """
    quote = node.last_token.string[0]
    return quote if quote in ('"', "'") else None
