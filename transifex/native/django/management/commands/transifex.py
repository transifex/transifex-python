from __future__ import absolute_import, unicode_literals

from django.core.management import BaseCommand, CommandParser

from .migrate import Migrate
from .push import Push


class Command(BaseCommand):
    """ Main `transifex` CLI command that includes the following subcommands:

        - push: Detects translatable strings in Django templates and Python
                files, based on the syntax of Transifex Native and pushes them
                as source strings to Transifex.

        - migrate: Migrates files using the Django i18n syntax to Transifex
                   Native syntax.

        Usage Example:
            `$./manage.py transifex <subcommand> [options]`
    """

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.subcommands = {'push': Push(), 'migrate': Migrate()}

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            def __init__(self, **kwargs):
                super(SubParser, self).__init__(cmd, **kwargs)

        # common arguments to all subcommands
        parser.add_argument(
            '--domain', '-d', default='django', dest='domain',
            help='The domain of the message files (default: "django").',
        )

        subparsers = parser.add_subparsers(title="subcommands",
                                           dest="subcommand",
                                           help="Available subcommands",
                                           parser_class=SubParser)
        subparsers.required = True

        for subcommand in self.subcommands.values():
            subcommand.add_arguments(subparsers)

    def handle(self, *args, **options):
        subcommand = options['subcommand']
        self.subcommands[subcommand].handle(*args, **options)
