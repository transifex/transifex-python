class EventDispatcher(object):
    LABELS = ['FETCHING_TRANSLATIONS', 'TRANSLATIONS_FETCHED',
              'TRANSLATIONS_FETCH_FAILED', 'LOCALE_CHANGED',
              'FETCHING_LOCALES', 'LOCALES_FETCHED', 'LOCALES_FETCH_FAILED']

    def __init__(self):
        self.callbacks = {}

    def on(self, label, callback):
        self._require_label(label)
        self.callbacks.setdefault(label, set()).add(callback)

    def off(self, label, callback):
        self._require_label(label)
        # Can raise KeyError if callback is not there
        self.callbacks.get(label, set()).remove(callback)

    def trigger(self, label, *args, **kwargs):
        self._require_label(label)
        for callback in self.callbacks.get(label, []):
            callback(*args, **kwargs)

    def _require_label(self, label):
        if label not in self.LABELS:
            raise ValueError("Label '{}' is not supported".format(label))
