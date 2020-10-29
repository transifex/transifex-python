from __future__ import unicode_literals

import ast
import importlib
import inspect
import io
import itertools
import re
import reprlib
import sys
from collections import namedtuple
from copy import copy

try:
    from collections.abc import MutableSet
except ImportError:
    from collections import MutableSet

import six

from transifex.common._compat import string_types
from transifex.common.utils import generate_key
from transifex.native.consts import KEY_CONTEXT

PYVER = sys.version_info[0]

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


ATTR_MAPPING = {'_context': "context",
                '_charlimit': "character_limit",
                '_comment': "developer_comment",
                '_occurrences': "occurrences",
                '_tags': "tags"}


class SourceString(object):
    """ Simple container for describing source strings found in source files.

        The 'context', 'tags' and 'occurrences' are always saved as lists, even
        if they are provided as strings.

        Supports the `key` property.

        Implements the `__hash__` and `__eq__` methods so that they can be
        compared and/or used in sets/dicts.
    """

    def __init__(self, source_string=None, context=None, character_limit=None,
                 developer_comment=None, occurrences=None, tags=None):
        self.source_string = source_string
        self.context = context
        self.character_limit = character_limit
        self.developer_comment = developer_comment
        self.occurrences = occurrences
        self.tags = tags

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        if isinstance(value, string_types):
            value = [item.strip() for item in value.split(',')]
        self._context = value

    def _array_property(attr):
        """ Define a property that accepts a string or an array but always
            saves an array. Splits string input by ','.

            Usage:

                >>> class SourceString:
                ...     a = _array_setter('_a')

            equivalent to:

                >>> class SourceString:
                ...     @property
                ...     def a(self):
                ...         return self._a
                ...
                ...     @a.setter
                ...     def a(self, value):
                ...         if isinstance(value, string_types):
                ...             value = [item.strip()
                ...                      for item in value.split(',')]
                ...         elif value is None:
                ...             value = []
                ...         self._a = sorted(value)
        """

        def _array_setter(self, attr, value):
            if isinstance(value, string_types):
                value = [item.strip() for item in value.split(',')]
            elif value is None:
                value = []
            setattr(self, attr, sorted(value))

        return property(lambda self: getattr(self, attr),
                        lambda self, value: _array_setter(self, attr, value))

    tags = _array_property('_tags')
    occurrences = _array_property('_occurrences')

    @property
    def key(self):
        return generate_key(self.source_string, self.context)

    def __repr__(self):
        result = reprlib.repr(self.source_string)
        meta = {attr: reprlib.repr(getattr(self, attr))
                for attr in ('context', 'developer_comment', 'character_limit',
                             'tags', 'occurrences')
                if getattr(self, attr)}
        meta = ', '.join(("{}: {}".format(key, value)
                          for key, value in meta.items()))
        if meta:
            result += " ({})".format(meta)
        result = "<SourceString: {}>".format(result)
        return result

    def _hash(self):
        attrs = ('source_string', 'context', 'character_limit',
                 'developer_comment', 'occurrences', 'tags')
        attrs = (getattr(self, attr) for attr in attrs)
        attrs = (repr(attr) for attr in attrs)
        # Escape ':' to ensure uniqueness
        attrs = (attr.replace('\\', "\\\\").replace(':', "\\:")
                 for attr in attrs)
        return ':'.join(attrs)

    def __hash__(self):
        return hash(self._hash())

    def __eq__(self, other):
        try:
            return hash(self) == hash(other)
        except Exception:
            return super(SourceString, self).__eq__(other)

    def __lt__(self, other):
        # For sorting
        try:
            return self._hash() < other._hash()
        except Exception:
            return super(SourceString, self).__lt__(other)

    def __copy__(self):
        return self.__class__(self.source_string, self.context,
                              self.character_limit, self.developer_comment,
                              self.occurrences, self.tags)


