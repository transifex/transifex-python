from __future__ import absolute_import, unicode_literals

import fnmatch
import io
import os
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from transifex.common.console import Color
from transifex.native.django.management.common import (NO_LOCALE_DIR,
                                                       TranslatableFile)


class CommandMixin(object):
    """ Common utilities of all subcommands """

    def output(self, msg):
        Color.echo(msg)

    def verbose(self, msg):
        if self.verbose_output:
            Color.echo(msg)

    def _find_files(self, root, subcommand):
        """Get all files in the given root.

        :param basestring root: the root path to search in
        :return: a list of TranslatableFile objects
        :rtype: list
        """
        # TODO: See if we can remove functionality about locale dir and
        # simplify

        def is_ignored(path, ignore_patterns):
            """Check if the given path should be ignored or not."""
            filename = os.path.basename(path)

            def ignore(pattern):
                return (fnmatch.fnmatchcase(filename, pattern) or
                        fnmatch.fnmatchcase(path, pattern))

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

        follow_links = self.symlinks if subcommand == 'push' else False
        for dirpath, dirnames, filenames in os.walk(root, topdown=True,
                                                    followlinks=follow_links):
            for dirname in dirnames[:]:
                if (
                        is_ignored(os.path.normpath(os.path.join(dirpath,
                                                                 dirname)),
                                   norm_patterns) or
                        os.path.join(os.path.abspath(dirpath), dirname) in
                        ignored_roots):
                    dirnames.remove(dirname)
                    self.verbose('Ignoring directory %s' % dirname)
                elif dirname == 'locale':
                    dirnames.remove(dirname)
                    if subcommand == 'push':
                        self.locale_paths.insert(0, os.path.join(
                            os.path.abspath(dirpath),
                            dirname
                        ))
            for filename in filenames:
                file_path = os.path.normpath(os.path.join(dirpath, filename))
                file_ext = os.path.splitext(filename)[1]
                if (file_ext not in self.extensions or
                        is_ignored(file_path, self.ignore_patterns)):
                    self.verbose('Ignoring file %s in %s' %
                                 (filename, dirpath))
                else:
                    if subcommand == 'push':
                        locale_dir = None
                        for path in self.locale_paths:
                            if os.path.abspath(dirpath).\
                                    startswith(os.path.dirname(path)):
                                locale_dir = path
                                break
                        if not locale_dir:
                            locale_dir = self.default_locale_path
                        if not locale_dir:
                            locale_dir = NO_LOCALE_DIR
                        all_files.append(TranslatableFile(
                            dirpath, filename, locale_dir))
                    elif subcommand == 'migrate':
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
            if self.verbose_output:
                sys.stderr.verbose("Running without configured settings.\n")
            return False
        return True


def pretty_options(options_dict):
    items = [(k, v) for k, v in options_dict.items()]
    return '\n'.join([' - "{}": {}'.format(x[0], x[1]) for x in items])
