# -*- coding: utf-8 -*-
import mock
from django.core.management import call_command
from tests.native.django.test_commands import get_transifex_command
from transifex.common.console import Color
from transifex.native.django.management.commands.transifex import Command

PATH_INVALIDATE_CACHE = ('transifex.native.django.management.utils.push.tx.'
                         'invalidate_cache')


@mock.patch(PATH_INVALIDATE_CACHE)
@mock.patch('transifex.common.console.Color.echo')
def test_invalidate_cache_fail(mock_echo, mock_invalidate_cache):
    mock_invalidate_cache.return_value = 500, {
        'message': 'error message',
        'details': 'error details',
    }

    expected = Color.format(
        '[error]\nCould not invalidate CDS.[end]\n'
        '[high]Status:[end] [warn]{code}[end]\n'
        '[high]Message:[end] [warn]{message}[end]\n'.format(
            code=500,
            message='error message',
        )
    )

    # Make sure it's idempotent
    mock_echo.reset_mock()
    command = get_transifex_command()
    call_command(command, 'invalidate')
    actual = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == actual


@mock.patch(PATH_INVALIDATE_CACHE)
@mock.patch('transifex.common.console.Color.echo')
def test_invalidate_cache_success(mock_echo, mock_invalidate_cache):
    mock_invalidate_cache.return_value = 200, {
        'count': 5,
    }

    expected = Color.format(
        '[green]\nSuccessfully invalidated CDS cache.[end]\n'
        '[high]Status:[end] [warn]{code}[end]\n'
        '[high]Records invalidated: {count}[end]\n'
        '[high]Note: It might take a few minutes for '
        'fresh content to be available\n'.format(
            code=200,
            count=5,
        )
    )

    # Make sure it's idempotent
    mock_echo.reset_mock()
    command = get_transifex_command()
    call_command(command, 'invalidate')
    actual = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == actual


@mock.patch(PATH_INVALIDATE_CACHE)
@mock.patch('transifex.common.console.Color.echo')
def test_purge_cache_success(mock_echo, mock_invalidate_cache):
    mock_invalidate_cache.return_value = 200, {
        'count': 5,
    }

    expected = Color.format(
        '[green]\nSuccessfully purged CDS cache.[end]\n'
        '[high]Status:[end] [warn]{code}[end]\n'
        '[high]Records purged: {count}[end]\n'.format(
            code=200,
            count=5,
        )
    )

    # Make sure it's idempotent
    mock_echo.reset_mock()
    command = get_transifex_command()
    call_command(command, 'invalidate', purge=True)
    actual = Color.format(mock_echo.call_args_list[1][0][0])
    assert expected == actual
