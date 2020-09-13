from unittest.case import expectedFailure
from django_unicorn.call_method_parser import get_args


def test_args():
    expected = [1, 2]
    actual = get_args("1, 2")

    assert actual == expected


def test_single_quote_args():
    expected = ["1"]
    actual = get_args("'1'")

    assert actual == expected


def test_doublee_quote_args():
    expected = ["1"]
    actual = get_args('"1"')

    assert actual == expected


def test_args_with_single_quote_dict():
    expected = [1, {"2": 3}]
    actual = get_args("1, {'2': 3}")

    assert actual == expected


def test_args_with_double_quote_dict():
    expected = [1, {"2": 3}]
    actual = get_args("1, {'2': 3}")

    assert actual == expected


def test_args_with_nested_dict():
    expected = [1, {"2": {"3": 4}}]
    actual = get_args("1, {'2': { '3': 4 }}")

    assert actual == expected


def test_args_with_nested_list():
    expected = [[1, ["2", "3"], 4], 9]
    actual = get_args("[1, ['2', '3'], 4], 9")

    assert actual == expected


def test_args_with_nested_tuple():
    expected = [9, (1, ("2", "3"), 4)]
    actual = get_args("9, (1, ('2', '3'), 4)")

    assert actual == expected


def test_args_with_nested_objects():
    expected = [[0, 1], {"2": {"3": 4}}, (5, 6, [7, 8])]
    actual = get_args("[0,1], {'2': { '3': 4 }}, (5, 6, [7, 8])")

    assert actual == expected


def test_list_args():
    expected = [1, [2, "3"]]
    actual = get_args("1, [2, '3']")

    assert actual == expected


from datetime import datetime


def test_datetime():
    expected = [datetime(2020, 9, 12, 1, 1, 1)]
    actual = get_args("2020-09-12T01:01:01")

    assert actual == expected


from uuid import UUID


def test_uuid():
    expected = [UUID("90144cb9-fc47-476d-b124-d543b0cff091")]
    actual = get_args("90144cb9-fc47-476d-b124-d543b0cff091")

    assert actual == expected


from decimal import Decimal


def test_decimal():
    # expected = [Decimal("2.11"), [1, Decimal("5.4"), ("asdf", Decimal("9.12"))]]
    # actual = get_args("2.11, [1, 5.4], ('asdf', 9.12)")

    expected = [[1, Decimal("5.4")]]
    actual = get_args("[1, 5.4]")

    # expected = [Decimal("2.11")]
    # actual = get_args("2.11")

    assert actual == expected
