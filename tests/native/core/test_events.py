import pytest
import responses

from transifex.native import TxNative
from transifex.native.events import EventDispatcher


def test_simple():
    e = EventDispatcher(('a', 'b'))
    counts = {'a': 0, 'b': 0}

    def incr_a():
        counts['a'] += 1

    def incr_b():
        counts['b'] += 1

    e.on('a', incr_a)

    e.trigger('a')
    e.trigger('b')

    assert counts == {'a': 1, 'b': 0}

    e.on('b', incr_b)

    e.trigger('a')
    e.trigger('b')

    assert counts == {'a': 2, 'b': 1}

    e.off('b', incr_b)

    e.trigger('a')
    e.trigger('b')

    assert counts == {'a': 3, 'b': 1}

    with pytest.raises(ValueError) as exc_info:
        e.on('c', incr_b)
    assert str(exc_info.value) == "'c' is not a valid event name"

    with pytest.raises(KeyError) as exc_info:
        e.off('b', incr_b)
    assert str(exc_info.value) == str(incr_b)


@responses.activate
def test_get_languages_triggers_events():
    responses.add(responses.GET,
                  "http://some.host/languages",
                  json={'data': []},
                  status=200)
    counts = {'FETCHING_LANGUAGES': 0, 'LANGUAGES_FETCHED': 0}

    def incr_fetching_languages(*args, **kwargs):
        counts['FETCHING_LANGUAGES'] += 1

    def incr_languages_fetched(*args, **kwargs):
        counts['LANGUAGES_FETCHED'] += 1

    tx = TxNative(cds_host="http://some.host")
    tx.on('FETCHING_LANGUAGES', incr_fetching_languages)
    tx.on('LANGUAGES_FETCHED', incr_languages_fetched)

    tx.get_languages()

    assert counts == {'FETCHING_LANGUAGES': 1, 'LANGUAGES_FETCHED': 1}


@responses.activate
def test_fetch_translations_triggers_events():
    responses.add(responses.GET,
                  "http://some.host/languages",
                  json={'data': [{'code': "el"}, {'code': "fr"}]},
                  status=200)
    responses.add(responses.GET,
                  "http://some.host/content/el",
                  json={'data': {}},
                  status=200)
    responses.add(responses.GET,
                  "http://some.host/content/fr",
                  json={'data': {}},
                  status=200)

    logged_events = []

    def log_fetching_translations(*args):
        logged_events.append(('FETCHING_TRANSLATIONS', args))

    def log_translations_fetched(*args):
        logged_events.append(('TRANSLATIONS_FETCHED', args))

    tx = TxNative(cds_host="http://some.host")
    tx.on('FETCHING_TRANSLATIONS', log_fetching_translations)
    tx.on('TRANSLATIONS_FETCHED', log_translations_fetched)
    tx.fetch_translations()

    assert logged_events == [('FETCHING_TRANSLATIONS', ("el", )),
                             ('TRANSLATIONS_FETCHED', ("el", )),
                             ('FETCHING_TRANSLATIONS', ("fr", )),
                             ('TRANSLATIONS_FETCHED', ("fr", ))]
