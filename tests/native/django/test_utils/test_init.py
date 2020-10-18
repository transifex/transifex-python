# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils import translation
from mock import patch

from transifex.common.strings import LazyString
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


@patch('transifex.native.core.TxNative.get_translation')
def test_translate_with_translation(mock_get_translation):
    mock_get_translation.return_value = 'Γεια σου, {user}!'
    string = translate("Doesn't matter", user='John')
    assert string == 'Γεια σου, John!'


@patch('transifex.native.core.TxNative.get_translation')
def test_lazy_translate_with_translation(mock_get_translation):
    mock_get_translation.return_value = 'Γεια σου, {user}!'
    string = lazy_translate("Doesn't matter", user='John')
    assert string == 'Γεια σου, John!'
