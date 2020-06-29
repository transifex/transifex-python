import os
import sys

from transifex.common.console import Color, pluralized, prompt
from transifex.native.tools.migrations.mark import (
    MarkLowConfidenceFilesPolicy, MarkLowConfidenceStringsPolicy,
    NoopMarkPolicy, create_mark_policy)
from transifex.native.tools.migrations.models import Confidence
from transifex.native.tools.migrations.review import (
    REVIEW_ACCEPT_ALL, REVIEW_EXIT, REVIEW_REJECT_ALL, FileReviewPolicy,
    LowConfidenceFileReviewPolicy, LowConfidenceStringReviewPolicy,
    NoopReviewPolicy, StringReviewPolicy, create_review_policy)
from transifex.native.tools.migrations.save import (BackupSavePolicy,
                                                    NewFileSavePolicy,
                                                    NoopSavePolicy,
                                                    ReplaceSavePolicy,
                                                    create_save_policy)

SAVE_POLICY_OPTIONS = {
    NoopSavePolicy.name: 'no changes will be saved\n',
    NewFileSavePolicy.name: 'migrated content will be saved in a new file, '
                            'named <filename>__native.<extension>\n',
    BackupSavePolicy.name: 'migrated content will be saved directly in the '
                           'original file path, and a backup will also be '
                           'saved in <filename>.<extension>.bak\n',
    ReplaceSavePolicy.name: 'migrated content will be saved in the original '
                            'file',
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

MARK_POLICY_OPTIONS = {
    NoopMarkPolicy.name: 'nothing will automatically be marked for '
                         'proofreading\n',
    MarkLowConfidenceFilesPolicy.name: 'any migrated file that includes '
                                       'at least one string that has low '
                                       'migration confidence will be marked '
                                       'for proofreading\n',
    MarkLowConfidenceStringsPolicy.name: 'any migrated string that has low '
                                         'confidence will be marked for '
                                         'proofreading\n',
}


class MigrationExecutor(object):
    """Responsible for orchestrating a migration of multiple files
    to Transifex Native syntax.

    It guides the user throughout the process, providing important
    feedback in the console. It supports various "review", "save" and "mark"
    policies, that determine what the user is asked to accept or reject
    before being saved, and the file location the changes are saved in.

    It is agnostic to any specific Python framework. The part that
    does the actual transformation from a specific framework (e.g. Django)
    to Transifex Native is handled by the `file_migrator_func` callable
    that is provided externally through dependency injection.
    """

    def __init__(self, options, file_migrator_func):
        """Constructor.

        :param dict options: the following configuration options of
            the migration:
             - 'files': a list of files to migrate, relative to
                current location
             - 'review_policy' (see REVIEW_POLICY_OPTIONS)
             - 'save_policy' (SAVE_POLICY_OPTIONS)
        :param callable file_migrator_func: a callable that is responsible for
            getting an object (e.g. a TranslatableFile) and returning
            a FileMigration object
        """
        self.options = options
        self.file_migrator_func = file_migrator_func
        self.save_policy = create_save_policy(options['save_policy'])
        self.review_policy = create_review_policy(options['review_policy'])
        self.mark_policy = create_mark_policy(options['mark_policy'])
        self.stats = {
            'processed_files': 0,
            'migrations': [],
            'saved': [],
            'files_marked': 0,
            'strings_marked': 0,
            'errors': [],
        }

    def _comment_format(self, path):
        """Return the comment format suitable for the given file,
        based on its extension.

        :param unicode path: the path to a migration file
        :return: a new string, to use with .format()
        :rtype: unicode
        """
        _, extension = os.path.splitext(path)
        return '# {}\n' if extension == '.py' else '<!-- {} -->'

    def migrate_files(self, files):
        """Search all related files, detect Django i18n translate hooks and
        migrate them to Transifex syntax.

        :param list files: a list of TranslatableFile objects
        """
        files_total = len(files)

        # Ask the user for permission to continue
        self._prompt_to_start(len(files))

        accept_remaining_files = False
        exit_migration = False

        # Loop through each file, migrate, ask for user review if applicable,
        # save to disk if applicable
        for file_cnt, translatable_file in enumerate(files):
            if exit_migration:
                break

            comment_format = self._comment_format(translatable_file.file)
            self.review_policy.set_comment_format(comment_format)
            self.mark_policy.set_comment_format(comment_format)

            Color.echo(
                '\n---- '
                '[[high]{cnt}[end]/[high]{total}[end]] '
                'Migrating [file]{path}[end]...'.format(
                    path=translatable_file.path,
                    cnt=file_cnt + 1,
                    total=files_total,
                )
            )
            self.stats['processed_files'] += 1
            file_migration = self.file_migrator_func(translatable_file)
            if not file_migration:
                continue

            modified_strings = file_migration.modified_strings
            total_modified = len(modified_strings)
            total_low_confidence = len(
                [x for x in modified_strings if x.confidence == Confidence.LOW]
            )
            msg = pluralized(
                '[warn]1[end] [prompt]string was modified[end]',
                '[warn]{cnt}[end] [prompt]strings were modified[end]',
                total_modified,
            )
            Color.echo(
                '{msg}{confidence}'.format(
                    msg=msg,
                    confidence=(
                        ' ([warn]{low}[end] with low confidence)'.format(
                            low=total_low_confidence,
                        )
                        if total_low_confidence else ''
                    )
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
                reject_remaining_strings = False
                for string_index in range(total_modified):
                    string_migration = modified_strings[string_index]

                    # The rest of the string test_migrations should be reverted
                    # based on the user's choice
                    if reject_remaining_strings:
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
                        elif result == REVIEW_REJECT_ALL:
                            reject_remaining_strings = True

                        # The user has chosen to exit the migration completely
                        # Break to exit the outer (file) loop
                        elif result == REVIEW_EXIT:
                            exit_migration = True
                            break

            # If the mark policy says so, give it a chance to mark
            # each string for proofread
            if self.mark_policy.should_mark_strings():
                for string_migration in modified_strings:
                    marked = self.mark_policy.mark_string(string_migration)
                    if marked:
                        self.stats['strings_marked'] += 1

            # If the review policy says so, prompt the user for each file
            if accept_remaining_files is False and exit_migration is False:
                result = self.review_policy.review_file(file_migration)

                # The user has chosen to reject all remaining files
                # Break, so that we exit the outer (file) loop
                if result == REVIEW_REJECT_ALL:
                    break

                # The user has chosen to accept all remaining files
                # Set the flag, so that the file review policy won't be used
                # for the remaining file test_migrations
                elif result == REVIEW_ACCEPT_ALL:
                    accept_remaining_files = True

                # The user has chosen to exit the migration completely
                elif result == REVIEW_EXIT:
                    exit_migration = True

            # Skip to the results
            # Break to exit the outer (file) loop
            if exit_migration is True:
                break

            # Give a chance to the mark policy to mark the file for proofread
            marked = self.mark_policy.mark_file(file_migration)
            if marked:
                self.stats['files_marked'] += 1

            # If the save policy says so, save the changes
            if file_migration.modified_strings:
                saved, error_type = self.save_policy.save_file(file_migration)
            else:
                saved, error_type = False, None

            # Update stats
            self.stats['migrations'].append(
                (translatable_file.path, file_migration)
            )
            if saved:
                self.stats['saved'].append(file_migration)
            elif error_type is not None:
                self.stats['errors'].append(file_migration)

        self._show_results(files, self.stats)

    def show_intro(self):
        """Show an introductory message to help the user understand what
        is going on.
        """
        Color.echo(
            '[high]'
            '\n############################################################'
            '########\n'
            'Running migration from Django i18n syntax to Transifex Native '
            'syntax\n'
            '[end]'
            '\nThis migration is idempotent, so its output should not '
            'change if run'
            '\nmultiple times with the same configuration.'
        )
        Color.echo('\n[high]Configuration:[end]')
        if self.options['path']:
            Color.echo(
                '[opt]Path:[end] [file]{}[end]'.format(self.options['path'])
            )
        if self.options['files']:
            Color.echo('[opt]Files:[end]')
            Color.echo(
                '\n'.join([
                    ' - [file]{}[end]'.format(x)
                    for x in self.options['files']
                ])
            )
        Color.echo(
            '[opt]Review policy:[end] [high]{}[end] -> {}'.format(
                self.options['review_policy'],
                REVIEW_POLICY_OPTIONS[self.options['review_policy']],
            ).strip()
        )
        Color.echo(
            '[opt]Save policy:[end] [high]{}[end] -> {}'.format(
                self.options['save_policy'],
                SAVE_POLICY_OPTIONS[self.options['save_policy']],
            ).strip()
        )
        Color.echo(
            '[opt]Mark policy:[end] [high]{}[end] -> {}'.format(
                self.options['mark_policy'],
                MARK_POLICY_OPTIONS[self.options['mark_policy']],
            ).strip()
        )

    def _prompt_to_start(self, total_files):
        """Prompt the user before starting the migration.

        If the user chooses to not go through with it, sys.exit() is called.

        :param int total_files: the total number of files to migrate
        """
        msg = pluralized(
            'Found [warn]{cnt}[end] file to check for translatable strings.',
            'Found [warn]{cnt}[end] files to check for translatable strings.',
            total_files,
        )
        Color.echo('\n{}'.format(msg))

        if not total_files:
            Color.echo('\n[high]Migration ended.[end]')
            sys.exit(1)

        if (
            self.options['save_policy'] != NoopSavePolicy.name
            and self.options['review_policy'] == NoopReviewPolicy.name
        ):
            Color.echo(
                '\n[warn]WARNING! The selected configuration will save '
                'all files automatically, without allowing you to do any '
                'reviewing first.[end]'
            )

        while True:
            reply = prompt(
                Color.format(
                    '[opt](Y)[end] Yes [opt](N)[end] No'
                ),
                description='Are you sure you want to continue?',
                default='N',
            )
            reply = reply.upper()
            if reply == 'Y':
                return
            elif reply == 'N':
                Color.echo('\n[high]Migration aborted.[end]')
                sys.exit(1)

    def _show_results(self, files, stats):
        """Show a detailed report of how the migration went.

        :param list files: a list of TranslatableFile objects
        :param dict stats: a dictionary with all statistics of the execution
        """
        Color.echo('\n\n[high]Migration completed![end]')
        Color.echo('--------------------')
        Color.echo('[high]Files found:[end] [warn]{}[end]'.format(
            len(files))
        )
        Color.echo('[high]Files processed:[end] [warn]{}[end]'.format(
            stats['processed_files'])
        )

        files_modified = 0
        strings_modified = 0
        for _, file_migration in stats['migrations']:
            new_string_count = len(file_migration.modified_strings)
            strings_modified += new_string_count
            if new_string_count:
                files_modified += 1

        # Files & string migrations
        Color.echo(
            '[high]File migrations created:[end] [warn]{}[end]'.format(
                files_modified
            )
        )
        Color.echo(
            '[high]String migrations inside these files: [warn]{}[end]'.format(
                strings_modified
            )
        )

        # Files saved
        Color.echo('[high]Files saved:[end] [warn]{}[end]'.format(
            len(stats['saved'])
        ))
        saved_str = '\n'.join([
            ' - [file]{}[end]'.format(x.filename)
            for x in stats['saved']
        ])
        if saved_str:
            Color.echo(saved_str)

        # Files & strings marked
        Color.echo(
            '[high]Files marked for proofreading:[end] [warn]{}[end]'.format(
                stats['files_marked']
            )
        )
        Color.echo(
            '[high]Strings marked for proofreading:[end] [warn]{}[end]'.format(
                stats['strings_marked']
            )
        )

        # Errors found
        Color.echo('[high]Errors found:[end] [warn]{}[end]'.format(
            len(stats['errors'])
        ))
        errors_str = '\n'.join([
            ' - [warn]{}[end]'.format(x.filename)
            for x in stats['errors']
        ])
        if errors_str:
            Color.echo(errors_str)

        Color.echo('')


def migrate_text(text, migrator_func):
    """Convert the given text from the original framework to Native syntax.

    Supports both HTML/template syntax and Python/gettext syntax.
    Prints out the result in the console.

    :param unicode text: the text to migrate to Native syntax
    :param callable migrator_func: a Callable[unicode] -> FileMigration object
        that converts syntax to Transifex Native; provided externally
        so that it can support any Python framework (e.g. Django)
    """
    Color.echo(
        '[high]Original syntax:[end]\n[red]{}[end]'.format(text)
    )
    file_migration = migrator_func(text)
    Color.echo(
        '\n[high]Transifex Native syntax:[end]\n[green]{}[end]'.format(
            file_migration.compile()
        )
    )
