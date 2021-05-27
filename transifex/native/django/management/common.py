import os
from functools import total_ordering

from transifex.common.utils import generate_key

NO_LOCALE_DIR = object()


@total_ordering
class TranslatableFile(object):
    """Holds information about a localizable file, i.e. a file
    that holds translatable strings."""

    def __init__(self, dirpath, file_name, locale_dir=None):
        self.file = file_name
        self.dirpath = dirpath
        self.locale_dir = locale_dir

    def __repr__(self):
        return "<%s: %s>" % (
            self.__class__.__name__,
            os.sep.join([self.dirpath, self.file]),
        )

    def __eq__(self, other):
        return self.path == other.path

    def __lt__(self, other):
        return self.path < other.path

    @property
    def path(self):
        return os.path.join(self.dirpath, self.file)


class SourceStringCollection(object):
    """Holds SourceString objects in memory."""

    def __init__(self):
        self.strings = {}

    def add(self, source_string):
        """Add a source string to the collection.

        :param SourceString source_string: the object to add
        """
        key = generate_key(
            string=source_string.string, context=source_string.context
        )
        if key not in self.strings:
            self.strings[key] = source_string
        else:
            self.strings[key].occurrences = source_string.occurrences

    def extend(self, source_strings):
        """Add multiple strings to the collection.

        :param list source_strings: a list of SourceString objects
        """
        if source_strings:
            for string in source_strings:
                self.add(string)

    def update(self, source_strings):
        """Reset the collection so that it only includes the given
         strings.

        :param list source_strings: a list of SourceString objects
        """
        self.strings = {}
        if source_strings is None:
            return

        self.extend(source_strings)
