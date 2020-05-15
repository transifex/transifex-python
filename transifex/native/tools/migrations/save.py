# -*- coding: utf-8 -*-
"""This module contains everything related to the saving functionality
of a migration from another i18n framework to Transifex Native.

The classes defined here are responsible for saving the migrated content
to the proper target, saving a backup and so on.
"""
from __future__ import unicode_literals

import io
import os

from transifex.common.console import Color


class SavePolicy(object):
    """Determines if and how each file migration will be saved
    to the disk.

    It is meant to be subclassed, so that each policy provides custom
    functionality. This class also provides some convenience functionality
    that might be used by subclasses.
    """

    # Do not save the new content at all
    DRY_RUN = 0

    # Save the new content in a new file
    NEW_FILE = 1

    # Save the new content in the original file but take a backup
    # in another file first
    BACKUP = 2

    # Replace the original file with no backup
    IN_PLACE = 3

    name = None

    def save_file(self, file_migration):
        """Called when a file migration is ready to be saved.

        Needs to be overridden in subclasses.

        :param FileMigration file_migration: the migration of a whole file
        :return: a tuple that shows if the file was saved and the type of
            exception raised if applicable
        :rtype: Tuple[bool, type]
        """
        raise NotImplementedError()

    def _safe_save(self, path, content_func, file_type):
        """Attempt to save the string provided by the given callable to the
        given file path, gracefully handling any exception.

        Requires a callable so that it also catches any exceptions raised
        during the generation of the content.

        Usage:
        >>> _safe_save('file/path.html', lambda: content, file_type='Backup')  # noqa
        >>> _safe_save('file/path.html', my_provider.get_content, file_type='Backup')  # noqa

        :param basestring path: the path to save to
        :param callable content_func: a callable that should return the content
            to save in the file
        :param basestring file_type: the type of the file that was saved,
            used to display a more clear message to the user
            e.g. 'backup' or 'original'
        :return: a tuple that shows if the file was saved and the type of
            exception raised if applicable
        :rtype: Tuple[bool, type]
        """
        try:
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(content_func())
                Color.echo(
                    '💾️ {} file saved at [file]{}[end]'.format(file_type, path)
                )
                return True, None
        except IOError as e:
            Color.echo(
                '❌ [red]IOError while saving to {} file[end] '
                '[file]{}[end]: {}'.format(
                    file_type.lower(), path, e
                )
            )
            return False, type(e)
        except Exception as e:
            Color.echo(
                '❌ [red]Error while saving to {} file[end]'
                ' [file]{}[end]: {}'.format(
                    file_type.lower(), path, e
                )
            )
            return False, type(e)


class NoopSavePolicy(SavePolicy):
    """Doesn't save anything to a file, i.e. a dry-run."""

    name = 'none'

    def save_file(self, file_migration):
        Color.echo('Dry-run: no file was saved')
        return False, None


class NewFileSavePolicy(SavePolicy):
    """Saves the contents to a new file."""

    name = 'new'

    def save_file(self, file_migration):
        """Save the new content in a new file.

        :param FileMigration file_migration: the migration of a whole file
        """
        filename, extension = os.path.splitext(file_migration.filename)
        new_filename = '{}__native{}'.format(filename, extension)
        return self._safe_save(
            new_filename, file_migration.compile, file_type='New',
        )


class BackupSavePolicy(SavePolicy):
    """Saves the contents to the original file, but takes a backup first."""

    name = 'backup'

    def save_file(self, file_migration):
        """Save the new content in the original path, but take a backup first.

        :param FileMigration file_migration: the migration of a whole file
        """
        # Save the original content in a backup file
        backup_filename = file_migration.filename + '.bak'
        success = self._safe_save(
            backup_filename,
            lambda: file_migration.original_content,
            file_type='Backup',
        )

        # If the backup failed, do not modify the original file
        if not success:
            Color.echo(
                '[warn]  -> will not modify the original file '
                '[file]{}[end]'.format(file_migration.filename)
            )
            return False

        # Save the new content in the original file
        return self._safe_save(
            file_migration.filename,
            file_migration.compile,
            file_type='Original'
        )


class ReplaceSavePolicy(SavePolicy):
    """Saves the contents to the original file, without taking any backup."""

    name = 'replace'

    def save_file(self, file_migration):
        """Save the new content in the original path.

        :param FileMigration file_migration: the migration of a whole file
        """
        return self._safe_save(
            file_migration.filename,
            file_migration.compile,
            file_type='Original',
        )


def create_save_policy(policy_id):
    """Create the save policy object that corresponds to the given ID.

    :param str policy_id: the ID of the policy to create, as expected
        in the command parameters
    :return: a SavePolicy subclass
    :rtype: SavePolicy
    """
    policy_classes = {
        x.name: x
        for x in [
            NoopSavePolicy, NewFileSavePolicy, BackupSavePolicy,
            ReplaceSavePolicy,
        ]
    }
    try:
        _class = policy_classes[policy_id.lower()]
        return _class()
    except KeyError:
        raise AttributeError('Invalid save policy ID={}'.format(policy_id))
