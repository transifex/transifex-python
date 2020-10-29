import glob
import logging
import os

import click

from .cds import CDSHandler
from .parsing import SourceStringSet, extract


logger = logging.getLogger(__name__)


@click.group(context_settings={'help_option_names': ["-h", "--help"]})
@click.option('-v', '--verbose', is_flag=True, help="Enables verbose mode")
@click.option('-t', '--traceback', is_flag=True,
              help="Show full traceback on errors")
@click.pass_context
def cli(ctx, verbose, traceback):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['traceback'] = traceback


@cli.command(help="Show help")
@click.argument('command', default="")
def help(command):
    if command:
        try:
            command = cli.commands[command]
        except KeyError:
            click.echo("Unknown command {}".format(command))
            cli.invoke(cli.make_context('txpy-cli', ['--help']))
        else:
            command.invoke(command.make_context('txpy-cli {}'.format(command),
                                                ['--help']))
    else:
        cli.invoke(cli.make_context('txpy-cli', ['--help']))


@cli.command(context_settings={'help_option_names': ["-h", "--help"]},
             help="Detect translatable strings and push content to Transifex")
@click.option('-c', '--cds-host', default=None, help="CDS host URL")
@click.option('-t', '--token', prompt=True, hide_input=True,
              envvar="TRANSIFEX_TOKEN", help="Native project public token")
@click.option('-s', '--secret', prompt=True, hide_input=True,
              envvar="TRANSIFEX_SECRET", help="Native project secret")
@click.option('-p', '--purge', is_flag=True, help="Purge content on Transifex")
@click.option('--tags', default="", help="Globally tag strings")
@click.option('-d', '--dry-run', is_flag=True,
              help="Only extract, do not push to Transifex")
@click.argument('pattern', nargs=-1)
@click.pass_context
def push(ctx, cds_host, token, secret, purge, tags, dry_run, pattern):
    if ctx.obj['traceback']:
        push_with_exceptions(ctx, cds_host, token, secret, purge, tags,
                             dry_run, pattern)
    else:
        try:
            push_with_exceptions(ctx, cds_host, token, secret, purge, tags,
                                 dry_run, pattern)
        except (click.ClickException, EOFError, KeyboardInterrupt):
            raise
        except Exception as e:
            click.echo(str(e))


def push_with_exceptions(ctx, cds_host, token, secret, purge, tags, dry_run,
                         pattern):
    if tags:
        tags = [tag.strip() for tag in tags.split(',')]

    if not pattern:
        pattern = ('.', )
    paths = _get_paths(pattern)
    source_strings = SourceStringSet()

    click.echo("Extracting from {} file{}".
               format(len(paths), "s" if len(paths) != 1 else ""))
    error_count = 0
    for path in paths:
        if ctx.obj['verbose']:
            click.echo("- Extracting from {}".format(path))
        try:
            file_source_strings = extract(path)
        except Exception as e:
            error_count += 1
            if ctx.obj['verbose']:
                if ctx.obj['traceback']:
                    logger.exception(e)
                else:
                    click.echo("  - Problem extracting from {}, use the "
                               "--traceback option for more information".
                               format(path))
            continue
        if ctx.obj['verbose']:
            for source_string in file_source_strings:
                click.echo("  - Found {}".format(str(source_string)))
            click.echo("  - Found {} string{} total".
                       format(len(file_source_strings),
                              "s" if len(file_source_strings) != 1 else ""))
        for source_string in file_source_strings:
            source_string.tags = list(set(source_string.tags or []) |
                                      set(tags))
        source_strings |= file_source_strings

    if ctx.obj['verbose']:
        click.echo("Encountered problems while extracting from {} file{}".
                   format(error_count, "s" if error_count != 1 else ""))
    else:
        click.echo("Encountered problems while extracting from {} file{}, use "
                   "--verbose and/or --traceback options for more information".
                   format(error_count, "s" if error_count != 1 else ""))

    click.echo("Extracted {} string{}".
               format(len(source_strings),
                      "s" if len(source_strings) != 1 else ""))

    if dry_run:
        click.echo("Dry run selected, skipping push to CDS")
    else:
        click.echo("Pushing to CDS with purge {}".
                   format("ON" if purge else "OFF"))
        cds = CDSHandler(host=cds_host, token=token, secret=secret)
        report = cds.push_source_strings(source_strings, purge=purge)
        click.echo("Done")
        click.echo(str(report))


def _get_paths(patterns):
    """ Returns a list of file paths """

    # 1st pass: glob
    dirpaths = [path
                for pattern in patterns
                for path in glob.glob(pattern, recursive=True)]

    # 2nd pass: directories
    filepaths = []
    for dirpath in dirpaths:
        if os.path.isdir(dirpath):
            filepaths.extend((filepath
                              for filepath in glob.glob(dirpath + "/**/*.py",
                                                        recursive=True)))
        else:
            filepaths.append(dirpath)

    # 3rd pass: only keep python files
    return [path for path in filepaths if path.endswith('.py')]
