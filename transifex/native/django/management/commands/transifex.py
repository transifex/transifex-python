from __future__ import absolute_import, unicode_literals

import fnmatch
import io
import json
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand, CommandParser
from django.core.management.utils import handle_extensions
from django.utils.encoding import force_text
from django.utils.functional import cached_property
from transifex.native import tx
from transifex.native.django.management.common import (NO_LOCALE_DIR,
                                                       SourceStringCollection,
                                                       TranslatableFile)
from transifex.native.django.tools.migrations.templatetags import \
    DjangoTagMigrationBuilder
from transifex.native.django.utils.templates import \
    extract_transifex_template_strings
from transifex.native.parsing import Extractor
from transifex.native.tools.migrations.execution import (MARK_POLICY_OPTIONS,
                                                         REVIEW_POLICY_OPTIONS,
                                                         SAVE_POLICY_OPTIONS,
                                                         MigrationExecutor)

MIGRATE_EXTENSIONS = ['html', 'txt', 'py']


def pretty_options(options_dict):
    items = [(k, v) for k, v in options_dict.items()]
    return '\n'.join([' - "{}": {}'.format(x[0], x[1]) for x in items])


class Command(BaseCommand):
    """Main `transifex` CLI command that includes the following subcommands:

    - push: Detects translatable strings in Django templates and Python files,
            based on the syntax of Transifex Native and pushes them as source strings
            to Transifex.

    - migrate: Migrates files using the Django i18n syntax to Transifex Native syntax.

    Usage Example:
        `$./manage.py transifex <subcommand> [options]`
    """

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
        push_parser = subparsers.add_parser('push', help="Detect translatable strings in "
                                            "Django templates and Python files and push them "
                                            "as source strings to Transifex")
        migrate_parser = subparsers.add_parser(
            'migrate', help="Migrate files using the Django i18n syntax to Transifex Native syntax")

        # push subcommand arguments
        push_parser.add_argument(
            '--extension', '-e', dest='extensions', action='append',
            help='The file extension(s) to examine (default: "html,txt,py", or "js" '
                 'if the domain is "djangojs"). Separate multiple extensions with '
                 'commas, or use -e multiple times.',
        )
        push_parser.add_argument(
            '--purge', '-p', action='store_true', dest='purge', default=False,
            help='Replace the entire resource content with the pushed content '
                 'of this request. If not provided (the default), then append '
                 'the source content of this request to the existing resource '
                 'content.',
        )
        push_parser.add_argument(
            '--symlinks', '-s', action='store_true', dest='symlinks', default=False,
            help='Follows symlinks to directories when examining source code '
                 'and templates for translation strings.',
        )
        # migrate subcommand arguments
        migrate_parser.add_argument(
            '--file', '-f', dest='files', action='append',
            help='The relative paths of the files to migrate. Separate '
                 'multiple paths with commas, or use -f multiple times.',
        )
        migrate_parser.add_argument(
            '--path', '-p', dest='path',
            help='The path of the files to migrate. Finds files recursively.',
        )
        migrate_parser.add_argument(
            '--save', dest='save_policy', default='new',
            help=(
                'Determines where the migrated content will be saved: \n' +
                pretty_options(SAVE_POLICY_OPTIONS)
            ),
        )
        migrate_parser.add_argument(
            '--review', dest='review_policy', default='file',
            help=(
                'Determines where the migrated content will be saved: \n' +
                pretty_options(REVIEW_POLICY_OPTIONS)
            ),
        )
        parser.add_argument(
            '--mark', dest='mark_policy', default='none',
            help=(
                'Determines if anything gets marked for proofreading: \n' +
                pretty_options(MARK_POLICY_OPTIONS)
            ),
        )

    def handle(self, *args, **options):
        self.subcommand = options['subcommand']
        self.domain = options['domain']
        self.verbosity = options['verbosity']
        self.ignore_patterns = []

        if self.subcommand == 'push':
            self.purge = options['purge']
            self.symlinks = options['symlinks']
            extensions = options['extensions']
            if self.domain == 'djangojs':
                exts = extensions if extensions else ['js']
            else:
                exts = extensions if extensions else ['html', 'txt', 'py']
            func = self.handle_push
        elif self.subcommand == 'migrate':
            self.path = options['path']
            self.files = set(options['files'] or [])
            exts = MIGRATE_EXTENSIONS
            func = self.handle_migrate
        self.extensions = handle_extensions(exts)
        func(*args, **options)

    def handle_push(self, *args, **options):
        self.locale_paths = []
        self.default_locale_path = None

        self.string_collection = SourceStringCollection()

        # Create an extractor for Python files, to reuse for all files
        self.python_extractor = Extractor()
        # Support `t()` and `ut()` calls made on the Django module.
        self.python_extractor.register_functions(
            'transifex.native.django.t',
            'transifex.native.django.ut',
        )

        self.stats = {'processed_files': 0, 'strings': []}

        # Search all related files and collect translatable strings,
        # storing them in `self.string_collection`
        self.collect_strings()

        # Push the strings to the CDS
        self.push_strings()

    def handle_migrate(self, *args, **options):
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
            files = self._find_files(self.path)

        # Create a reusable migrator for templates code
        self.django_migration_builder = DjangoTagMigrationBuilder()

        # Execute the migration
        self.executor.migrate_files(files)

    def collect_strings(self):
        """Search all related files, collect and store translatable strings.

        Stores found strings in `self.string_collection`.
        """
        self.output('Parsing all files to detect translatable content...')
        files = self._find_files('.')
        for f in files:
            extracted = self._extract_strings(f)
            self.string_collection.extend(extracted)
            self.stats['processed_files'] += 1
            if extracted and len(extracted):
                self.stats['strings'].append((f.file, len(extracted)))

        self._show_collect_results()

    def push_strings(self):
        """Push strings to the CDS."""
        total = len(self.string_collection.strings)
        if total == 0:
            self.output('There are no strings to push to Transifex.')
            return

        self.output('Pushing {} source strings to Transifex...'.format(total))
        status_code, response_content = tx.push_source_strings(
            self.string_collection.strings.values(), self.purge
        )
        self._show_push_results(status_code, response_content)

    def _extract_strings(self, translatable_file):
        """Extract source strings from the given file.

        Supports both Python files and Django template files.

        :param TranslatableFile translatable_file: the file to search
        :return: a list of SourceString objects
        :rtype: list
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
            return self.python_extractor.extract_strings(
                force_text(src_data), translatable_file.path[2:]
            )

        # Template file
        return extract_transifex_template_strings(
            src_data, translatable_file.path[2:], encoding,
        )

    def _read_file(self, path, encoding):
        with io.open(path, 'r', encoding=encoding) as fp:
            return fp.read()

    def _find_files(self, root):
        """Get all files in the given root.

        :param basestring root: the root path to search in
        :return: a list of TranslatableFile objects
        :rtype: list
        """
        # TODO: See if we can remove functionality about locale dir and simplify

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

        follow_links = self.symlinks if self.subcommand == 'push' else False
        for dirpath, dirnames, filenames in os.walk(root, topdown=True,
                                                    followlinks=follow_links):
            for dirname in dirnames[:]:
                if (is_ignored(os.path.normpath(os.path.join(dirpath, dirname)),
                               norm_patterns) or
                        os.path.join(os.path.abspath(dirpath),
                                     dirname) in ignored_roots):
                    dirnames.remove(dirname)
                    self.verbose('Ignoring directory %s' % dirname)
                elif dirname == 'locale':
                    dirnames.remove(dirname)
                    if self.subcommand == 'push':
                        self.locale_paths.insert(0, os.path.join(
                            os.path.abspath(dirpath),
                            dirname
                        ))
            for filename in filenames:
                file_path = os.path.normpath(os.path.join(dirpath, filename))
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in self.extensions or is_ignored(file_path,
                                                                 self.ignore_patterns):
                    self.verbose('Ignoring file %s in %s' %
                                 (filename, dirpath))
                else:
                    if self.subcommand == 'push':
                        locale_dir = None
                        for path in self.locale_paths:
                            if os.path.abspath(dirpath).startswith(os.path.dirname(path)):
                                locale_dir = path
                                break
                        if not locale_dir:
                            locale_dir = self.default_locale_path
                        if not locale_dir:
                            locale_dir = NO_LOCALE_DIR
                        all_files.append(TranslatableFile(
                            dirpath, filename, locale_dir))
                    elif self.subcommand == 'migrate':
                        all_files.append(
                            TranslatableFile(dirpath.lstrip('./'), filename)
                        )
        return sorted(all_files)

    def _show_collect_results(self):
        """Display results of collecting source strings from files."""
        total_strings = sum([x[1] for x in self.stats['strings']])
        self.output(
            'Processed {} file(s) and found {} translatable strings '
            'in {} of them'.format(
                self.stats['processed_files'], total_strings, len(self.stats)
            )
        )

    def _show_push_results(self, status_code, response_content):
        """Display results of pushing the source strings to CDS.

        :param int status_code: the HTTP status code
        :param dict response_content: the content of the response
        """
        try:
            if 200 <= status_code < 300:
                # {"created":0,"updated":5,"skipped":1,"deleted":0,"failed":0,"errors":[]}
                created = response_content.get('created')
                updated = response_content.get('updated')
                skipped = response_content.get('skipped')
                deleted = response_content.get('deleted')
                failed = response_content.get('failed')
                errors = response_content.get('errors', [])
                self.output(
                    'Successfully pushed strings to Transifex.\n'
                    'Status: {code}\n'
                    'Created strings: {created}\n'
                    'Updated strings: {updated}\n'
                    'Skipped strings: {skipped}\n'
                    'Deleted strings: {deleted}\n'
                    'Failed strings: {failed}\n'
                    'Errors: {errors}\n'.format(
                        code=status_code,
                        created=created,
                        updated=updated,
                        skipped=skipped,
                        deleted=deleted,
                        failed=failed,
                        errors='\n'.join(errors)
                    )
                )

            else:
                message = response_content.get('message')
                details = response_content.get('details')
                self.output(
                    'Could not push strings to Transifex.\n'
                    'Status: {code}\n'
                    'Message: {message}\n'
                    'Details: {details}\n'.format(
                        code=status_code,
                        message=message,
                        details=json.dumps(details, indent=4),
                    )
                )
        except:
            self.output(
                '(Error while printing formatted report, '
                'falling back to raw format)\n'
                'Status: {code}\n'
                'Content: {content}'.format(
                    code=status_code,
                    content=response_content,
                )
            )

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

    @cached_property
    def settings_available(self):
        try:
            settings.LOCALE_PATHS
        except ImproperlyConfigured:
            if self.verbosity > 1:
                self.stderr.verbose("Running without configured settings.")
            return False
        return True

    def verbose(self, msg):
        if self.verbosity > 1:
            print(msg)

    def output(self, msg):
        print(msg)
