# -*- coding: utf-8 -*-
"""This module contains everything related to the reviewing functionality
of a migration from another i18n framework to Transifex Native.

Reviewing is the process during which users can see the migration changes
and decide what is accepted and what is rejected.
"""

from __future__ import unicode_literals

import sys

from transifex.common.console import Color, prompt
# The reviewer has decided to reject the changes on a specific string
from transifex.native.tools.migrations.mark import (MARK_PROOFREAD_FILE,
                                                    MARK_PROOFREAD_STRING,
                                                    mark_string)
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

# The reviewer has decided to exit the migration, skipping remaining changes
REVIEW_EXIT = 7

# When the user is prompted to review a change (file or string)
# these are the valid responses
ACCEPT_CHOICE = 'A'  # accept the change
ACCEPT_ALL_CHOICE = 'AA'  # accept all changes
REJECT_CHOICE = 'R'  # reject the change
REJECT_ALL_CHOICE = 'RR'  # reject all changes
EXIT_CHOICE = 'X'  # exit the migration completely
MARK_CHOICE = 'M'  # mark for later review (inside the file, if saved)
PRINT_CHAR = 'P'  # print the diff


class ReviewPolicy(object):
    """Determines if and how each migration (string or file) will be reviewed
    by the user, before being accepted for save.

    It is meant to be subclassed, in order to provide custom functionality.
    """
    name = None

    def __init__(self):
        # This determines how review comments will appear
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

        :param StringMigration string_migration: the migration of a single
            string
        :param int string_cnt: the current index of the migrated string
            (0-based)
        :param int strings_total: the total number of strings in the
            corresponding file migration
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
        :param int string_cnt: the current index of the migrated string
            (0-based)
        :param int strings_total: the total number of strings in the
            corresponding file migration
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
                    '[opt](M)[end] Accept & Mark for proofreading '
                    '\n[opt](AA)[end] Accept remaining strings in file '
                    '[opt](RR)[end] Reject remaining strings in file '
                    '\n[opt](X)[end] Exit the migration'
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

            elif reply == EXIT_CHOICE:
                string_migration.revert()
                Color.echo('❌ ❌ All remaining changes rejected')
                Color.echo('❕Exiting the migration')
                return REVIEW_EXIT

            elif reply == MARK_CHOICE:
                mark_string(
                    string_migration,
                    self._comment_format,
                    MARK_PROOFREAD_STRING,
                )
                Color.echo('📝 Change marked for proofreading')
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
                    '[opt](M)[end] Accept & Mark for proofreading '
                    '[opt](P)[end] Print file diff '
                    '\n[opt](AA)[end] Accept remaining files '
                    '[opt](X)[end] Exit the migration'
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
                mark_string(
                    file_migration.strings[0],
                    self._comment_format,
                    MARK_PROOFREAD_FILE,
                )
                Color.echo(
                    '📝 Changes in file accepted & file marked for proofreading'
                )
                return REVIEW_MARK_STRING

            elif reply == PRINT_CHAR:
                Color.echo(
                    '[prompt]These are the modified strings[end]'
                    ' (the rest of the file is omitted)'
                )
                for string_migration in modified_strings:
                    if string_migration.confidence == Confidence.LOW:
                        Color.echo('[warn]--- [Low confidence!][end]')
                    Color.echo('[red]{}[end]'.format(
                        string_migration.original))
                    Color.echo('[green]{}[end]\n'.format(string_migration.new))

            elif reply == EXIT_CHOICE:
                file_migration.revert()
                Color.echo('❌ Changes in file rejected')
                Color.echo('❕Exiting the migration')
                return REVIEW_EXIT

    def _yes_no(self, description, yes_message=None, no_message=None):
        """Prompts the user to reply to a Yes/No question.

        :param basestring description: the message to display before prompting
        :param basestring yes_message: the message to display if user accepts
        :param basestring no_message: the message to display is user declines
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

    name = 'none'


class FileReviewPolicy(ReviewPolicy):
    """Prompts the user to review each file."""

    name = 'file'

    def review_file(self, file_migration):
        return self.prompt_for_file(file_migration)


class LowConfidenceFileReviewPolicy(ReviewPolicy):
    """Prompts the user to review each file that includes at least one string
    with low confidence."""

    name = 'file-low'

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

    name = 'string'

    def should_review_strings(self):
        return True

    def review_string(self, string_migration, string_cnt, strings_total):
        return self.prompt_for_string(string_migration, string_cnt, strings_total)


class LowConfidenceStringReviewPolicy(ReviewPolicy):
    """Prompts the user to review each string that has low confidence."""

    name = 'string-low'

    def should_review_strings(self):
        return True

    def review_string(self, string_migration, string_cnt, strings_total):
        if string_migration.confidence == Confidence.LOW:
            return self.prompt_for_string(string_migration, string_cnt, strings_total)


def create_review_policy(policy_id):
    """Create the review policy object that corresponds to the given ID.

    :param str policy_id: the ID of the policy to create, as expected
        in the command parameters
    :return: a ReviewPolicy subclass
    :rtype: ReviewPolicy
    """
    policy_classes = {
        x.name: x
        for x in [
            NoopReviewPolicy, FileReviewPolicy, StringReviewPolicy,
            LowConfidenceFileReviewPolicy, LowConfidenceStringReviewPolicy,
        ]
    }
    try:
        _class = policy_classes[policy_id.lower()]
        return _class()
    except KeyError:
        raise AttributeError('Invalid review policy ID={}'.format(policy_id))
