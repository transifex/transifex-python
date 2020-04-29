from __future__ import absolute_import, unicode_literals

import os

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
                                                         MigrationExecutor)

MIGRATE_EXTENSIONS = ['html', 'txt', 'py']


class Migrate(CommandMixin):
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

    def handle(self, *args, **options):
        self.domain = options['domain']
        self.verbosity = options['verbosity']
        self.ignore_patterns = []
        self.path = options['path']
        self.files = set(options['files'] or [])
        exts = MIGRATE_EXTENSIONS
        self.extensions = handle_extensions(exts)
        self.stats = {
            'processed_files': 0, 'migrations': [], 'saved': [], 'errors': [],
        }
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

        # Create a reusable migrator for templates code
        self.django_migration_builder = DjangoTagMigrationBuilder()

        # Execute the migration
        self.executor.migrate_files(files)

    def _migrate_file(self, translatable_file):
        """Extract source strings from the given file.

        Supports both Python files and Django template files.

        :param TranslatableFile translatable_file: the file to search
        :return: an object with the migration info
        :rtype: FileMigration
        """
        self.verbose('Processing file %s in %s' % (
            translatable_file.file, translatable_file.dirpath
        ))
        encoding = (
            settings.FILE_CHARSET if self.settings_available
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
            return None  # TODO

        # Template file
        return self.django_migration_builder.build_migration(
            src_data, translatable_file.path, encoding,
        )
