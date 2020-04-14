from transifex.common.utils import is_plural


def test_simple():
    assert not is_plural("hello world")
    assert is_plural("{cnt, plural, one {ONE} other {OTHER}}")
    assert is_plural("{cnt, plural, one {ONE} =5 {OTHER}}")
    assert is_plural("{cnt, plural, =1 {ONE} other {OTHER}}")
    assert is_plural("{cnt, plural, =1 {ONE} =5 {OTHER}}")


def test_almost_plural():
    assert not is_plural("{cnt, plural, one {ONE} other {OTHER}")
    assert not is_plural("{cnt, plurall, one {ONE} other {OTHER}}")
    assert not is_plural("{cnt, plural, onee {ONE} other {OTHER}}")
    assert not is_plural("{cnt, plural, =7 {ONE} other {OTHER}}")
    assert not is_plural("{cnt, plural, one {ONE}, other {OTHER}}")
    assert not is_plural("{cnt, plural, one {ONE} many {OTHER}}")
    assert not is_plural("{cnt, plural, one {ONE}}")


def test_escapes():
    assert is_plural("{cnt, plural, one {O '' NE} other {OTHER}}")
    assert is_plural("{cnt, plural, one {O '{ NE'} other {OTHER}}")
