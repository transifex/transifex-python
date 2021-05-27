from __future__ import unicode_literals

import ast
import re
from collections import namedtuple

from transifex.common._compat import string_types
from transifex.common.utils import generate_key, make_hashable, parse_plurals
from transifex.native import consts
from transifex.native.consts import KEY_CONTEXT, KEY_OCCURRENCES

# PEP 263 magic comment for source code encodings
# e.g. "# -*- coding: <encoding name> -*-"

ENCODING_PATTERN = re.compile(r'#.*coding[:=]\s*utf-?8', re.IGNORECASE)


# A list of the translate functions that TxNative supports,
# in the syntax of module.deeper_module..function
DEFAULT_MODULES = [
    'transifex.native.translate',
    'transifex.native.lazy_translate',
]


Import = namedtuple('Import', ('module', 'function', 'node'))


class SourceString(object):
    """A data object that contains information about a source string."""

    def __init__(self, string, _context=None, **meta):
        """Constructor.

        :param unicode string: the source string  # check ./consts.py
        :param unicode _context: an optional context that accompanies
            the source string
        """

        self.key = generate_key(string=string, context=_context)
        self.string = string
        self.context = (
            [x.strip() for x in _context.split(',')] if _context
            else None
        )  # type: list
        self.meta = self._transform_meta(meta)

    @property
    def occurrences(self):
        """An optional occurrence field, shows were the string is located

        :rtype: unicode
        """
        return self.meta.get(consts.KEY_OCCURRENCES, [])

    @occurrences.setter
    def occurrences(self, value):
        self.meta.setdefault(consts.KEY_OCCURRENCES, []).extend(value)

    @property
    def developer_comment(self):
        """An optional developer comment for the string.

        :rtype: unicode
        """
        return self.meta.get(consts.KEY_DEVELOPER_COMMENT)

    @property
    def character_limit(self):
        """An optional character limit for the string or None if not defined.

        :rtype: int
        """
        return self.meta.get(consts.KEY_CHARACTER_LIMIT)

    @property
    def tags(self):
        """A list of tags.

        :rtype: list
        """
        return self.meta.get(consts.KEY_TAGS, [])

    def _transform_meta(self, meta):
        """Transform values in meta object, whenever applicable.

        :param dict meta:
        :return: the same dictionary, with some values potentially altered
        :rtype: dict
        """
        tags = meta.get(consts.KEY_TAGS)
        if tags and isinstance(tags, string_types):
            meta[consts.KEY_TAGS] = [x.strip() for x in tags.split(',')]

        return {
            k: v for k, v in meta.items()
            if k in consts.ALL_KEYS
        }

    def __repr__(self):
        return u'<{}: {}>'.format(
            self.__class__.__name__,
            u' '.join((self.context or []) + [self.string]),
        )

    def __eq__(self, other):
        """Object equality.

        :param SourceString other: the instance to compare to
        :return: True if the instances are equal, False otherwise
        :rtype: bool
        """
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.key, make_hashable(self.meta)))


class Extractor(object):
    """Extracts translatable source strings from Python files.

    It also keeps stats about any errors that have occurred.

    It allows clients to register custom module/function paths in order
    to support translate modules and functions that exist in framework
    implementations that use native, such as a Django or a Flask SDK.
    """

    def __init__(self):
        self.errors = []
        self._functions = []
        for path in DEFAULT_MODULES:
            self.register_functions(path)

    def register_functions(self, *func_paths):
        """Register a custom function to be detected during extraction.

        Each arg in `func_paths` must be a string, representing the full path
            of the function, like 'module.deeper_module.func_name'
        """
        for func_path in func_paths:
            nodes = func_path.split('.')
            if len(nodes) < 2:
                raise ValueError(
                    'Function path must contain at least a module and'
                    'a function, e.g. "my_module.translate"'
                )
            self._functions.append(
                ('.'.join(nodes[:-1]), nodes[-1])
            )

    def extract_strings(self, src, origin=None):
        """Parse the given Python file string and extract translatable content.

        :param unicode src: a chunk of Python code
        :param str origin: the filename of the code, i.e. the filename
            it came from
        :return: a list of SourceString objects
        :rtype: list
        """
        # Replace utf-8 magic comment, to avoid getting a
        # "SyntaxError: encoding declaration in Unicode string"
        src = ENCODING_PATTERN.sub('# ', src)
        try:
            tree = ast.parse(src)
            visitor = CallDetectionVisitor(self._functions)
            visitor.visit(tree)
            source_strings, linenos = parse_source_strings(
                visitor.function_calls)
            # add file path to the string occurrence along with already
            # included number
        except Exception as e:
            # Store an exception for this particular file
            self.errors.append((origin, e))
            source_strings, linenos = [], []

        for src_str, lineno in zip(source_strings, linenos):
            src_str.occurrences = ["{}:{}".format(origin, lineno)]
        return source_strings


