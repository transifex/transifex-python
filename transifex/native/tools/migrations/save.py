# -*- coding: utf-8 -*-

from __future__ import unicode_literals

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
        >>> _safe_save('file/path.html', lambda: content, file_type='Backup')
        >>> _safe_save('file/path.html', my_provider.get_content, file_type='Backup')

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
            with open(path, "w") as f:
                f.write(content_func())
                Color.echo(
                    '✅️ {} saved at [file]{}[end]'.format(file_type, path)
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

    def save_file(self, file_migration):
        Color.echo(
            'Dry-run: no file was saved (file={})'.format(
                file_migration.filename
            )
        )
        return False, None


class NewFileSavePolicy(SavePolicy):
    """Saves the contents to a new file."""

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


class InPlaceSavePolicy(SavePolicy):
    """Saves the contents to the original file, without taking any backup."""

    def save_file(self, file_migration):
        """Save the new content in the original path.

        :param FileMigration file_migration: the migration of a whole file
        """
        return self._safe_save(
            file_migration.filename,
            file_migration.compile,
            file_type='Original',
        )
