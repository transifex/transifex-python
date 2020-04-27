# -*- coding: utf-8 -*-
"""This module contains everything related to the functionality
that marks a migration to Transifex Native code for proofreading.

When a file or a string in a file is marked for proofreading, a special
string is added in the file, so that users can grep for it and
make sure the migration is correct.
"""

from __future__ import unicode_literals

from transifex.common.console import Color
from transifex.native.tools.migrations.models import Confidence

MARK_PROOFREAD_STRING = 'Transifex Native: PROOFREAD_STRING'
MARK_PROOFREAD_FILE = 'Transifex Native: PROOFREAD_FILE'
MARK_ARGUMENT_FIXME = '__txnative_fixme'


def mark_string(string_migration, comment_format, mark):
    """Mark a string migration for proofreading.

    Adds a comment in the beginning of this string.

    :param StringMigration string_migration: the string migration object
        to update
    :param unicode comment_format: the format of the comment,
        compatible with the file type of the migration
    :param str mark: the string to add as a comment
    """
    string_migration.update(
        '', comment_format.format(mark),
        append=False,
    )


class MarkPolicy(object):
    """Determines if a migrated file or a migrated string will be marked
    for proofread.
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
        """Define the comment format to use when a policy adds
        comments to the migrated file.

        Example:
        >>> set_comment_format('# {}')

        :param unicode comment_format: the format to use; must include '{}'
        :raise ValueError: if `comment_format` does not include '{}'
        """
        if '{}' not in comment_format:
            raise ValueError('The provided `comment_format` must include {}')
        self._comment_format = comment_format

    def should_mark_strings(self):
        """Returns whether or not a policy object wants to mark individual
        strings.

        Although policy subclasses can only mark *some* strings, and not all,
        this method is important for optimization, so that the objects that
        use a policy object know if they need to feed each string migration
        to the mark policy or not.
        """
        return False

    def mark_file(self, file_migration):
        """The base class does nothing.

        :param FileMigration file_migration: the migration object
        :return: True if the file was marked, False otherwise
        :rtype: bool
        """
        return False

    def mark_string(self, string_migration):
        """The base class does nothing.

        :param StringMigration string_migration: the migration object
        :return: True if the string was marked, False otherwise
        :rtype: bool
        """
        return False


class NoopMarkPolicy(MarkPolicy):
    """Does not mark anything."""

    name = 'none'


class MarkLowConfidenceFilesPolicy(MarkPolicy):
    """Marks all files that have at least one string with low confidence."""

    name = 'file-low'

    def mark_file(self, file_migration):
        if not file_migration.low_confidence_strings:
            return False

        first_string_migration = file_migration.strings[0]
        if MARK_PROOFREAD_FILE in first_string_migration.new:
            return False

        mark_string(
            first_string_migration,
            self._comment_format,
            MARK_PROOFREAD_FILE,
        )
        Color.echo('📝 File automatically marked for proofreading')
        return True


class MarkLowConfidenceStringsPolicy(MarkPolicy):
    """Marks all string that have low confidence."""

    name = 'string-low'

    def should_mark_strings(self):
        return True

    def mark_string(self, string_migration):
        if string_migration.confidence != Confidence.LOW:
            return False

        if MARK_PROOFREAD_STRING in string_migration.new:
            return False

        mark_string(
            string_migration,
            self._comment_format,
            MARK_PROOFREAD_STRING,
        )
        return True


def create_mark_policy(policy_id):
    """Create the mark policy object that corresponds to the given ID.

    :param str policy_id: the ID of the policy to create, as defined
        in the MarkPolicy subclasses
    :return: an instance of a subclass of MarkPolicy
    :rtype: MarkPolicy
    """
    policy_classes = {
        x.name: x
        for x in [
            NoopMarkPolicy, MarkLowConfidenceFilesPolicy,
            MarkLowConfidenceStringsPolicy,
        ]
    }
    try:
        _class = policy_classes[policy_id.lower()]
        return _class()
    except KeyError:
        raise AttributeError('Invalid mark policy ID={}'.format(policy_id))
