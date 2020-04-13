from __future__ import unicode_literals

import fnmatch
import io
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.core.management.utils import handle_extensions
from django.utils.functional import cached_property
from transifex.common.console import Color
from transifex.native.django.management.common import TranslatableFile
from transifex.native.django.tools.migrations.templatetags import \
    DjangoTagMigrationBuilder
from transifex.native.tools.migrations.models import Confidence
from transifex.native.tools.migrations.review import (
    REVIEW_ACCEPT_ALL, REVIEW_REJECT_ALL, FileReviewPolicy,
    LowConfidenceFileReviewPolicy, LowConfidenceStringReviewPolicy,
    NoopReviewPolicy, StringReviewPolicy, prompt_to_start)
from transifex.native.tools.migrations.save import (BackupSavePolicy,
                                                    InPlaceSavePolicy,
                                                    NewFileSavePolicy,
                                                    NoopSavePolicy)

SAVE_POLICY_OPTIONS = {
    'dry-run': 'no changes will be saved\n',
    'new': 'migrated content will be saved in a new file, '
           'named <filename>__native.<extension>\n',
    'backup': 'migrated content will be saved directly in the original '
              'file path, and a backup will also be saved '
              'in <filename>.<extension>.bak\n',
    'replace': 'migrated content will be saved in the original file',
}

REVIEW_POLICY_OPTIONS = {
    'none': 'everything will be done automatically without '
            'having a chance to review anything\n',
    'file': 'you get a chance to review each migrated file '
            'before it is saved\n',
    'string': 'you get a chance to review each string of each file '
              'before the file is saved\n',
    'file-low': 'you get a chance to review each migrated file '
                'that includes at least one string that has '
                'a low migration confidence\n',
    'string-low': 'you get a chance to review each string '
                  'that has a low migration confidence\n',
}


def pretty_options(options_dict):
    items = [(k, v) for k, v in options_dict.items()]
    return '\n'.join([' - "{}": {}'.format(x[0], x[1]) for x in items])


