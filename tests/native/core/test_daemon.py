import time

from mock import patch
from transifex.native import TxNative
from transifex.native.daemon import DaemonicThread


class TestFetchingDaemon(object):

    @patch('transifex.native.daemon.tx')
    def test_daemon_starts(self, patched_tx):
        tx = TxNative()
        tx.init(['en', 'el'], 'some:token', 'https://some.host')

        # the `interval` we will be using
        interval = 1

        daemon = DaemonicThread()

        # nothing is running
        assert not daemon.is_daemon_running(log_errors=False)

        # start deamon
        daemon.start_daemon(interval=interval)

        # test that thread has started
        time.sleep(interval * 2)
        assert daemon.is_daemon_running(log_errors=False)

        # test that `fetch_translations` has been called
        assert patched_tx.fetch_translations.call_count > 0

        daemon.stop_daemon()
        assert not daemon.is_daemon_running()

    @patch('transifex.native.daemon.tx')
    @patch('transifex.native.daemon.logger')
    def test_daemon_exception(self, patched_logger, patched_tx):

        patched_tx.fetch_translations.side_effect = Exception(
            'Something went wrong')

        tx = TxNative()
        tx.init(['en', 'el'], 'some:token', 'https://some.host')

        daemon = DaemonicThread()

        interval = 1
        daemon.start_daemon(interval=1)
        time.sleep(interval * 2)
        assert daemon.is_daemon_running(log_errors=False)

        patched_logger.exception.assert_called_with(
            'Fetching daemon exception: Something went wrong'
        )
        daemon.stop_daemon()
