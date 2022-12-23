from transifex.native.core import TxNative


def init(
    token, languages, secret=None,
    cds_host=None, missing_policy=None,
    error_policy=None, cache=None,
    fetch_all_langs=False,
    filter_tags=None,
    filter_status=None,
):
    """Initialize the framework.

    :param list languages: A list of language codes for the languages
        the application is localized into
    :param str token: the API token to use for connecting to the CDS
    :param str secret: the additional secret required for pushing translations
    :param str cds_host: an optional host for the Content Delivery Service,
        defaults to the host provided by Transifex
    :param AbstractRenderingPolicy missing_policy: an optional policy to use
        for returning strings when a translation is missing
    :param AbstractErrorPolicy error_policy: an optional policy to use
        for defining how to handle translation rendering errors
    :param AbstractCache cache: an optional cache
    :param bool fetch_all_langs: force pull all remote languages
    :param str filter_tags: fetch only content with tags
    :param str filter_status: fetch only content with specific translation status
    """
    if not tx.initialized:
        tx.init(
            languages,
            token,
            secret=secret,
            cds_host=cds_host,
            missing_policy=missing_policy,
            error_policy=error_policy,
            cache=cache,
            fetch_all_langs=fetch_all_langs,
            filter_tags=filter_tags,
            filter_status=filter_status,
        )


tx = TxNative()
