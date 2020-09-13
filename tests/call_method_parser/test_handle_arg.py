from datetime import datetime
from decimal import Decimal

import pytest

from django_unicorn.call_method_parser import handle_arg
from django_unicorn.errors import UnicornViewError


def test_double_quotes():
    expected = "1"
    actual = handle_arg("'1'")

    assert actual == expected


def test_single_quotes():
    expected = "1"
    actual = handle_arg('"1"')

    assert actual == expected


def test_int():
    expected = 1
    actual = handle_arg("1")

    assert actual == expected


def test_list():
    expected = [1, 2, 3]
    actual = handle_arg("[1,2,3]")

    assert actual == expected


def test_list_with_mixed_types():
    expected = ["1", 2, 3]
    actual = handle_arg("['1',2,3]")

    assert actual == expected


def test_list_with_mixed_types_with_spaces():
    expected = ["1", "2", 3]
    actual = handle_arg("['1', \"2\", 3]")

    assert actual == expected


def test_tuple():
    expected = (1, 2, 3)
    actual = handle_arg("(1,2,3)")

    assert actual == expected


def test_dictionary():
    expected = {"1": "1", "2": "2"}
    actual = handle_arg('{"1": "1", "2": "2"}')

    assert actual == expected


@pytest.mark.skip("Non-string keys aren't handled")
def test_dictionary_with_non_string_keys():
    expected = {1: "1", 2: 2}
    actual = handle_arg('{1: "1", 2: 2}')

    assert actual == expected


def test_nested_dictionary():
    expected = {"name": 1, "nested": {"name": 2}}
    actual = handle_arg('{"name": 1, "nested": {"name": 2}}')

    assert actual == expected


def test_nested_dictionary_with_single_quotes():
    expected = {"name": 1, "nested": {"name": 2}}
    actual = handle_arg("{'name': 1, 'nested': {'name': 2}}")

    assert actual == expected


def test_dictionary_single_quotes():
    expected = {"1": "1", "2": "2"}
    actual = handle_arg("{'1': '1', '2': '2'}")

    assert actual == expected


def test_set():
    expected = set({1, 2})
    actual = handle_arg("{1, 2}")

    assert actual == expected


def test_set_with_string():
    expected = set({1, "2"})
    actual = handle_arg('{1, "2"}')

    assert actual == expected


def test_decimal():
    expected = Decimal("1.24")
    actual = handle_arg("1.24")

    assert actual == expected


def test_datetime():
    expected = datetime(2016, 10, 3, 19, 1, 0)
    actual = handle_arg("2016-10-03T19:01:00")

    assert actual == expected


def test_invalid_datetime_error_raised():
    with pytest.raises(UnicornViewError) as e:
        handle_arg("2016-10-03T19:01asd")

    assert "Invalid method argument" in e.exconly()


def test_invalid_dict_error_raised():
    with pytest.raises(UnicornViewError) as e:
        handle_arg("{-}")

    assert "Invalid dict method argument" in e.exconly()
