# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sys

from transifex.common.console import Color, prompt
# The reviewer has decided to reject the changes on a specific string
from transifex.native.tools.migrations.models import Confidence

# The reviewer has decided to reject the changes on a specific string or file
REVIEW_REJECT = 1

# The reviewer has decided to reject the changes of all strings or all files
REVIEW_REJECT_ALL = 2

# The reviewer has decided to accept the change of one string or one file
REVIEW_ACCEPT = 3

# The reviewer has decided to accept the changes of all strings or all files
REVIEW_ACCEPT_ALL = 4

# The reviewer has decided to mark a specific string for later review
REVIEW_MARK_STRING = 5

# The reviewer has decided to mark a specific file for later review
REVIEW_MARK_FILE = 6

# When the user is prompted to review a change (file or string)
# these are the valid responses
ACCEPT_CHOICE = 'A'  # accept the change
ACCEPT_ALL_CHOICE = 'AA'  # accept all changes
REJECT_CHOICE = 'R'  # reject the change
REJECT_ALL_CHOICE = 'RR'  # reject all change
MARK_CHOICE = 'M'  # mark for later review (inside the file, if saved)
PRINT_CHAR = 'P'  # print the diff

MARK_REVIEW_STRING = 'Transifex Native: REVIEW_STRING'
MARK_REVIEW_FILE = 'Transifex Native: REVIEW_FILE'


