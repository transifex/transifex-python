from __future__ import absolute_import, unicode_literals

from transifex.common.console import Color
from transifex.native import tx
from transifex.native.django.management.utils.base import CommandMixin


class Invalidate(CommandMixin):
    def add_arguments(self, subparsers):
        parser = subparsers.add_parser(
            'invalidate',
            help=('Invalidate CDS, forcing it to re-cache fresh '
                  'translations.'),
        )
        parser.add_argument(
            '--purge', '-p', action='store_true', dest='purge', default=False,
            help=('Force purging CDS cache instead of refreshing content '
                  'asynchronously in the background. (not recommended)'),
        )

    def handle(self, *args, **options):
        purge = options['purge']

        if purge:
            Color.echo('Purging CDS cache...')
        else:
            Color.echo('Invalidating CDS cache...')

        status_code, response_content = tx.invalidate_cache(purge)

        try:
            if 200 <= status_code < 300:
                # {"count":0}
                count = response_content.get('count')
                if purge:
                    Color.echo(
                        '[green]\nSuccessfully purged CDS cache.[end]\n'
                        '[high]Status:[end] [warn]{code}[end]\n'
                        '[high]Records purged: {count}[end]\n'.format(
                            code=status_code,
                            count=count,
                        )
                    )
                else:
                    Color.echo(
                        '[green]\nSuccessfully invalidated CDS cache.[end]\n'
                        '[high]Status:[end] [warn]{code}[end]\n'
                        '[high]Records invalidated: {count}[end]\n'
                        '[high]Note: It might take a few minutes for '
                        'fresh content to be available\n'.format(
                            code=status_code,
                            count=count,
                        )
                    )
            else:
                message = response_content.get('message')
                Color.echo(
                    '[error]\nCould not invalidate CDS.[end]\n'
                    '[high]Status:[end] [warn]{code}[end]\n'
                    '[high]Message:[end] [warn]{message}[end]\n'.format(
                        code=status_code,
                        message=message,
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
