# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils import translation

from transifex.common.strings import LazyString
from transifex.common.utils import generate_key
from transifex.native import tx
from transifex.native.django.utils import lazy_translate, translate


def test_translate_without_translation():
    tx.setup(source_language_code="en_US")
    translation.activate("en-US")
    assert translate('A string') == 'A string'
    tx.source_language_code = None  # reset


def test_lazy_translate_without_translation():
    tx.setup(source_language_code="en_US")
    translation.activate("en-US")
    string = lazy_translate('A string')
    assert isinstance(string, LazyString)
    assert string == 'A string'
    tx.source_language_code = None  # reset


def test_translate_with_translation():
    tx.setup(source_language_code="en")
    old_cache = tx._cache
    key = generate_key("Hello, {user}!")
    tx._cache = {'en_US': {key: "Γεια σου, {user}!"}}
    assert translate("Hello, {user}!", user="John") == "Γεια σου, John!"
    tx._cache = old_cache
    tx.source_language_code = None  # reset


def test_lazy_translate_with_translation():
    tx.setup(source_language_code="en")
    old_cache = tx._cache
    key = generate_key("Hello, {user}!")
    tx._cache = {'en_US': {key: "Γεια σου, {user}!"}}
    assert lazy_translate("Hello, {user}!", user="John") == "Γεια σου, John!"
    tx._cache = old_cache
    tx.source_language_code = None  # reset
