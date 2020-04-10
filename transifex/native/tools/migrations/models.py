from __future__ import unicode_literals


class Confidence(object):

    LOW = 1
    HIGH = 2

    @classmethod
    def to_string(cls, confidence):
        """Return a string representation of a confidence int type.

        :param int confidence: the int ID
        :rtype: str
        """
        return 'LOW' if confidence == Confidence.LOW else 'HIGH'


class StringMigration(object):
    """Migration info for a framework's i18n syntax to Transifex Native syntax,
    for a single unit (e.g. a Django template tag or a Python function call).

    Describes the changes that need to be made in order to change
    a template file that uses the framework's i18n syntax to a file that uses
    the Transifex Native syntax.
    """

    def __init__(self, original, new, confidence=Confidence.HIGH):
        """Constructor.

        :param unicode original:
        :param unicode new:
        :param int confidence:
        """
        self.original = ''
        self.new = ''
        self.confidence = confidence
        self.modified = False
        self.update(original, new)

    def update(self, extra_original, extra_new, confidence=None, append=True):
        """Append a extra_new substring.

        :param unicode extra_original:
        :param unicode extra_new:
        :param int confidence:
        :param bool append: if True, the changes will be appended to the end
            of the strings, otherwise they will be prepended in the beginning
        """
        if append:
            self.original = self.original + extra_original
            self.new = self.new + extra_new
        else:
            self.original = extra_original + self.original
            self.new = extra_new + self.new

        self.confidence = confidence or self.confidence or Confidence.HIGH
        self.modified = self.new != self.original

    def revert(self):
        """Revert the migration, making the new string identical to the
        original one."""
        self.new = self.original
        self.confidence = Confidence.HIGH
        self.modified = False

    def __repr__(self):
        return (
            '<StringMigration original="{original}" new="{new}" '
            'modified={modified} confidence={confidence}>'
        ).format(
            original=self.original[:20].replace('\n', '\\n') + '...',
            new=self.new[:20].replace('\n', '\\n') + '...',
            modified=self.modified,
            confidence=Confidence.to_string(self.confidence),
        )


class FileMigration(object):
    """Migration info for a framework's i18n syntax to Transifex Native syntax,
    for a whole file.

    Describes the changes that need to be made in order to change
    a template file that uses the framework's i18n syntax to a file that uses
    the Transifex Native syntax.
    """

    def __init__(self, filename, original_content):
        """Constructor.

        :param unicode filename: the path of the original file
        :param unicode original_content: the actual content of the original file
        """
        self.filename = filename
        self.original_content = original_content
        self.strings = []

    def add_string(self, string_migration):
        """Add a string migration.

        Each string migration represents a distinctive item that was found
        in the file. It may have changes or it may not.

        :param StringMigration string_migration: the migration object to add
        """
        self.strings.append(string_migration)

    def compile(self):
        """Render all changes in a string, resulting to the final migrated file.

        :return: a string that includes the final state of the migrated file
        :rtype: unicode
        """
        return ''.join(
            [(x.new if x.new is not None else '') for x in self.strings]
        )

    def revert(self):
        """Revert all string test_migrations in the file."""
        for string_migration in self.strings:
            string_migration.revert()

    @property
    def modified_strings(self):
        """A list of all StringMigration objects with content that was really migrated,
        for a particular file.

        :rtype: List[StringMigration]
        """
        return [string for string in self.strings if string.modified]
