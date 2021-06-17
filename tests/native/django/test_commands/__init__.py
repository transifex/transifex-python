from transifex.native.django.management.commands.transifex import Command


def get_transifex_command():
    """Return an instance of the Transifex Django command
    that works in all Django versions.

    After Django 2.0+, attempting to run
    `call_command(command, 'subcommand', option=value)`
    with `option` not being defined on the main command results
    to a TypeError, e.g. Unknown option(s) for transifex command: dry_run

    This is solved by adding all possible options to the command's
    `stealth_options` attribute.
    """
    command = Command()
    command.stealth_options = (
        # Migrate
        'files',
        'path',
        'text',
        'save_policy',
        'review_policy',
        'mark_policy',
        'verbose',

        # Push
        'extension',
        'append_tags',
        'with_tags_only',
        'without_tags_only',
        'dry_run',
        'symlinks',

        # Invalidate
        'purge',
    )
    return command
