from __future__ import absolute_import, unicode_literals

import json
import os

from django.conf import settings
from django.core.management.utils import handle_extensions
from django.utils.encoding import force_text
from transifex.native import tx
from transifex.native.django.management.common import SourceStringCollection
from transifex.native.django.management.utils.base import CommandMixin
from transifex.native.django.utils.templates import \
    extract_transifex_template_strings
from transifex.native.parsing import Extractor


class Push(CommandMixin):
    def add_arguments(self, subparsers):
        parser = subparsers.add_parser(
            'push',
            help=("Detect translatable strings in Django templates and Python "
                  "files and push them as source strings to Transifex"),
        )
        parser.add_argument(
            '--extension', '-e', dest='extensions', action='append',
            help=('The file extension(s) to examine (default: "html,txt,py", '
                  'or "js" if the domain is "djangojs"). Separate multiple '
                  'extensions with commas, or use -e multiple times.'),
        )
        parser.add_argument(
            '--purge', '-p', action='store_true', dest='purge', default=False,
            help=('Replace the entire resource content with the '
                  'pushed content of this request. If not provided (the '
                  'default), then append the source content of this request '
                  'to the existing resource content.'),
        )
        parser.add_argument(
            '--symlinks', '-s', action='store_true', dest='symlinks',
            default=False,
            help=('Follows symlinks to directories when examining source code '
                  'and templates for translation strings.'),
        )

    def handle(self, *args, **options):
        self.domain = options['domain']
        self.verbosity = options['verbosity']
        self.ignore_patterns = []
        self.purge = options['purge']
        self.symlinks = options['symlinks']
        extensions = options['extensions']
        if self.domain == 'djangojs':
            exts = extensions if extensions else ['js']
        else:
            exts = extensions if extensions else ['html', 'txt', 'py']
        self.extensions = handle_extensions(exts)
        self.locale_paths = []
        self.default_locale_path = None

        self.string_collection = SourceStringCollection()

        # Create an extractor for Python files, to reuse for all files
        self.python_extractor = Extractor()
        # Support `t()` and `ut()` calls made on the Django module.
        self.python_extractor.register_functions(
            'transifex.native.django.t',
            'transifex.native.django.ut',
            'transifex.native.django.lazyt')

        self.stats = {'processed_files': 0, 'strings': []}

        # Search all related files and collect translatable strings,
        # storing them in `self.string_collection`
        self.collect_strings()

        # Push the strings to the CDS
        self.push_strings()

    def collect_strings(self):
        """Search all related files, collect and store translatable strings.

        Stores found strings in `self.string_collection`.
        """
        self.output('Parsing all files to detect translatable content...')
        files = self._find_files('.', 'push')
        for f in files:
            extracted = self._extract_strings(f)
            self.string_collection.extend(extracted)
            self.stats['processed_files'] += 1
            if extracted and len(extracted):
                self.stats['strings'].append((f.file, len(extracted)))
        self._show_collect_results()

    def push_strings(self):
        """Push strings to the CDS."""
        total = len(self.string_collection.strings)
        if total == 0:
            self.output('There are no strings to push to Transifex.')
            return

        self.output('Pushing {} source strings to Transifex...'.format(total))
        status_code, response_content = tx.push_source_strings(
            self.string_collection.strings.values(), self.purge
        )
        self._show_push_results(status_code, response_content)

    def _extract_strings(self, translatable_file):
        """Extract source strings from the given file.

        Supports both Python files and Django template files.

        :param TranslatableFile translatable_file: the file to search
        :return: a list of SourceString objects
        :rtype: list
        """
        self.verbose('Processing file %s in %s' % (
            translatable_file.file, translatable_file.dirpath
        ))
        encoding = (
            settings.FILE_CHARSET if self.settings_available
            else 'utf-8'
        )
        try:
            src_data = self._read_file(translatable_file.path, encoding)
        except UnicodeDecodeError as e:
            self.verbose(
                'UnicodeDecodeError: skipped file %s in %s (reason: %s)' % (
                    translatable_file.file, translatable_file.dirpath, e,
                )
            )
            return None

        _, extension = os.path.splitext(translatable_file.file)
        # Python file
        if extension == '.py':
            return self.python_extractor.extract_strings(
                force_text(src_data), translatable_file.path[2:]
            )

        # Template file
        return extract_transifex_template_strings(
            src_data, translatable_file.path[2:], encoding,
        )

    def _show_collect_results(self):
        """Display results of collecting source strings from files."""
        total_strings = sum([x[1] for x in self.stats['strings']])
        self.output(
            'Processed {} file(s) and found {} translatable strings '
            'in {} of them'.format(
                self.stats['processed_files'], total_strings, len(self.stats)
            )
        )

    def _show_push_results(self, status_code, response_content):
        """Display results of pushing the source strings to CDS.

        :param int status_code: the HTTP status code
        :param dict response_content: the content of the response
        """
        try:
            if 200 <= status_code < 300:
                # {"created":0,"updated":5,"skipped":1,"deleted":0,"failed":0,"errors":[]}
                created = response_content.get('created')
                updated = response_content.get('updated')
                skipped = response_content.get('skipped')
                deleted = response_content.get('deleted')
                failed = response_content.get('failed')
                errors = response_content.get('errors', [])
                self.output(
                    'Successfully pushed strings to Transifex.\n'
                    'Status: {code}\n'
                    'Created strings: {created}\n'
                    'Updated strings: {updated}\n'
                    'Skipped strings: {skipped}\n'
                    'Deleted strings: {deleted}\n'
                    'Failed strings: {failed}\n'
                    'Errors: {errors}\n'.format(
                        code=status_code,
                        created=created,
                        updated=updated,
                        skipped=skipped,
                        deleted=deleted,
                        failed=failed,
                        errors='\n'.join(errors)
                    )
                )

            else:
                message = response_content.get('message')
                details = response_content.get('details')
                self.output(
                    'Could not push strings to Transifex.\n'
                    'Status: {code}\n'
                    'Message: {message}\n'
                    'Details: {details}\n'.format(
                        code=status_code,
                        message=message,
                        details=json.dumps(details, indent=4),
                    )
                )
        except Exception:
            self.output(
                '(Error while printing formatted report, '
                'falling back to raw format)\n'
                'Status: {code}\n'
                'Content: {content}'.format(
                    code=status_code,
                    content=response_content,
                )
            )
