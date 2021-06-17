from __future__ import absolute_import, unicode_literals

import os

import transifex.native.tools.migrations.gettext as gettext
from django.conf import settings
from django.core.management.utils import handle_extensions
from transifex.native.django.management.common import TranslatableFile
from transifex.native.django.management.utils.base import (CommandMixin,
                                                           pretty_options)
from transifex.native.django.tools.migrations.templatetags import \
    DjangoTagMigrationBuilder
from transifex.native.tools.migrations.execution import (MARK_POLICY_OPTIONS,
                                                         REVIEW_POLICY_OPTIONS,
                                                         SAVE_POLICY_OPTIONS,
                                                         MigrationExecutor,
                                                         migrate_text)
from transifex.native.tools.migrations.gettext import (GettextMethods,
                                                       GettextMigrationBuilder)

MIGRATE_EXTENSIONS = ['html', 'txt', 'py']


# These are the functions + arguments of the gettext wrappers
# provided in Django
GETTEXT_FUNCTIONS = {
    gettext.GETTEXT: (
        'django.utils.translation.gettext',
        [('message', gettext.KEYWORD_STRING)],
    ),
    gettext.UGETTEXT: (
        'django.utils.translation.ugettext',
        [('message', gettext.KEYWORD_STRING)],
    ),
    gettext.NGETTEXT: (
        'django.utils.translation.ngettext',
        [
            ('singular', gettext.KEYWORD_ONE),
            ('plural', gettext.KEYWORD_OTHER),
            ('number', gettext.KEYWORD_CNT),
        ]
    ),
    gettext.UNGETTEXT: (
        'django.utils.translation.ungettext',
        [
            ('singular', gettext.KEYWORD_ONE),
            ('plural', gettext.KEYWORD_OTHER),
            ('number', gettext.KEYWORD_CNT),
        ]
    ),
    gettext.PGETTEXT: (
        'django.utils.translation.pgettext',
        [
            ('context', gettext.KEYWORD_CONTEXT),
            ('message', gettext.KEYWORD_STRING),
        ]
    ),
    gettext.NPGETTEXT: (
        'django.utils.translation.npgettext',
        [
            ('context', gettext.KEYWORD_CONTEXT),
            ('singular', gettext.KEYWORD_ONE),
            ('plural', gettext.KEYWORD_OTHER),
            ('number', gettext.KEYWORD_CNT),
        ]
    ),
}
# Add lazy variants with identical arguments as the corresponding non-lazy ones
for func_name, lazy_func_name in gettext.LAZY_MAPPING.items():
    item = GETTEXT_FUNCTIONS[func_name]
    GETTEXT_FUNCTIONS[lazy_func_name] = (
        item[0] + gettext.LAZY_SUFFIX, item[1]
    )

# This is the import statement that will replace gettext imports
T_IMPORT = 'from transifex.native.django import {}'


class Migrate(CommandMixin):
    """Migrate files using the Django i18n syntax to Transifex Native syntax."""

    def add_arguments(self, subparsers):
        parser = subparsers.add_parser(
            'migrate',
            help=("Migrate files using the Django i18n syntax to Transifex "
                  "Native syntax")
        )
        parser.add_argument(
            '--file', '-f', dest='files', action='append',
            help=('The relative paths of the files to migrate. Separate '
                  'multiple paths with commas, or use -f multiple times.'),
        )
        parser.add_argument(
            '--path', '-p', dest='path',
            help='The path of the files to migrate. Finds files recursively.',
        )
        parser.add_argument(
            '--text', '-t', dest='text', default='',
            help='If set, the migration command will display the result '
                 'of converting the given text to Transifex Native syntax, '
                 'and then exit.',
        )
        parser.add_argument(
            '--save', dest='save_policy', default='new',
            help=('Determines where the migrated content will be saved: \n' +
                  pretty_options(SAVE_POLICY_OPTIONS)),
        )
        parser.add_argument(
            '--review', dest='review_policy', default='file',
            help=('Determines where the migrated content will be saved: \n' +
                  pretty_options(REVIEW_POLICY_OPTIONS)),
        )
        parser.add_argument(
            '--mark', dest='mark_policy', default='none',
            help=('Determines if anything gets marked for proofreading: \n' +
                  pretty_options(MARK_POLICY_OPTIONS)),
        )
        parser.add_argument(
            '--verbose', '-v', action='store_true',
            dest='verbose_output', default=False,
            help=('Verbose output'),
        )

    def handle(self, *args, **options):
        self.domain = options['domain']
        self.verbose_output = options['verbose_output']
        self.ignore_patterns = []
        self.path = options['path']
        self.files = set(options['files'] or [])
        exts = MIGRATE_EXTENSIONS
        self.extensions = handle_extensions(exts)
        self.stats = {
            'processed_files': 0, 'migrations': [], 'saved': [], 'errors': [],
        }

        # Create a reusable migrator for templates code
        self.django_migration_builder = DjangoTagMigrationBuilder()
        self.gettext_migration_builder = GettextMigrationBuilder(
            methods=GettextMethods(**GETTEXT_FUNCTIONS),
            import_statement=T_IMPORT,
        )

        # -- Text mode: simply transform the given text and exit
        text = options['text']
        if text:
            migrate_text(text, self._migrate_text)
            return

        # -- File mode: read all files based on the given options and migrate
        # each of them
        self.executor = MigrationExecutor(
            options, file_migrator_func=self._migrate_file,
        )

        # Show an intro message
        self.executor.show_intro()

        # If specific files are defined, use those
        if self.files:
            dirpath = os.getcwd()
            files = [
                TranslatableFile(dirpath, filename)
                for filename in self.files
            ]
        # Else search the file path for supported files
        else:
            files = self._find_files(self.path, 'migrate')

        # Execute the migration
        self.executor.migrate_files(files)

    def _migrate_text(self, text):
        """Create a migration to Native syntax for the given string.

        Supports both Python files and Django template files.

        :param unicode text: the code string
        :return: an object with the migration info
        :rtype: FileMigration
        """
        # Template code
        if '{%' in text:
            return self.django_migration_builder.build_migration(text, '')
        # Python code
        else:
            return self.gettext_migration_builder.build_migration(text, '')

    def _migrate_file(self, translatable_file):
        """Create a migration to Native syntax for the given file.

        Supports both Python files and Django template files.

        :param TranslatableFile translatable_file: the file to search
        :return: an object with the migration info
        :rtype: FileMigration
        """
        self.verbose('Processing file %s in %s' % (
            translatable_file.file, translatable_file.dirpath
        ))
        encoding = (
            settings.FILE_CHARSET if (
                hasattr(settings, 'FILE_CHARSET')
                and self.settings_available
            )
            else 'utf-8'
        )
        try:
            src_data = self._read_file(translatable_file.path, encoding)
        except UnicodeDecodeError as e:
            self.verbose(
                'UnicodeDecodeError: skipped file %s in %s (reason: %s)' % (
                    translatable_file.file, translatable_file.dirpath, e,
                )
            )
            return None

        _, extension = os.path.splitext(translatable_file.file)

        # Python file
        if extension == '.py':
            return self.gettext_migration_builder.build_migration(
                src_data, translatable_file.path,
            )

        # Template file
        return self.django_migration_builder.build_migration(
            src_data, translatable_file.path, encoding,
        )
