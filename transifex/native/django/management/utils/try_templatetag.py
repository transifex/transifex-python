from __future__ import absolute_import, print_function, unicode_literals

import itertools
import json
import re
import sys

from django.template import Context, Template
from django.utils import translation
from transifex.common.console import Color
from transifex.native.django.management.utils.base import CommandMixin

try:
    raw_input
except NameError:
    pass
else:
    input = raw_input  # pragma no cover  # noqa


def fancy_input(text, *choices):
    """ Multiple choice input

        Given arguments ('Which tag do you want to use?',
                         ('t', 't', '{% t ... %}'),
                         ('ut', 'ut', '{% ut ... %}'))

        It will render:

            ===> Which tag do you want to use?
            .... 1. t                 : {% t ... %}
            .... 2. ut                : {% ut ... %}
            .... [examples: "1", "1 3"; empty input for all choices]

        The return value will be a list of "choices", ie the first items in the
        3-tuples.
    """

    print()
    Color.echo("[yel]===>[end] {}".format(text))
    for i, (_, display, example) in enumerate(choices, 1):
        line = "[yel]....[end] [warn]{}[end]. {:18}".format(i, display)
        if example:
            line += ": [cyan]{}[end]".format(example)
        Color.echo(line)

    while True:
        Color.echo('.... [examples: "[warn]1[end]", "[warn]1 3[end]"; '
                   '[warn]empty input[end] for all choices]')
        answer = input("===> ")
        if answer.strip() == "":
            return [choice for choice, _, _ in choices]
        try:
            answer = [int(choice) - 1 for choice in answer.split()]
        except Exception:
            pass
        else:
            if all((0 <= choice < len(choices) for choice in answer)):
                return [choices[choice][0] for choice in answer]
        print("Invalid answer, please try again")


def make_tests(tag_names, sources, source_filters, params, param_filters,
               asvars, asvar_filters, blocks, context_values):
    """ Use `itertools.product` to create a set of tests. Each argument should
        be a list with at least one item (otherwise `product` will return an
        empty result). It delegates each test creation to the `make_test`
        method.
    """

    results = []
    for (tag_name, source, source_filter, param, param_filter, asvar,
            asvar_filter, block,
            context_value) in itertools.product(
                tag_names, sources, source_filters, params, param_filters,
                asvars, asvar_filters, blocks, context_values
    ):
        try:
            test = make_test(tag_name, source, source_filter, param,
                             param_filter, asvar, asvar_filter, block,
                             context_value)
        except TypeError:
            pass
        else:
            results.append(test)

    # Remove duplicates
    results = [(template, json.dumps(context))
               for template, context in results]
    results = sorted(set(results))
    results = [(template, json.loads(context))
               for template, context in results]
    return results


def make_test(tag_name, source=None, source_filter=None, param=None,
              param_filter=None, asvar=None, asvar_filter=None, block=None,
              context_value=None):
    """ Compose a template and context for testing based on the arguments.  """

    if not source and not block:
        raise TypeError("At least one of 'source' or 'block' must be "
                        "specified")

    result = ['{% ', tag_name, ' ']
    context_vars = []
    if source:
        if source[0] not in ('"', "'"):
            context_vars.append(source)
        for match in re.findall(r'\{[\w_]+\}', source):
            context_vars.append(match[1:-1])
        result.append(source)
    if source_filter:
        result.extend(['|', source_filter])
    if param:
        context_vars.append(param)
        result.extend([' ', param, '=', param])
        if param_filter:
            result.extend(['|', param_filter])
    if asvar:
        result.extend([' as ', asvar])
    result.append(' %}')
    if not source and block:
        for match in re.findall(r'\{[\w_]+\}', block):
            context_vars.append(match[1:-1])
        result.extend([block, '{% end', tag_name, ' %}'])
    if asvar:
        result.extend(['{{ ', asvar])
        if asvar_filter:
            result.extend(['|', asvar_filter])
        result.extend([' }}'])

    context = {}
    if context_value is not None:
        context = {context_var: context_value for context_var in context_vars}

    return ''.join(result), context


