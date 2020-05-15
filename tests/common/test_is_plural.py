from transifex.common.utils import parse_plurals


def test_simple():
    assert (False, {5: "hello world"}) == parse_plurals("hello world")

    assert (True, {1: 'ONE', 5: 'OTHER'}) == \
        parse_plurals("{cnt, plural, one {ONE} other {OTHER}}")

    assert (True, {1: 'ONE', 5: 'OTHER'}) == \
        parse_plurals("{cnt, plural, one {ONE} =5 {OTHER}}")

    assert (True, {1: 'ONE', 5: 'OTHER'}) == \
        parse_plurals("{cnt, plural, =1 {ONE} other {OTHER}}")

    assert (True, {1: 'ONE', 5: 'OTHER'}) == \
        parse_plurals("{cnt, plural, =1 {ONE} =5 {OTHER}}")


def test_almost_plural():
    assert (False, {5: "{cnt, plural, one {ONE} other {OTHER}"}) ==\
        parse_plurals("{cnt, plural, one {ONE} other {OTHER}")
    assert (False, {5: "{cnt, plurall, one {ONE} other {OTHER}}"}) ==\
        parse_plurals("{cnt, plurall, one {ONE} other {OTHER}}")
    assert (False, {5: "{cnt, plural, onee {ONE} other {OTHER}}"}) ==\
        parse_plurals("{cnt, plural, onee {ONE} other {OTHER}}")
    assert (False, {5: "{cnt, plural, =7 {ONE} other {OTHER}}"}) ==\
        parse_plurals("{cnt, plural, =7 {ONE} other {OTHER}}")
    assert (False, {5: "{cnt, plural, one {ONE}, other {OTHER}}"}) ==\
        parse_plurals("{cnt, plural, one {ONE}, other {OTHER}}")
    assert (False, {5: "{cnt, plural, one {ONE} many {OTHER}}"}) ==\
        parse_plurals("{cnt, plural, one {ONE} many {OTHER}}")
    assert (False, {5: "{cnt, plural, one {ONE}}"}) ==\
        parse_plurals("{cnt, plural, one {ONE}}")


def test_escapes():
    assert (True, {1: "O '' NE", 5: 'OTHER'}) == \
        parse_plurals("{cnt, plural, one {O '' NE} other {OTHER}}")
    assert (True, {1: "O '{ NE'", 5: 'OTHER'}) == \
        parse_plurals("{cnt, plural, one {O '{ NE'} other {OTHER}}")