class Command(BaseCommand):
    """Migrates files using the Django i18n syntax to Transifex Native syntax."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain', '-d', default='django', dest='domain',
            help='The domain of the message files (default: "django").',
        )
        parser.add_argument(
            '--extension', '-e', dest='extensions', action='append',
            help='The file extension(s) to examine (default: "html,txt,py", or "js" '
                 'if the domain is "djangojs"). Separate multiple extensions with '
                 'commas, or use -e multiple times.',
        )
        parser.add_argument(
            '--file', '-f', dest='files', action='append',
            help='The relative paths of the files to migrate. Separate multiple paths '
                 'with commas, or use -f multiple times.',
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
        self.files = options['files']

        self.save_policy = self._create_save_policy(options['save_policy'])
        self.review_policy = self._create_review_policy(
            options['review_policy'])

        self.extensions = handle_extensions(['html', 'txt', 'py'])
        self.stats = {
            'processed_files': 0, 'migrations': [], 'saved': [], 'errors': [],
        }

        # Show an intro message
        self._show_intro(options)

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

        # Execute the migration
        self.django_migration_builder = DjangoTagMigrationBuilder()
        self.migrate_files(files)

    def _show_intro(self, options):
        """Show an introductory message to help the user understand what is going on.

        :param dict options: the configuration options of the command
        """
        Color.echo(
            '[high]'
            '\n####################################################################\n'
            'Running migration from Django i18n syntax to Transifex Native syntax\n'
            '[end]'
            'This migration is idempotent, so its output should not change if run\n'
            'multiple times.'
        )
        Color.echo('\n[high]Configuration:[end]')
        Color.echo('- [opt]Path:[end] [file]{}[end]'.format(self.path))
        Color.echo(
            '- [opt]Save policy:[end] [high]{}[end] -> {}'.format(
                options['save_policy'],
                SAVE_POLICY_OPTIONS[options['save_policy']],
            ).strip()
        )
        Color.echo(
            '- [opt]Review policy:[end] [high]{}[end] -> {}'.format(
                options['review_policy'],
                REVIEW_POLICY_OPTIONS[options['review_policy']],
            ).strip()
        )

    def migrate_files(self, files):
        """Search all related files, detect Django i18n translate hooks and migrate
        them to Transifex syntax.

        :param list files: a list of TranslatableFile objects
        """
        files_total = len(files)
        prompt_to_start(files_total)

        # Loop through each file, migrate, ask for user review if applicable,
        # save to disk if applicable
        accept_remaining_files = False
        for file_cnt, translatable_file in enumerate(files):
            _, extension = os.path.splitext(translatable_file.file)
            comment_format = '# {}\n' if extension == '.py' else '<!-- {} -->\n'
            self.review_policy.set_comment_format(comment_format)

            Color.echo(
                '\n---- [{cnt}/{total}] Migrating [file]{path}[end]...'.format(
                    path=translatable_file.path,
                    cnt=file_cnt + 1,
                    total=files_total,
                )
            )
            file_migration = self._migrate_file(translatable_file)
            if not file_migration:
                self.stats['processed_files'] += 1
                continue

            modified_strings = file_migration.modified_strings
            total_modified = len(modified_strings)
            total_low_confidence = len(
                [x for x in modified_strings if x.confidence == Confidence.LOW]
            )
            Color.echo(
                '[prompt]{strings} strings were modified '
                ' ([warn]{low}[end] with LOW confidence)[end]'.format(
                    strings=total_modified,
                    low=total_low_confidence,
                )
            )
            if not total_modified:
                continue

            # If the review policy says so, prompt the user for each string
            # If this returns True, it doesn't necessarily mean that the user
            # will be prompted, as the actual review policy may use
            # additional filters, e.g. only prompt for strings with low
            # confidence
            if self.review_policy.should_review_strings():
                reject_remaining = False
                for string_index in range(total_modified):
                    string_migration = modified_strings[string_index]

                    # The rest of the string test_migrations should be reverted
                    # based on the user's choice
                    if reject_remaining:
                        string_migration.revert()

                    # Optionally prompt the user to review the migration
                    else:
                        # Give the user the option to review
                        # May modify `string_migration` in place
                        result = self.review_policy.review_string(
                            string_migration, string_index, total_modified
                        )
                        # The user has chosen to accept the changes
                        # in all remaining strings. Break so that
                        # there will be no more prompts for the rest
                        # of the strings
                        if result == REVIEW_ACCEPT_ALL:
                            break

                        # The user has chosen to reject the changes in all
                        # remaining strings. Set the flag to True, so that
                        # it will revert all changes for the rest strings
                        # in the loop
                        if result == REVIEW_REJECT_ALL:
                            reject_remaining = True

            # If the review policy says so, prompt the user for each file
            if accept_remaining_files is False:
                result = self.review_policy.review_file(file_migration)

                # The user has chosen to reject all remaining files
                # Break, so that we exit the outer (file) loop
                if result == REVIEW_REJECT_ALL:
                    break

                # The user has chosen to accept all remaining files
                # Set the flag, so that the file review policy won't be used
                # for the remaining file test_migrations
                if result == REVIEW_ACCEPT_ALL:
                    accept_remaining_files = True

            # If the save policy says so, save the changes
            if file_migration.modified_strings:
                saved, error_type = self.save_policy.save_file(file_migration)
            else:
                saved, error_type = False, None

            # Update stats
            self.stats['processed_files'] += 1
            self.stats['migrations'].append(
                (translatable_file.path, file_migration)
            )
            if saved:
                self.stats['saved'].append(file_migration)
            elif error_type is not None:
                self.stats['errors'].append(file_migration)

        self._show_results(files)

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

    def _show_results(self, files):
        """Show a detailed report of how the migration went.

        :param list files: a list of TranslatableFile objects
        """
        Color.echo('\n\n[high]Migration completed![end]')
        Color.echo('--------------------')
        Color.echo('[high]Total files found:[end] [warn]{}[end]'.format(
            len(files))
        )
        Color.echo('[high]Total files processed:[end] [warn]{}[end]'.format(
            self.stats['processed_files'])
        )
        modified = [
            file_migration for _, file_migration in self.stats['migrations']
            if len(file_migration.modified_strings)
        ]
        Color.echo('[high]Total migrations created:[end] [warn]{}[end]'.format(
            len(modified)
        ))
        Color.echo('[high]Total files saved:[end] [warn]{}[end]'.format(
            len(self.stats['saved'])
        ))
        Color.echo(
            '\n'.join([
                '- [file]{}[end]'.format(x.filename)
                for x in self.stats['saved']
            ])
        )
        Color.echo('[high]Total errors:[end] [warn]{}[end]'.format(
            len(self.stats['errors'])
        ))
        Color.echo(
            '\n'.join([
                '- [warn]{}[end]'.format(x.filename)
                for x in self.stats['errors']
            ])
        )
        Color.echo('')

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

    def _create_save_policy(self, policy_id):
        """Create the save policy object that corresponds to the given ID.

        :param str policy_id: the ID of the policy to create, as expected
            in the command parameters
        :return: a SavePolicy subclass
        :rtype: SavePolicy
        """
        policy_id = policy_id.lower()
        if policy_id == 'dry-run':
            return NoopSavePolicy()
        elif policy_id == 'new':
            return NewFileSavePolicy()
        elif policy_id == 'backup':
            return BackupSavePolicy()
        elif policy_id == 'replace':
            return InPlaceSavePolicy()

        raise AttributeError('Invalid save policy ID={}'.format(policy_id))

    def _create_review_policy(self, policy_id):
        """Create the review policy object that corresponds to the given ID.

        :param str policy_id: the ID of the policy to create, as expected
            in the command parameters
        :return: a ReviewPolicy subclass
        :rtype: ReviewPolicy
        """
        if policy_id == 'none':
            return NoopReviewPolicy()
        elif policy_id == 'file':
            return FileReviewPolicy()
        elif policy_id == 'string':
            return StringReviewPolicy()
        elif policy_id == 'file-low':
            return LowConfidenceFileReviewPolicy()
        elif policy_id == 'string-low':
            return LowConfidenceStringReviewPolicy()

        raise AttributeError('Invalid review policy ID={}'.format(policy_id))