class CallDetectionVisitor(ast.NodeVisitor):
    """A visitor subclass that detects externally-defined imports and
    function methods and stores them.

    Subclasses can provide additional functionality that takes the imports
    and function calls and does something more useful with them.

    NOTE: in order for a function call to be detected, the corresponding
    `import` statement must appear before in the syntax tree. If we want
    to support calls that appear before imports, we could visit the tree
    twice, once to detect the imports and once to detect the calls
    and create the strings.
    """

    def __init__(self, registered_calls):
        """Constructor.

        Each item in `registered_calls` should be a tuple like:
          ('a.b.c', 'translate_func')
        which translates to calls like:
          from a.b.c import translate_func as tr; tr(...)
          from a.b import c; c.translate_func(...)
        and so on

        :param list registered_calls: a list of 2-tuples each with information
            on how to detect the imports and the calls
        """
        super(CallDetectionVisitor, self).__init__()

        # Contains a list of module/function pairs in dot notation
        # that are provided in the constructor. These are the imports
        # and function calls that the visitor will detect as being
        # "of interest".
        # Example: [('a.b', 'translate'), ('foo', 'trans')]
        self._registered_calls = registered_calls

        # Dynamically populated when parsing import statements,
        # this list will contain the module/function pairs that are
        # actually found in the current syntax tree (e.g. in a specific
        # Python file). This way, only calls that are actually made to
        # registered functions will be matched for each file, instead
        # of matching any function that has a name identical to what
        # a certain module provides (e.g. a `translate()` method of
        # another module).
        # Supports 'as' syntax, e.g. import translate as _trans
        # Contains `Import` objects.
        self.imports = []

        # This dictionary will contain all imports per Import/ImportFrom node.
        # It stores all imports, not only those that correspond to registered
        # calls.
        # For example, with the following statements:
        #   from a.b.c import gettext as _, e, d as _d
        # it will become:
        #   {
        #       <ImportFrom>: {
        #           'module': 'a.b.c',
        #           'imports': [('gettext', '_'), ('e', None), ('d', '_d')],
        #       },
        #   }
        self.imports_per_node = {}

        # For each detected function call that matches the detected imports
        # an ast.Call object will be stored here
        self.function_calls = []

        # We store each % operation here to process later, by its proceeding
        # function call node
        self.modulos = {}

    def visit_Import(self, node):
        """Support the 'import native as _native' type of imports.

        Given a supported function path that looks like this:
            >>> 'a.b.c.d.translate'
        takes an import statement that looks like this:
            >>> import a.b as _b
        and comes up with a tuple like this:
            >>> ('_b.c.d', 'translate')
        """
        self.generic_visit(node)

        for module_path, func_name in self._registered_calls:
            name = node.names[0].name
            as_name = node.names[0].asname
            # e.g. module_path='a.b.c', func_name='translate',
            #      name='a.b', asname='_c'
            if not module_path.startswith(name):
                continue

            remaining_module_path = module_path.replace(name, '')
            remaining_module_path = remaining_module_path.lstrip('.')

            if not as_name:
                as_name = name.split('.')[-1]

            remaining_module_path = (
                '{}.{}'.format(as_name, remaining_module_path).rstrip('.')
            )

            self.imports.append(
                Import(remaining_module_path, func_name, node)
            )

    def visit_ImportFrom(self, node):
        """Support the 'from native import native as _native' type of imports.

        Given a supported function path that looks like this:
            >>> 'a.b.c.d.translate'
        takes an import statement that looks like this:
            >>> from a.b import c as _c
        and comes up with a tuple like this:
            >>> ('_c.d', 'translate', <ImportFrom node>)
        """
        self.generic_visit(node)

        # Store the information for each part of the import
        imports_in_node = {'module': node.module, 'imports': []}
        for name_obj in node.names:
            name = name_obj.name
            as_name = name_obj.asname
            import_unit = (name, as_name)
            if import_unit not in imports_in_node['imports']:
                imports_in_node['imports'].append(import_unit)

        # Loop through all registered module/function calls,
        # e.g. transifex.native.django.t
        # and see if the current import matches any of them
        for registered_module_path, registered_func_name in self._registered_calls:
            # e.g. registered_module_path='transifex.native.django',
            #      registered_func_name='t'

            module = node.module
            if not registered_module_path.startswith(module):
                continue

            # Loop through all 'import' statements, e.g.
            # from m import a, b, c -> loop through [a, b, c] objects
            for name_obj in node.names:
                name = name_obj.name
                as_name = name_obj.asname

                try:
                    # If the full function call in the code is identical to the
                    # registered function name, e.g. it's `t('...')`
                    if name == registered_func_name:
                        registered_func_name = as_name or name
                        remaining_module_path = ''
                    else:
                        modules = registered_module_path.split('.')
                        if name in modules:
                            modules = modules[modules.index(name):]
                            if as_name and modules[0] == name:
                                modules[0] = as_name
                            remaining_module_path = '.'.join(modules)
                        else:
                            continue
                except Exception as e:
                    print(
                        'Error while visiting node: {}.{}{}: {}'.format(
                            module, name, (' as ' +
                                           as_name if as_name else ''),
                            e
                        )
                    )
                    continue

                # Store this import
                # Note that because self._registered_calls is a list,
                # we might append Import multiple objects with the same `node`
                self.imports.append(
                    Import(remaining_module_path, registered_func_name, node)
                )

        if imports_in_node:
            self.imports_per_node[node] = imports_in_node

    def visit_Call(self, node):
        """Extract a source string from a "translate" function call.

        Supports calls like:
          >>> translate('...')
          >>> a.b.c.translate('...')
        based on the supported calls that have been detected
        for the current syntax tree.
        """
        self.generic_visit(node)

        current_module_path, current_func_name = get_func_parts(node)

        # Check against all supported function calls and if there is a match
        # add the node for later processing
        for import_obj in self.imports:
            module_path = import_obj.module
            func_name = import_obj.function

            if module_path == current_module_path \
                    and func_name == current_func_name:
                self.function_calls.append(node)

    def visit_BinOp(self, node):
        """Store % operations to process later.

        We don't process them here because in _(...) % (...) statements
        the _(...) node hasn't been processed yet when the modulo operation
        is processed.
        """
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Call):
            func_call = node.left
            self.visit_Call(func_call)
            if self.function_calls and self.function_calls[-1] == func_call:
                self.modulos[func_call] = node
        else:
            self.generic_visit(node)


