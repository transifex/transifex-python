from __future__ import unicode_literals

import fnmatch
import io
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.core.management.utils import handle_extensions
from django.utils.functional import cached_property

from transifex.native.django.management.common import TranslatableFile
from transifex.native.tools.migrations.review import (FileReviewPolicy,
    LowConfidenceFileReviewPolicy, LowConfidenceStringReviewPolicy,
    NoopReviewPolicy, StringReviewPolicy)
from transifex.native.tools.migrations.save import (BackupSavePolicy,
                                                    ReplaceSavePolicy,
                                                    NewFileSavePolicy,
                                                    NoopSavePolicy)

SAVE_POLICY_OPTIONS = {
    NoopSavePolicy.name: 'no changes will be saved\n',
    NewFileSavePolicy.name: 'migrated content will be saved in a new file, '
                            'named <filename>__native.<extension>\n',
    BackupSavePolicy.name: 'migrated content will be saved directly in the '
                           'original file path, and a backup will also be '
                           'saved in <filename>.<extension>.bak\n',
    ReplaceSavePolicy: 'migrated content will be saved in the original file',
}

REVIEW_POLICY_OPTIONS = {
    NoopReviewPolicy.name: 'everything will be done automatically without '
                           'having a chance to review anything\n',
    FileReviewPolicy.name: 'you get a chance to review each migrated file '
                           'before it is saved\n',
    StringReviewPolicy.name: 'you get a chance to review each string of each '
                             'file before the file is saved\n',
    LowConfidenceFileReviewPolicy.name: 'you get a chance to review each '
                                        'migrated file that includes at least '
                                        'one string that has a low migration '
                                        'confidence\n',
    LowConfidenceStringReviewPolicy.name: 'you get a chance to review each '
                                          'string that has a low migration '
                                          'confidence\n',
}
from transifex.native.django.tools.migrations.templatetags import DjangoTagMigrationBuilder
from transifex.native.tools.migrations.execution import (MigrationExecutor,
    REVIEW_POLICY_OPTIONS, SAVE_POLICY_OPTIONS)

EXTENSIONS = ['html', 'txt', 'py']


def pretty_options(options_dict):
    items = [(k, v) for k, v in options_dict.items()]
    return '\n'.join([' - "{}": {}'.format(x[0], x[1]) for x in items])


class Command(BaseCommand):
    """Migrates files using the Django i18n syntax to Transifex Native syntax.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain', '-d', default='django', dest='domain',
            help='The domain of the message files (default: "django").',
        )
        parser.add_argument(
            '--file', '-f', dest='files', action='append',
            help='The relative paths of the files to migrate. Separate '
                 'multiple paths with commas, or use -f multiple times.',
        )
        parser.add_argument(
            '--path', '-p', dest='path',
            help='The path of the files to migrate. Finds files recursively.',
        )
        parser.add_argument(
            '--save', dest='save_policy', default='new',
            help=(
                'Determines where the migrated content will be saved: \n' +
                pretty_options(SAVE_POLICY_OPTIONS)
            ),
        )
        parser.add_argument(
            '--review', dest='review_policy', default='file',
            help=(
                'Determines where the migrated content will be saved: \n' +
                pretty_options(REVIEW_POLICY_OPTIONS)
            ),
        )

    def handle(self, *args, **options):
        self.ignore_patterns = []
        self.verbosity = options['verbosity']
        self.path = options['path']

        options['files'] = set(options['files'] or [])
        self.files = options['files']
        self.extensions = handle_extensions(EXTENSIONS)

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
            files = self._find_files(self.path)

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

    def _find_files(self, root):
        """Get all files in the given root.

        :param basestring root: the root path to search in
        :return: a list of TranslatableFile objects
        :rtype: list
        """

        def is_ignored(path, ignore_patterns):
            """Check if the given path should be ignored or not."""
            filename = os.path.basename(path)

            def ignore(pattern):
                return fnmatch.fnmatchcase(filename, pattern) or fnmatch.fnmatchcase(
                    path, pattern)

            return any(ignore(pattern) for pattern in ignore_patterns)

        ignore_patterns = [os.path.normcase(p) for p in self.ignore_patterns]
        dir_suffixes = {'%s*' % path_sep for path_sep in {'/', os.sep}}
        norm_patterns = []
        for p in ignore_patterns:
            for dir_suffix in dir_suffixes:
                if p.endswith(dir_suffix):
                    norm_patterns.append(p[:-len(dir_suffix)])
                    break
            else:
                norm_patterns.append(p)

        all_files = []
        ignored_roots = []
        if self.settings_available:
            ignored_roots = [os.path.normpath(p) for p in
                             (settings.MEDIA_ROOT, settings.STATIC_ROOT) if p]

        for dirpath, dirnames, filenames in os.walk(root, topdown=True,
                                                    followlinks=False):
            for dirname in dirnames[:]:
                if (is_ignored(os.path.normpath(os.path.join(dirpath, dirname)),
                               norm_patterns) or
                        os.path.join(os.path.abspath(dirpath),
                                     dirname) in ignored_roots):
                    dirnames.remove(dirname)
                    self.verbose('Ignoring directory %s' % dirname)
                elif dirname == 'locale':
                    dirnames.remove(dirname)

            for filename in filenames:
                file_path = os.path.normpath(os.path.join(dirpath, filename))
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in self.extensions or is_ignored(file_path,
                                                                 self.ignore_patterns):
                    self.verbose('Ignoring file %s in %s' %
                                 (filename, dirpath))
                else:
                    all_files.append(
                        TranslatableFile(dirpath.lstrip('./'), filename)
                    )
        return sorted(all_files)

    def _read_file(self, path, encoding):
        with io.open(path, 'r', encoding=encoding) as fp:
            return fp.read()

    @cached_property
    def settings_available(self):
        try:
            settings.LOCALE_PATHS
        except ImproperlyConfigured:
            self.verbose("Running without configured settings.")
            return False
        return True

    def verbose(self, msg):
        if self.verbosity > 1:
            print(msg)

    def output(self, msg):
        print(msg)
