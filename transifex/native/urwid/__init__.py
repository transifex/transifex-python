""" Utilities for integrating urwid applications with Transifex Native. """

import urwid
from transifex.native import t, tx


class Variable(object):
    """ Holds a value and will trigger events on change.

            >>> v = Variable(1)
            >>> v.on_change(lambda: print("New value: " + v.get()))
            >>> v.set(v.get() + 1)
            <<< # New value: 2
    """

    def __init__(self, value):
        self._value = value
        self._callbacks = set()

    def get(self):
        return self._value

    def set(self, value):
        if value != self._value:
            self._value = value
            for callback in self._callbacks:
                callback(value)

    def on_change(self, callback):
        self._callbacks.add(callback)

    def off_change(self, callback):
        self._callbacks.remove(callback)


class T(urwid.Text):
    """ Usage:

        Render the string in the current language. Will rerender on language
        change:

            >>> T("Hello world")

        Render using the variable as template parameter, will rerender on
        language change and if the parameter changes value:

            >>> variable = Variable("Bob")
            >>> T("Hello {username}", {'username': variable})
            >>> variable.set("Jill")

        Render inside an untranslatable wrapper template:

            >>> T("Hello world", wrapper="Translation: {}")
    """

    def __init__(self, source_string, params=None, wrapper=None, _context=None,
                 _charlimit=None, _comment=None, _occurrences=None, _tags=None,
                 *args, **kwargs):
        if params is None:
            params = {}

        self._source_string = source_string
        self._params = params
        self._wrapper = wrapper

        tx.on("LOCALE_CHANGED", self.rerender)
        for key, value in self._params.items():
            try:
                value.on_change(self.rerender)
            except AttributeError:
                pass

        super().__init__("", *args, **kwargs)
        self.rerender()

    def rerender(self, *args, **kwargs):
        params = {}
        for key, value in self._params.items():
            try:
                params[key] = value.get()
            except AttributeError:
                params[key] = value

        translation = t(self._source_string, params=params)

        if self._wrapper is not None:
            self.set_text(self._wrapper.format(translation))
        else:
            self.set_text(translation)


def language_picker(source_language=None):
    """ Returns an array of radio buttons for language selection.

        The 'source_language' must be a dictionary describing the source
        language, with at least the 'name' and 'code' fields. If unset,
        `{'name': "English", 'code': "en"}` will be used
    """

    if source_language is None:
        source_language = {'name': "English", 'code': "en"}

    languages = tx.fetch_languages()
    if not any((language['code'] == source_language['code']
                for language in languages)):
        languages = [source_language] + languages

    language_group, language_radio = [], []
    for language in languages:
        button = urwid.RadioButton(language_group, language['name'])
        urwid.connect_signal(button, 'change', _on_language_select,
                             language['code'])
        language_radio.append(button)
    return language_radio


def _on_language_select(radio_button, new_state, language_code):
    if new_state:
        tx.set_current_language(language_code)