def parse_source_strings(nodes):
    """Parse the given function call nodes and return a list of SourceString
    objects.

    :param list nodes: a list of Node objects

    :return:  a tuple of the source_strings along with the corresponding linenos
    :rtype: tuple
    """
    strings = []
    string_linenos = []
    for node in nodes:
        try:
            string = node.args[0].s
            # Context could be passed as an argument, e.g. t('str', 'context')
            context = node.args[1].s if len(node.args) > 1 else None
            # Find all custom parameters, e.g. developer comments etc
            params = {}
            for keyword in node.keywords:
                name, value = render_keyword(keyword)
                if value is not None:
                    params[name] = value
            string_linenos.append(node.lineno)
            # If no context was found before, maybe it was passed as a kwarg
            if context is None:
                context = params.pop(KEY_CONTEXT, None)

            strings.append(SourceString(string, context, **params))
        except Exception as e:
            raise AttributeError(
                'Invalid module/function format on line {} col {}: {}'.format(
                    node.lineno, node.col_offset, e
                )
            )

    return strings, string_linenos


def render_keyword(keyword):
    """Render the given keyword to a proper value.

    Processes Keyword objects and returns the keyword name along with
    a value of their corresponding type, i.e. a string, a number
    or a boolean.

    :param Keyword keyword: the keyword object
    :return: a tuple like (<key>, <value>)
    :rtype: tuple
    """
    if isinstance(keyword.value, ast.Str):
        val = keyword.value.s
    elif isinstance(keyword.value, ast.Num):
        val = keyword.value.n
    elif (isinstance(keyword.value, ast.Name)
          and keyword.value.id in ('True', 'False')):
        val = keyword.value.id == 'True'
    else:
        val = None

    return keyword.arg, val


def get_func_parts(node):
    # Find the full module/function path of the current calling node,
    # e.g. 'a.b.c.translate'.
    # The way to retrieve the module name and function name
    # differs a lot depending on the level of nesting, so try...catch blocks
    # are used in order to cover all cases
    modules = []
    try:
        current_node = node.func.value
        current_func_name = node.func.attr
        # Module nesting can be indefinite, so we need to follow it
        # to the end
        while True:
            try:
                modules.insert(0, current_node.attr)
                current_node = current_node.value
            except AttributeError:
                modules.insert(0, current_node.id)
                break
    except AttributeError:
        try:
            current_func_name = node.func.id
        except AttributeError:
            try:
                current_func_name = node.func.attr
            except AttributeError as e:
                raise AttributeError(
                    'Invalid module/function format on line {} '
                    'col {}: {}'.format(node.lineno, node.col_offset, e)
                )

    current_module_path = '.'.join(modules)

    return current_module_path, current_func_name
