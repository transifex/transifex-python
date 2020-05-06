# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from mock import patch
from transifex.common.strings import LazyString
from transifex.native.django.utils import lazy_translate, translate


def test_translate_without_translation():
    assert translate('A string') == 'A string'


def test_lazy_translate_without_translation():
    string = lazy_translate('A string')
    assert isinstance(string, LazyString)
    assert string == 'A string'


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