class SourceStringSet(MutableSet):
    """ Set-like object that contains SourceStrings. If you attempt to add a
        string with the same key as an existing one, the two will be merged.

        Usage:

            >>> strings = SourceStringSet([SourceString("hello world")])
            <<< {<SourceString: "hello world">}

            >>> strings |= [SourceString("hello world", character_limit=5)]
            <<< {<SourceString: "hello world" (character_limit: 5)>}

            >>> strings |= [SourceString("hello world", character_limit=4)]
            <<< {<SourceString: "hello world" (character_limit: 4)>}

            >>> strings |= [SourceString("hello world",
            ...                          context="with_tags",
            ...                          tags="a,b")]
            <<< {<SourceString: "hello world" (character_limit: 4)>,
            ...  <SourceString: "hello world" (context: ["with_tags"],
            ...                                tags: ["a", "b"])>}

            >>> strings |= [SourceString("hello world",
            ...                          context="with_tags",
            ...                          tags=["b", "c"])]
            <<< {<SourceString: "hello world" (character_limit: 4)>,
            ...  <SourceString: "hello world" (context: ["with_tags"],
            ...                                tags: ["a", "b", "c"])>}
    """

    def __init__(self, strings=None):
        if strings is None:
            strings = []

        self._data = {}
        for string in strings:
            self.add(string)

    # MutableSet's abstract methods
    def __contains__(self, string):
        return string.key in self._data and self._data[string.key] == string

    def __iter__(self):
        for string in six.itervalues(self._data):
            yield string

    def __len__(self):
        return len(self._data)

    def add(self, string):
        if string.key in self._data:
            self._data[string.key] = self._merge(self._data[string.key],
                                                 string)
        else:
            self._data[string.key] = string

    def discard(self, string):
        if string in self:
            del self._data[string.key]

    def __repr__(self):
        return repr(set(self))

    # Private methods
    @staticmethod
    def _merge(left, right):
        """ Merge the two SourceStrings. We assume they have the same
            source_string, context and key. Merge the rest of the metadata,
            giving priority to the left's.
        """

        result = copy(left)
        if (right.character_limit is not None and
                (result.character_limit is None or
                 result.character_limit > right.character_limit)):
            result.character_limit = right.character_limit
        if (right.developer_comment is not None and
                result.developer_comment is None):
            result.developer_comment = right.developer_comment
        result.occurrences = list(set(result.occurrences or []) |
                                  set(right.occurrences or [])) or None
        result.tags = list(set(result.tags or []) |
                           set(right.tags or [])) or None
        return result


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
        for (registered_module_path,
             registered_func_name) in self._registered_calls:
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
    """ Parse the given function call nodes and return a list of SourceString
        objects.

        :param list nodes: a list of Node objects

        :return:  a tuple of the source_strings along with the corresponding
            linenos
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

            string = SourceString(string, context)
            for key, value in params.items():
                if key in ATTR_MAPPING:
                    setattr(string, ATTR_MAPPING[key], value)
            strings.append(string)

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


DEFAULT_IMPORT_PATHS = ("transifex.native.t",
                        "transifex.native.tx.translate",
                        "transifex.native.django.t",
                        "transifex.native.django.ut",
                        "transifex.native.urwid.T")


class CallDetectionVisitor2(ast.NodeVisitor):
    """ Parser for python files that extracts invocations of t-functions. It is
        required that the `import_paths` argument points to importable
        functions and that the names of the arguments they accept are
        compatible, namely 'source_string', '_context', '_charlimit',
        '_comment', '_occurrences' and '_tags'.

        1. Detect whether the target functions are being imported
        2. Find calls to these functions
        3. Match the actual arguments of the function calls to the argument
           names from the function definitions
        4. Limit extracted arguments to constants
        5. Create `SourceString` instance from arguments
        6. Save SourceStrings to `self.strings`

        Usage:

            >>> v = CallDetectionVisitor2(filename="filename.py")
            >>> v.visit(ast.parse("\n".join((
            ...     'import transifex.native as nt',
            ...     'from transifex.native import t as t2',
            ...     'nt.tx.translate("hello", "fr")',
            ...     't2("hello", "de", "context")'
            ... ))))
            >>> v.strings
            <<< {<SourceString: 'hello' (occurrences: ['filename.py:3'])>,
                 <SourceString: 'hello' (context: ['context'],
                                         occurrences: ['filename.py:4'])>}
    """

    def __init__(self, filename=None, import_paths=None):
        if import_paths is None:
            import_paths = DEFAULT_IMPORT_PATHS

        self.import_paths = [path.split('.') for path in import_paths]
        self.filename = filename

        self.functions = {}
        self.strings = SourceStringSet()

    def visit_Import(self, node):
        # code: import transifex.native
        # node: Import(names=[alias(name='transifex.native', asname=None)]),
        for item, import_path in itertools.product(node.names,
                                                   self.import_paths):
            name = item.name.split('.')
            #   name:         ['transifex', 'native']
            #   import_path:  ['transifex', 'native', 'tx', 'translate']
            #   _is_subset(): (True, 2)
            is_subset, parts_matched = self._is_subset(name, import_path)

            if not is_subset:
                continue

            if item.asname is None:
                # function: ['transifex', 'native', 'tx', 'translate']
                function = tuple(import_path)
            else:
                # code:     import transifex.native as nt
                # item:     alias(name='transifex.native', asname='nt')
                # function: ['nt', 'tx', 'translate']
                function = tuple([item.asname] +
                                 import_path[parts_matched:])
            self.functions[function] = self._import_from_path(import_path)

    def visit_ImportFrom(self, node):
        # code: from transifex.native import tx
        # node: ImportFrom(module='transifex.native',
        #                  names=[alias(name='tx', asname=None)]),
        for import_path in self.import_paths:
            # node.module: ['transifex', 'native']
            # import_path: ['transifex', 'native', 'tx', 'translate']
            # is_subset:   (True, 2)
            is_subset, parts_matched = self._is_subset(node.module.split('.'),
                                                       import_path)

            if not is_subset:
                continue

            # rest: ['tx', 'translate']
            rest = import_path[parts_matched:]
            for item in node.names:
                if item.name != rest[0]:
                    continue

                if item.asname is None:
                    # function: ['tx', 'translate']
                    function = tuple(rest)
                else:
                    # code:     from transifex.native import tx as tx2
                    # item:     alias(name='tx', asname='tx2')
                    # function: ['tx2', 'translate']
                    function = tuple([item.asname] + rest[1:])
                self.functions[function] = self._import_from_path(import_path)

    def visit_Call(self, node):
        # code: transifex.native.t("hello {username}",
        #                          _charlimit=3,
        #                          username="Bob")
        # node: Call(func=Attribute(value=Attribute(value=Name(id='transifex'),
        #                                           attr='native'),
        #                           attr='t'),
        #            args=[Constant(value='hello {username}')],
        #            keywords=[keyword(arg='_charlimit',
        #                              value=Constant(value=3)),
        #                      keyword(arg='username',
        #                              value=Constant(value='Bob'))])

        # 1. path: []
        #    ptr:  Attribute(value=Attribute(value=Name(id='transifex'),
        #                                    attr='native'),
        #                    attr='t')
        # 2. path: ['t']
        #    ptr:  Attribute(value=Name(id='transifex'), attr='native')
        # 3. path: ['t', 'native']
        #    ptr:  Name(id='transifex')
        path = []
        ptr = node.func
        while isinstance(ptr, ast.Attribute):
            path.append(ptr.attr)
            ptr = ptr.value

        try:
            path.append(ptr.id)
            # path: ['t', 'native', 'transifex']
        except AttributeError:
            # Not a typical call, more likely something like `a[b].c(...)`
            self.generic_visit(node)
            return

        path = tuple(reversed(path))  # ('transifex', 'native', 't')
        if path not in self.functions:
            self.generic_visit(node)
            return

        # Gotcha, lets create a SourceString!
        arguments = self._extract_arguments(self.functions[path], node)
        if 'source_string' not in arguments:
            # Maybe t-function was called with a variable as its first argument
            self.generic_visit(node)
            return
        string = SourceString(arguments['source_string'])
        for key in set(ATTR_MAPPING.keys()) & set(arguments.keys()):
            setattr(string, ATTR_MAPPING[key], arguments[key])
        if self.filename is not None:
            # Add to occurrences
            string.occurrences = (string.occurrences +
                                  ["{}:{}".format(self.filename, node.lineno)])
        self.strings.add(string)
        self.generic_visit(node)

    @staticmethod
    def _is_subset(name, import_path):
        """ Usage:

            >>> _is_subset(['transifex'], ['transifex.native'])
            <<< (True, 1)
            >>> _is_subset(['transifex', 'native'],
            ...            ['transifex', 'native', 't'])
            <<< (True, 2)
            >>> _is_subset(['transifex', 'utils'], ['transifex', 'native'])
            <<< (False, None)
        """

        name = iter(name)
        import_path = iter(import_path)

        parts_matched = 0
        while True:
            try:
                left = next(name)
            except StopIteration:
                return True, parts_matched
            try:
                right = next(import_path)
            except StopIteration:
                return False, None

            if left != right:
                return False, None
            else:
                parts_matched += 1

    @staticmethod
    def _import_from_path(import_path):
        # import_path: ['transifex', 'native', 'tx', 'translate']
        module = None
        for i in range(-1, -len(import_path), -1):
            # left, right: ['transifex', 'native'], ['tx', 'translate']
            left, right = import_path[:i], import_path[i:]
            try:
                module = importlib.import_module('.'.join(left))
            except ModuleNotFoundError:
                continue
            else:
                break
        if module is None:
            raise ValueError("Cannot import '{}'".
                             format('.'.join(import_path)))
        # module: transifex.native
        # right: ['tx', 'translate']
        function = module
        for attr in right:
            try:
                # function: tx, then: tx.translate
                function = getattr(function, attr)
            except AttributeError:
                raise ValueError("Cannot import '{}'".
                                 format('.'.join(import_path)))
        return function

    @classmethod
    def _extract_arguments(cls, func, node):
        """ Extracts all constant arguments from an AST `node` that describes a
            function call. The names of the arguments are retrieved from the
            signature of `func`.

            Usage:

                >>> from transifex.native import t

                >>> node = ast.parse('t("string")').body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string"}

                >>> node = ast.parse('t(source_string="string")').body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string"}

                >>> node = ast.parse('t("string", "fr")').body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string", 'language_code': "fr"}

                >>> node = ast.parse(
                ...     't("string", "fr", "context")'
                ... ).body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string",
                ...  'language_code': "fr",
                ...  '_context': "context"}

                >>> node = ast.parse(
                ...     't("string", "fr", _context="context")'
                ... ).body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string",
                ...  'language_code': "fr",
                ...  '_context': "context"}

                >>> node = ast.parse(
                ...     't("string", _tags=["a", "b"])'
                ... ).body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string", '_tags': ["a", "b"]}

                >>> node = ast.parse(
                ...     't("hello {username}", username="Bob")'
                ... ).body[0].value
                >>> _extract_arguments(t, node)
                <<< {'source_string': "string"}
        """

        args = node.args
        kwargs = {keyword.arg: keyword.value
                  for keyword in node.keywords
                  if keyword.arg is not None}

        try:
            signature = inspect.signature(func)
        except AttributeError:
            # Python 2
            argspec = inspect.getargspec(func)
            defaults = argspec.defaults or []
            if argspec.args[0] == "self":
                del argspec.args[0]
            arguments = {}
            for field, arg in zip(argspec.args, args):
                arguments[field] = arg
            for i, field in enumerate(argspec.args[len(args):]):
                if len(defaults) > i and defaults[i] is not None:
                    arguments[field] = ast.\
                        parse('{}'.format(repr((defaults)[i]))).\
                        body[0].value
            for field, arg in kwargs.items():
                if field in argspec.args:
                    arguments[field] = arg
        else:
            # Python 3
            arguments = signature.bind(*args, **kwargs).arguments

        result = {}
        for key, value in arguments.items():
            try:
                result[key] = cls._get_constant_value(value)
            except TypeError:
                pass
        return result

    @classmethod
    def _get_constant_value(cls, node, include_lists=True):
        """ Extracts the value from an AST `node` that describe a constant. If
            `include_lists` is True, it will also support a flat list of
            constants.

            Usage:

                >>> node = ast.parse('1').body[0].value
                >>> _get_constant_value(node)
                <<< 1

                >>> node = ast.parse('"foo"').body[0].value
                >>> _get_constant_value(node)
                <<< 'foo'

                >>> node = ast.parse('True').body[0].value
                >>> _get_constant_value(node)
                <<< True

                >>> node = ast.parse('[1, "b"]').body[0].value
                >>> _get_constant_value(node)
                <<< [1, 'b']

                >>> node = ast.parse('variable_name').body[0].value
                >>> _get_constant_value(node)
                <<< TypeError: node 'Name(id='variable_name', ctx=Load())' is not a constant  # noqa
        """
        if PYVER == 3:
            if isinstance(node, ast.Constant):
                return node.value
            elif include_lists and isinstance(node, ast.List):
                return [cls._get_constant_value(elt, include_lists=False)
                        for elt in node.elts]
        if PYVER == 2:
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.Str):
                return node.s
            elif (isinstance(node, ast.Name) and
                    node.id in ('True', 'False', 'None')):
                if node.id == "True":
                    return True
                elif node.id == "False":
                    return False
                elif node.id == "None":
                    return None
                else:  # pragma: no cover
                    raise Exception("Unreachable code")
            elif include_lists and isinstance(node, ast.List):
                return [cls._get_constant_value(elt, include_lists=False)
                        for elt in node.elts]
        raise TypeError("node '{}' is not a constant".
                        format(ast.dump(node)))


def extract(filename, encoding="UTF-8", import_paths=None):
    visitor = CallDetectionVisitor2(filename=filename,
                                    import_paths=import_paths)
    with io.open(filename, encoding=encoding) as f:
        visitor.visit(ast.parse(f.read()))
    return visitor.strings
