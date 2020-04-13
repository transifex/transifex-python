# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from transifex.native.tools.migrations.models import (Confidence,
                                                      FileMigration,
                                                      StringMigration)


class TestConfidence(object):
    """Test the Confidence class."""

    def test_to_string(self):
        assert Confidence.to_string(Confidence.HIGH) == 'HIGH'
        assert Confidence.to_string(Confidence.LOW) == 'LOW'


class TestStringMigration(object):
    """Test the StringMigration class."""

    def test_constructor_creates_modified_string(self):
        migration = StringMigration('original', 'new')
        assert migration.modified is True
        assert migration.original == 'original'
        assert migration.new == 'new'
        assert migration.confidence == Confidence.HIGH

    def test_constructor_creates_modified_false_string(self):
        migration = StringMigration('identical_strings', 'identical_strings')
        assert migration.modified is False
        assert migration.original == 'identical_strings'
        assert migration.new == 'identical_strings'
        assert migration.confidence == Confidence.HIGH

    def test_update_append(self):
        migration = StringMigration('first', 'FIRST', Confidence.HIGH)
        migration.update('\nsecond', '\nSECOND')
        assert migration.confidence == Confidence.HIGH

        migration.update('\nthird', '\nTHIRD', Confidence.LOW)
        assert migration.confidence == Confidence.LOW
        assert migration.modified is True
        assert migration.original == 'first\nsecond\nthird'
        assert migration.new == 'FIRST\nSECOND\nTHIRD'

    def test_update_prepend(self):
        migration = StringMigration('first', 'FIRST', Confidence.HIGH)
        migration.update('\nsecond', '\nSECOND', append=False)
        migration.update('\nthird', '\nTHIRD', Confidence.LOW, append=False)
        assert migration.confidence == Confidence.LOW
        assert migration.modified is True
        assert migration.original == '\nthird\nsecondfirst'
        assert migration.new == '\nTHIRD\nSECONDFIRST'

    def test_revert(self):
        migration = StringMigration('original', 'new')
        migration.revert()
        assert migration.modified is False
        assert migration.original == 'original'
        assert migration.new == 'original'


class TestFileMigration(object):
    """Test the FileMigration class."""

    def test_constructor(self):
        migration = FileMigration('filename', 'doesnt-matter')
        assert migration.filename == 'filename'
        assert migration.original_content == 'doesnt-matter'
        assert migration.compile() == ''
        assert migration.modified_strings == []

    def test_add_strings_compiles_fine(self):
        migration = FileMigration('filename', 'doesnt-matter')

        m1 = StringMigration('first', 'πρώτο')
        m2 = StringMigration('\nsecond', '\nδεύτερο')
        m3 = StringMigration('\nêà', '\nεα')
        migration.add_string(m1)
        migration.add_string(m2)
        migration.add_string(m3)
        assert migration.modified_strings == [m1, m2, m3]
        assert migration.compile() == 'πρώτο\nδεύτερο\nεα'

    def test_revert_strings(self):
        migration = FileMigration('filename', 'doesnt-matter')

        m1 = StringMigration('first', 'πρώτο')
        m2 = StringMigration('second', 'δεύτερο')
        m3 = StringMigration('third', 'τρίτο')
        migration.add_string(m1)
        migration.add_string(m2)
        migration.add_string(m3)
        migration.revert()
        assert migration.compile() == 'firstsecondthird'
        assert migration.modified_strings == []
