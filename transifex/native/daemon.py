import logging
import threading
import time

from transifex.native import tx

logger = logging.getLogger('transifex.native.threading')


class DaemonicThread(threading.Thread):
    """A daemon thread that implements the logic of fetching
    translations periodically."""
    daemon = True
    should_exit = False

    def start_daemon(self, interval):
        """Start the daemon.

        Calls `threading.Thread.start()` to schedule execution in a different thread.

        :param int interval: the interval the daemon will use when fetching
            translations.
        """
        if self.is_daemon_running(log_errors=False):
            return False
        self.interval = interval
        self.start()
        return True

    def run(self, *args, **kwargs):
        """
        Fetches translations in an interval. Will not stop if exceptions are
        raised.
        """
        while not self.should_exit:
            logger.debug('Will fetch translations')
            try:
                tx.fetch_translations()
            except Exception as e:
                logger.exception(
                    'Fetching daemon exception: {}'.format(str(e)))
            time.sleep(self.interval)

    def is_daemon_running(self, log_errors=True, **kwargs):
        """Return whether the daemon is running or not.

        Checks both `is_alive` and `isAlive` (python compatibility)

        :param bool log_errors: Whether to log errors if the thread is
            not alive or not. Useful when using this method in your application
            so that you get notified if the daemon has stopped for some reason.
        """
        is_running_func = getattr(self, 'is_alive', None)
        if not is_running_func:
            is_running_func = getattr(self, 'isAlive', None)
        is_running = is_running_func() if is_running_func else False

        if not is_running and log_errors:
            logger.error('Fetching daemon error: The daemon is not running!')
        return is_running

    def stop_daemon(self):
        """Set the `should_exit` variable (which should force the thread to
        stop execution), then `join`s the thread.

        Meant to be used if you explicitly want to kill the thread which is
        usually not necessary since it's a demonic thread. This function can
        potentially **block** for `interval` seconds, so use wisely.
        """

        self.should_exit = True
        self.join()


daemon = DaemonicThread()
