class EventDispatcher(object):
    """ Simple event dispatcher.

        - Create an instance
        - Assign a callable to an event type with `on`
        - Unassign a previously assigned callable from an event type with `off`
        - Trigger an event type with `trigger`; args and kwargs to `trigger`
          will be passed on to the assigned callables

        During operations, you may get a `ValueError` if you try to operate on
        an invalid event type. During `off`, you may get a `KeyError` if you
        try to remove a non previously assigned callback.

        Usage:

            >>> dispatcher = EventDispatcher(['sample_event_type'])
            >>> dispatcher.on('sample_event_type',
            ...               lambda: print("hello world"))
            >>> dispatcher.trigger('sample_event_type')  # prints "hello world"
    """

    DEFAULT_VALID_EVENT_NAMES = ("FETCHING_LANGUAGES",
                                 "LANGUAGES_FETCHED",
                                 "FETCHING_TRANSLATIONS",
                                 "TRANSLATIONS_FETCHED",
                                 "CURRENT_LANGUAGE_CHANGED")

    def __init__(self, valid_event_names=None):
        if valid_event_names is None:
            valid_event_names = self.DEFAULT_VALID_EVENT_NAMES

        self._valid_event_names = valid_event_names
        self._events = {}

    def on(self, event_name, callback):
        self._require_valid_event_name(event_name)
        self._events.setdefault(event_name, set()).add(callback)

    def off(self, event_name, callback):
        self._require_valid_event_name(event_name)
        self._events.setdefault(event_name, set()).remove(callback)

    def trigger(self, event_name, *args, **kwargs):
        self._require_valid_event_name(event_name)
        for callback in self._events.get(event_name, set()):
            callback(*args, **kwargs)

    def _require_valid_event_name(self, event_name):
        if event_name not in self._valid_event_names:
            raise ValueError("'{}' is not a valid event name".
                             format(event_name))
