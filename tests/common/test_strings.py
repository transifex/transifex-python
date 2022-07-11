from __future__ import unicode_literals

import sys

import pytest

from transifex.common.strings import LazyString, alt_quote, printf_to_format_style


def test_printf_to_format_style():
    string, variables = printf_to_format_style("This is %s & %s")
    assert string == "This is {variable_1} & {variable_2}"
    assert set(variables) == {"variable_1", "variable_2"}

    string, variables = printf_to_format_style("This is %(foo)s and %(bar)s")
    assert string == "This is {foo} and {bar}"
    assert set(variables) == {"foo", "bar"}

    string, variables = printf_to_format_style("This is %s and %(bar)s and %s")
    assert string == "This is {variable_1} and {bar} and {variable_2}"
    assert set(variables) == {"variable_1", "bar", "variable_2"}


def test_alt_quote():
    assert alt_quote('"', r"This is a string") == '"'
    assert alt_quote('"', r'This is a " string') == "'"
    assert alt_quote('"', r"This is a \" string") == '"'

    assert alt_quote("'", r"This is a string") == "'"
    assert alt_quote("'", r"This is a ' string") == '"'
    assert alt_quote("'", r"This is a \' string") == "'"


class TestLazyString:
    def test_add(self):
        assert LazyString(str.upper, "hello") + " world" == "HELLO world"
        assert "hello" + LazyString(str.upper, " world") == "hello WORLD"

    def test_contains(self):
        assert "world" not in LazyString(str.upper, "hello world")
        assert "WORLD" in LazyString(str.upper, "hello world")

    def test_eq(self):
        assert LazyString(str.upper, "hello world") == "HELLO WORLD"
        assert "HELLO WORLD" == LazyString(str.upper, "hello world")
        assert LazyString(str.upper, "hello world") != "hello world"
        assert "hello world" != LazyString(str.upper, "hello world")

    def test_ge(self):
        assert not LazyString(str.upper, "b") >= "a"
        assert LazyString(str.upper, "b") >= "A"

    def test_getitem(self):
        assert LazyString(str.upper, "hello world")[1] == "E"

    def test_gt(self):
        assert not LazyString(str.upper, "b") > "a"
        assert LazyString(str.upper, "b") > "A"

    def test_hash(self):
        assert hash(LazyString(str.upper, "hello world")) != hash("hello world")
        assert hash(LazyString(str.upper, "hello world")) == hash("HELLO WORLD")

    def test_iter(self):
        assert list(LazyString(str.upper, "hello")) == ["H", "E", "L", "L", "O"]

    def test_le(self):
        assert LazyString(str.upper, "b") <= "a"
        assert not LazyString(str.upper, "b") <= "A"

    def test_len(self):
        assert len(LazyString(lambda s: s * 2, "abc")) == 6

    def test_lt(self):
        assert LazyString(str.upper, "b") < "a"
        assert not LazyString(str.upper, "b") < "A"

    def test_mod(self):
        assert LazyString(str.upper, "hello %f") % 1.0 == "HELLO 1.000000"

    def test_mul(self):
        assert LazyString(str.upper, "abc") * 2 == "ABCABC"

    def test_ne(self):
        assert not LazyString(str.upper, "hello world") != "HELLO WORLD"
        assert LazyString(str.upper, "hello world") != "hello world"

    def test_rmod(self):
        assert "hello %s" % LazyString(str.upper, "world") == "hello WORLD"

    def test_rmul(self):
        assert 2 * LazyString(str.upper, "abc") == "ABCABC"

    def test_str(self):
        assert str(LazyString(str.upper, "hello world")) == "HELLO WORLD"

    def test_capitalize(self):
        assert LazyString(str.lower, "HELLO WORLD").capitalize() == "Hello world"

    def test_casefold(self):
        assert LazyString(str.upper, "ß").casefold() == "ss"

    def test_center(self):
        assert LazyString(str.upper, "hello world").center(20) == "    HELLO WORLD     "

    def test_count(self):
        assert LazyString(str.upper, "hello world").count("l") == 0
        assert LazyString(str.upper, "hello world").count("L") == 3

    def test_encode(self):
        assert (
            LazyString(str.upper, "hεllo world").encode("utf8") == b"H\xce\x95LLO WORLD"
        )
        assert (
            LazyString(str.upper, "hεllo world").encode("iso-8859-7")
            == b"H\xc5LLO WORLD"
        )

    def test_endswith(self):
        assert not LazyString(str.upper, "hello world").endswith("world")
        assert LazyString(str.upper, "hello world").endswith("WORLD")

    def test_expandtabs(self):
        assert LazyString(str.upper, "hello\tworld").expandtabs() == "HELLO   WORLD"

    def test_find(self):
        assert LazyString(str.upper, "one two two").find("two") == -1
        assert LazyString(str.upper, "one two two").find("TWO") == 4

    def test_format(self):
        assert LazyString(str.upper, "hello {}").format("world") == "HELLO world"

    def test_index(self):
        with pytest.raises(ValueError, match="substring not found"):
            LazyString(str.upper, "hello world").index("world")
        assert LazyString(str.upper, "hello world").index("WORLD") == 6

    def test_isalnum(self):
        assert LazyString(str.upper, "h3llo").isalnum()
        assert not LazyString(str.upper, "h3llo world").isalnum()

    def test_isalpha(self):
        assert LazyString(str.upper, "hello").isalpha()
        assert not LazyString(str.upper, "h3llo").isalpha()

    @pytest.mark.skipif(
        sys.version_info < (3, 7), reason="requires python3.7 or higher"
    )
    def test_isascii(self):
        assert LazyString(str.upper, "hello").isascii()
        assert not LazyString(str.upper, "hεllo").isascii()

    def test_isdecimal(self):
        assert not LazyString(str.upper, "h").isdecimal()
        assert LazyString(str.upper, "1").isdecimal()
        assert not LazyString(str.upper, "²").isdecimal()

    def test_isdigit(self):
        assert not LazyString(str.upper, "h").isdigit()
        assert LazyString(str.upper, "1").isdigit()
        assert LazyString(str.upper, "²").isdigit()

    def test_isidentifier(self):
        assert LazyString(str.upper, "hello").isidentifier()
        assert LazyString(str.upper, "h3llo").isidentifier()
        assert not LazyString(str.upper, "3ello").isidentifier()
        assert not LazyString(str.upper, "hello world").isidentifier()

    def test_islower(self):
        assert not LazyString(str.upper, "hello world").islower()
        assert LazyString(str.lower, "HELLO WORLD").islower()

    def test_isnumeric(self):
        assert not LazyString(str.upper, "h").isnumeric()
        assert LazyString(str.upper, "1").isnumeric()
        assert LazyString(str.upper, "²").isnumeric()

    def test_isprintable(self):
        assert LazyString(str.upper, "hello world").isprintable()
        assert not LazyString(str.upper, "hello \b world").isprintable()

    def test_isspace(self):
        assert not LazyString(str.upper, "hello world").isspace()
        assert LazyString(str.upper, " ").isspace()

    def test_istitle(self):
        assert not LazyString(str.center, "Hello world", 20).istitle()
        assert LazyString(str.center, "Hello World", 20).istitle()

    def test_isupper(self):
        assert LazyString(str.upper, "hello world").isupper()
        assert not LazyString(str.lower, "HELLO WORLD").isupper()

    def test_join(self):
        assert (
            LazyString(str.upper, "aaa").join(["bbb", "ccc", "ddd"])
            == "bbbAAAcccAAAddd"
        )

    def test_ljust(self):
        assert LazyString(str.upper, "hello world").ljust(20) == "HELLO WORLD         "

    def test_lower(self):
        assert LazyString(str.upper, "hello world").lower() == "hello world"

    def test_lstrip(self):
        assert LazyString(str.upper, "  hello world  ").lstrip() == "HELLO WORLD  "

    def test_partition(self):
        assert LazyString(str.upper, "hello world").partition("l") == (
            "HELLO WORLD",
            "",
            "",
        )
        assert LazyString(str.upper, "hello world").partition("L") == (
            "HE",
            "L",
            "LO WORLD",
        )

    @pytest.mark.skipif(
        sys.version_info < (3, 9), reason="requires python3.9 or higher"
    )
    def test_removeprefix(self):
        assert LazyString(str.upper, "hello world").removeprefix("hel") == "HELLO WORLD"
        assert LazyString(str.upper, "hello world").removeprefix("HEL") == "LO WORLD"

    @pytest.mark.skipif(
        sys.version_info < (3, 9), reason="requires python3.9 or higher"
    )
    def test_removesuffix(self):
        assert LazyString(str.upper, "hello world").removesuffix("rld") == "HELLO WORLD"
        assert LazyString(str.upper, "hello world").removesuffix("RLD") == "HELLO WO"

    def test_replace(self):
        assert (
            LazyString(str.upper, "hello world").replace("world", "jim")
            == "HELLO WORLD"
        )
        assert (
            LazyString(str.upper, "hello world").replace("WORLD", "Jim") == "HELLO Jim"
        )

    def test_rfind(self):
        assert LazyString(str.upper, "one two two").rfind("two") == -1
        assert LazyString(str.upper, "one two two").rfind("TWO") == 8

    def test_rindex(self):
        with pytest.raises(ValueError, match="substring not found"):
            LazyString(str.upper, "one two two").rindex("two")
        assert LazyString(str.upper, "one two two").rindex("TWO") == 8

    def test_rjust(self):
        assert LazyString(str.upper, "hello world").rjust(20) == "         HELLO WORLD"

    def test_rpartition(self):
        assert LazyString(str.upper, "hello world").rpartition("l") == (
            "",
            "",
            "HELLO WORLD",
        )
        assert LazyString(str.upper, "hello world").rpartition("L") == (
            "HELLO WOR",
            "L",
            "D",
        )

    def test_split(self):
        assert LazyString(str.upper, "one two three").split(" ", 1) == [
            "ONE",
            "TWO THREE",
        ]

    def test_rsplit(self):
        assert LazyString(str.upper, "one two three").rsplit(" ", 1) == [
            "ONE TWO",
            "THREE",
        ]

    def test_rstrip(self):
        assert LazyString(str.upper, "  hello world  ").rstrip() == "  HELLO WORLD"

    def test_splitlines(self):
        assert LazyString(str.upper, "one\ntwo\nthree").splitlines() == [
            "ONE",
            "TWO",
            "THREE",
        ]

    def test_startswith(self):
        assert not LazyString(str.upper, "hello world").startswith("hello")
        assert LazyString(str.upper, "hello world").startswith("HELLO")

    def test_strip(self):
        assert LazyString(str.upper, "  hello world  ").strip() == "HELLO WORLD"

    def test_swapcase(self):
        assert LazyString(str.upper, "hello world").swapcase() == "hello world"
        assert LazyString(str.lower, "HELLO WORLD").swapcase() == "HELLO WORLD"

    def test_title(self):
        assert LazyString(str.upper, "hello world").title() == "Hello World"

    def test_translate(self):
        assert (
            LazyString(str.upper, "hello world").translate({ord("w"): ord("b")})
            == "HELLO WORLD"
        )
        assert (
            LazyString(str.upper, "hello world").translate({ord("W"): ord("B")})
            == "HELLO BORLD"
        )

    def test_upper(self):
        assert LazyString(str.lower, "HELLO WORLD").upper() == "HELLO WORLD"

    def test_zfill(self):
        assert LazyString(str.upper, "hello world").zfill(20) == "000000000HELLO WORLD"
