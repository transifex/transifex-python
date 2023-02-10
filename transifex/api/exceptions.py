class FileExchangeException(Exception):
    def __init__(self, message, errors):
        super().__init__(message, errors)

    @property
    def message(self):
        return self.args[0]

    @property
    def errors(self):
        return self.args[1]

    def __str__(self):
        """We expect Transifex APIv3 to only return one error during a file exchange.
        Even though for future compatibility we include the full list of errors in the
        exception objects, we override 'str' so that if someone does:

        >>> try:
        ...     transifex_api.ResourceStringsAsyncUpload(...)
        ... except UploadException as e:
        ...     print(f"Upload error: {e}")

        We want the first error's 'detail' field to appear. The full error list
        can still be accessed via the second argument.
        """

        return self.message


class DownloadException(FileExchangeException):
    pass


class UploadException(FileExchangeException):
    pass