def test(template_str, context_dict=None, autoescape=True, i=''):
    """ Use the django templating engine to run a test.

        Arguments:

        :param template_str: The template to render
        :param context_dict: The context to render the template against
        :param autoescape:   Pretend the django templating engine was setup
                             with autoescape or not (in most real use-cases, it
                             will have been set up with autoescape=True)
        :param i:            Prepend the output with this in order to help
                             distinguish tests when multiple are run

        Information about (auto)escaping in django:
        https://docs.djangoproject.com/en/3.0/ref/templates/language/#automatic-html-escaping  # noqa
    """

    if context_dict is None:
        context_dict = {}
    context = Context(dict(context_dict), autoescape=autoescape)
    template = ('{% load transifex %}' + template_str)
    try:
        result = Template(template).render(context)
    except Exception:
        print(template_str, context_dict, autoescape)
        raise
    Color.echo("[warn]{i:4}[end]. [cyan]Template[end]:    {template}".
               format(i=i, template=template_str))
    Color.echo("      [cyan]Context[end]:     {context}".
               format(context=context_dict))
    Color.echo("      [cyan]Autoescape[end]:  {autoescape}".
               format(autoescape=autoescape))
    Color.echo("      [cyan]Result[end]:      [green]{result}[end]".
               format(result=result))
    print()