def prompt_to_start(total_files):
    """Prompt the user before starting the migration.

    If the user chooses to not go through with it, sys.exit() is called.

    :param int total_files: the total number of files to migrate
    """
    Color.echo(
        '\nFound {} file(s) to check for translatable strings.'.format(
            total_files)
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


class ReviewPolicy(object):
    """Determines if and how each migration (string or file) will be reviewed
    by the user, before being accepted for save.

    It is meant to be subclassed, in order to provide custom functionality.
    """

    def __init__(self):
        # This determines review comments will appear
        # inside the migrated file. It is dynamic because different files
        # support different comment formats, e.g.
        # - '# Comment' in Python
        # - '<!-- Comment -->' in HTML
        self._comment_format = '{}'

    def set_comment_format(self, comment_format):
        """Define the comment format to use when a review policy adds
        comments to the reviewed file.

        Example:
        >>> set_comment_format('# {}')

        :param unicode comment_format: the format to use; must include '{}'
        :raise ValueError: if `comment_format` does not include '{}'
        """
        if '{}' not in comment_format:
            raise ValueError('The provided `comment_format` must include {}')
        self._comment_format = comment_format

    def should_review_strings(self):
        """Returns whether or not a policy object wants to review individual
        strings.

        Although policy subclasses can only review *some* strings, and not all,
        this method is important for optimization, so that the objects that
        use a policy object know if they need to feed each string migration
        to the review policy or not.
        """
        return False

    def review_string(self, string_migration, string_cnt, strings_total):
        """Optionally give the chance to the user to review a string migration
        before accepting it.

        By default this class automatically accepts the change
        (i.e. returns an "accept" directive), but subclasses can provide
        a custom implementation.

        :param StringMigration string_migration: the migration of a single string
        :param int string_cnt: the current index of the migrated string (0-based)
        :param int strings_total: the total number of strings in the corresponding
            file migration
        :return: an integer directive that determines what to do with the string
        :rtype: int
        """
        return REVIEW_ACCEPT

    def review_file(self, file_migration):
        """Optionally give the chance to the user to review a file migration
        before accepting it.

        :param FileMigration file_migration: the migration of a whole file
        :return: an integer directive that determines what to do with the string
        :rtype: int
        """
        return REVIEW_ACCEPT

    def prompt_for_string(self, string_migration, string_cnt, strings_total):
        """Prompt the user to review the string migration and decide what to do.

        :param StringMigration string_migration: the migration object
        :param int string_cnt: the current index of the migrated string (0-based)
        :param int strings_total: the total number of strings in the corresponding
            file migration
        :return: an integer directive that determines what to do with the string
        :rtype: int
        """
        Color.echo(
            '\n[{cnt}/{total}] [prompt]'
            'Please review the following change:[end] '
            '(confidence={confidence})'.format(
                cnt=string_cnt + 1,
                total=strings_total,
                confidence=(
                    '{}' if string_migration.confidence == Confidence.HIGH
                    else '[warn]{}[end]'
                ).format(
                    Confidence.to_string(string_migration.confidence)
                ),
            )
        )
        Color.echo('[red]{}[end]'.format(string_migration.original))
        Color.echo('[green]{}[end]'.format(string_migration.new))
        while True:
            reply = prompt(
                Color.format(
                    '[opt](A)[end] Accept '
                    '[opt](R)[end] Reject '
                    '[opt](M)[end] Mark for later review '
                    '\n[opt](AA)[end] Accept all remaining '
                    '[opt](RR)[end] Reject all remaining '
                ),
                default=str(ACCEPT_CHOICE),
            )
            reply = reply.upper()
            if reply == ACCEPT_CHOICE:
                Color.echo('✅️ Change accepted')
                return REVIEW_ACCEPT

            elif reply == ACCEPT_ALL_CHOICE:
                Color.echo('✅ ✅️ All remaining changes accepted')
                return REVIEW_ACCEPT_ALL

            elif reply == REJECT_CHOICE:
                string_migration.revert()
                Color.echo('❌ Change rejected')
                return REVIEW_REJECT

            elif reply == REJECT_ALL_CHOICE:
                string_migration.revert()
                Color.echo('❌ ❌ All remaining changes rejected')
                return REVIEW_REJECT_ALL

            elif reply == MARK_CHOICE:
                string_migration.update(
                    '', self._comment_format.format(MARK_REVIEW_STRING),
                    append=False,
                )
                Color.echo('📝 Change marked for later review')
                return REVIEW_MARK_STRING

    def prompt_for_file(self, file_migration):
        """Prompt the user to review the file migration and decide what to do.

        :param FileMigration file_migration: the migration object
        :return: an integer directive that determines what to do with the file
        :rtype: int
        """
        modified_strings = file_migration.modified_strings
        while True:
            reply = prompt(
                Color.format(
                    '[opt](A)[end] Accept '
                    '[opt](R)[end] Reject '
                    '[opt](M)[end] Mark for later review '
                    '[opt](P)[end] Print file diff '
                    '\n[opt](RR)[end] Reject all remaining '
                    '[opt](AA)[end] Accept all remaining'
                ),
                default=str(ACCEPT_CHOICE),
            )
            reply = reply.upper()
            if reply == ACCEPT_CHOICE:
                Color.echo('✅️ Changes accepted')
                return REVIEW_ACCEPT

            elif reply == ACCEPT_ALL_CHOICE:
                Color.echo('\n[warn]WARNING![end]')
                reply = self._yes_no(
                    'If you continue, all changes in the remaining files '
                    'will be accepted. Are you sure you want to continue?',
                    no_message='Aborted.'
                )
                if reply is True:
                    Color.echo('✅ ✅ Changes in all remaining files accepted')
                    return REVIEW_ACCEPT_ALL

            elif reply == REJECT_CHOICE:
                file_migration.revert()
                Color.echo('❌ Changes in file rejected')
                return REVIEW_REJECT

            elif reply == REJECT_ALL_CHOICE:
                Color.echo('\n[warn]WARNING![end]')
                reply = self._yes_no(
                    'If you continue, all changes in the remaining files '
                    'will be rejected. Are you sure you want to continue?',
                    no_message='Aborted.'
                )
                if reply is True:
                    Color.echo('❌ ❌ Changes in all remaining files rejected')
                    return REVIEW_REJECT_ALL

            elif reply == MARK_CHOICE:
                file_migration.strings[0].update(
                    '', self._comment_format.format(MARK_REVIEW_FILE),
                    append=False,
                )
                Color.echo('📝 File marked for later review')
                return REVIEW_MARK_STRING

            elif reply == PRINT_CHAR:
                Color.echo(
                    '[prompt]These are the modified strings[end]'
                    ' (the rest of the file is omitted)'
                )
                for string_migration in modified_strings:
                    Color.echo('[red]{}[end]'.format(
                        string_migration.original))
                    Color.echo('[green]{}[end]'.format(string_migration.new))
                    print('')

    def _yes_no(self, description, yes_message=None, no_message=None):
        """Prompts the user to reply to a Yes/No question.

        :param basestr description: the message to display before prompting
        :param basestr yes_message: the message to display if user accepts
        :param basestr no_message: the message to display is user declines
        :return: True if the user chose to go through, false otherwise
        :rtype: bool
        """
        while True:
            reply = prompt(
                Color.format('[opt](Y)[end] Yes [opt](N)[end] No'),
                description=description,
                default='N',
            )
            reply = reply.upper()
            if reply == 'Y':
                if yes_message:
                    Color.echo('[high]{}[end]'.format(yes_message))
                return True
            elif reply == 'N':
                if no_message:
                    Color.echo('[high]{}[end]'.format(no_message))
                return False


class NoopReviewPolicy(ReviewPolicy):
    """Never prompts the user for anything."""
    pass


class FileReviewPolicy(ReviewPolicy):
    """Prompts the user to review each file."""

    def review_file(self, file_migration):
        return self.prompt_for_file(file_migration)


class LowConfidenceFileReviewPolicy(ReviewPolicy):
    """Prompts the user to review each file that includes at least one string
    with low confidence."""

    def review_file(self, file_migration):
        total_low_confidence = len(
            [
                string for string in file_migration.modified_strings
                if string.confidence == Confidence.LOW
            ]
        )
        if total_low_confidence > 0:
            return self.prompt_for_file(file_migration)

        return REVIEW_ACCEPT


class StringReviewPolicy(ReviewPolicy):
    """Prompts the user to review each string."""

    def should_review_strings(self):
        return True

    def review_string(self, string_migration, string_cnt, strings_total):
        return self.prompt_for_string(string_migration, string_cnt, strings_total)


class LowConfidenceStringReviewPolicy(ReviewPolicy):
    """Prompts the user to review each string that has low confidence."""

    def should_review_strings(self):
        return True

    def review_string(self, string_migration, string_cnt, strings_total):
        if string_migration.confidence == Confidence.LOW:
            return self.prompt_for_string(string_migration, string_cnt, strings_total)