class TryTemplatetag(CommandMixin):
    """ Command to help users try cornercases when using our templatetag,
        especially related to escaping. See the help attribute of main parser
        in `add_arguments` for details.
    """

    def add_arguments(self, subparsers):
        parser = subparsers.add_parser(
            'try-templatetag',
            help="""
                Test the transifex templatetag against multiple variations of
                test cases.

                We recommend you generate your test cases with the
                `--interactive` option. At the end, it will provide you with
                the detailed invocation you would need in order to repeat the
                same tests, which you can edit to fine-tune your testing.
            """
        )

        parser.add_argument('-i', '--interactive', action="store_true",
                            dest="interactive",
                            help="Interactive dialog for setting up tests")
        parser.add_argument('--tag-names', default='', dest="tag_names")
        parser.add_argument('--sources', default='', dest="sources")
        parser.add_argument('--source-filters', default='',
                            dest="source_filters")
        parser.add_argument('--params', default='', dest="params")
        parser.add_argument('--param-filters', default='',
                            dest="param_filters")
        parser.add_argument('--asvars', default='', dest="asvars")
        parser.add_argument('--asvar-filters', default='',
                            dest="asvar_filters")
        parser.add_argument('--blocks', default='', dest="blocks")
        parser.add_argument('--context-values', default='',
                            dest="context_values")
        parser.add_argument('--autoescapes', default='', dest="autoescapes")

    def handle(self, *args, **options):
        translation.activate('en')

        tag_names = options.get('tag_names', '').split(',')
        sources = options.get('sources', '').split(',')
        source_filters = options.get('source_filters', '').split(',')
        params = options.get('params', '').split(',')
        param_filters = options.get('param_filters', '').split(',')
        asvars = options.get('asvars', '').split(',')
        asvar_filters = options.get('asvar_filters', '').split(',')
        blocks = options.get('blocks', '').split(',')
        context_values = options.get('context_values', '').split(',')
        autoescapes = options.get('autoescapes', '').split(',')

        if options['interactive']:
            if tag_names == ['']:
                tag_names = fancy_input("Which tag do you want to use?",
                                        ('t', 't', '{% t ... %}'),
                                        ('ut', 'ut', '{% ut ... %}'))
            if sources == ['']:
                sources = fancy_input(
                    "What type of source string do you want to use?",
                    ('', '<Nothing>', None),
                    ('source', "Variable", '{% t source ... %}'),
                    ('"hello {var}"',
                     "String without XML",
                     '{% t "hello {var}" ... %}'),
                    ('"<xml>hello</xml> {var}"',
                     "String with XML",
                     '{% t "<xml>hello</xml> {var}" ... %}'),
                )
            if source_filters == ['']:
                source_filters = fancy_input(
                    "What filters do you want to apply to the source string?",
                    ('', '<None>', '{% t "hello {var}" ... %}'),
                    ('safe', 'safe', '{% t "hello {var}"|safe ... %}'),
                    ('escape', 'escape', '{% t "hello {var}"|escape ... %}'),
                    ('escapejs', 'escapejs',
                     '{% t "hello {var}"|escapejs ... %}'),
                )
            if params == ['']:
                params = fancy_input(
                    "Do you want to pass a parameter to the tag?",
                    ('var', 'Yes', '{% t "hello {var}" var=var ... %}'),
                    ('', 'No', None),
                )
            if param_filters == ['']:
                param_filters = fancy_input(
                    "What filters do you want to apply to the parameter (if "
                    "you added one)?",
                    ('', '<None>', '{% t "hello {var} var=var ..." %}'),
                    ('safe', 'safe', '{% t "hello {var} var=var|safe ..." %}'),
                    ('escape', 'escape',
                     '{% t "hello {var} var=var|escape ..." %}'),
                    ('escapejs', 'escapejs',
                     '{% t "hello {var} var=var|escapejs ..." %}'),
                )
            if asvars == ['']:
                asvars = fancy_input(
                    "Do you want to save the translation to a context "
                    "variable?",
                    ('', 'No', '{% t ... %}'),
                    ('text', 'Yes', '{% t ... as text %}{{ text }}'),
                )
            if asvar_filters == ['']:
                asvar_filters = fancy_input(
                    "What filters do you want to apply to the saved variable "
                    "(if you chose one)?",
                    ('', '<None>', '{% t ... as text" %}{{ text }}'),
                    ('safe', 'safe', '{% t ... as text" %}{{ text|safe }}'),
                    ('escape', 'escape',
                     '{% t ... as text" %}{{ text|escape }}'),
                    ('escapejs', 'escapejs',
                     '{% t ... as text" %}{{ text|escapejs }}'),
                )
            if blocks == ['']:
                blocks = fancy_input(
                    "What do you want to use as the content of the translated "
                    "block (if no source string was one of the options you "
                    "chose)?",
                    ('', '<Nothing>', None),
                    ('hello {var}',
                     "String without XML",
                     '{% t ... %}hello {var}{% endt %}'),
                    ('<xml>hello</xml> {var}',
                     "String with XML",
                     '{% t ... %}<xml>hello</xml> {var}{% endt %}'),
                )
            if context_values == ['']:
                context_values = fancy_input(
                    "What values do you want to use for your context "
                    "variables?",
                    ('world', 'String without XML', None),
                    ('<xml>world</xml>', 'String with XML', None),
                )
            if autoescapes == ['']:
                autoescapes = fancy_input(
                    "Do you want to render the template using autoescape?",
                    ('yes', 'Yes', None),
                    ('no', 'No', None),
                )

        if autoescapes == ['']:
            autoescapes = ['yes']
        autoescapes = list(set((
            {'yes': True, 'no': False}.get(autoescape.lower(), True)
            for autoescape in autoescapes
        )))

        tests = make_tests(tag_names, sources, source_filters, params,
                           param_filters, asvars, asvar_filters, blocks,
                           context_values)

        print()
        for i, ((template, context), autoescape) in enumerate(
                itertools.product(tests, autoescapes), 1):
            test(template, context, autoescape, i)

        if options['interactive']:
            command = [sys.argv[0], sys.argv[1], sys.argv[2]]
            command.append("--tag-names={}".format(','.join(tag_names)))
            if sources != ['']:
                command.append("--sources='{}'".format(','.join(sources)))
            if source_filters != ['']:
                command.append("--source-filters={}".
                               format(','.join(source_filters)))
            if params != ['']:
                command.append("--params={}".format(','.join(params)))
            if param_filters != ['']:
                command.append("--param-filters={}".
                               format(','.join(param_filters)))
            if asvars != ['']:
                command.append("--asvars={}".format(','.join(asvars)))
            if asvar_filters != ['']:
                command.append("--asvar-filters={}".
                               format(','.join(asvar_filters)))
            if blocks != ['']:
                command.append("--blocks='{}'".format(','.join(blocks)))
            if context_values != ['']:
                command.append("--context-values='{}'".
                               format(','.join(context_values)))
            command.append("--autoescapes={}".format(','.join((
                {True: 'yes', False: 'no'}[autoescape]
                for autoescape in autoescapes
            ))))
            command = ' '.join(command)
            print()
            print("In order to run the same tests again later, use the "
                  "following command:")
            print(command)
