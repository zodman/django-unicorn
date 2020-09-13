import logging
from decimal import Decimal, InvalidOperation
from typing import Any, List, Tuple
from uuid import UUID

import orjson
from django.utils.dateparse import parse_datetime

from ast import literal_eval

from .errors import UnicornViewError


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_args(args: str) -> List[Any]:
    found_args = []
    arg = ""
    dict_count = 0
    list_count = 0
    tuple_count = 0

    def _eval_arg(_arg):
        try:
            evaled_arg = literal_eval(_arg)

            if isinstance(evaled_arg, float):
                _arg = Decimal(_arg)
            else:
                _arg = evaled_arg
        except SyntaxError:
            casters = [
                # lambda a: int(a),
                # lambda a: Decimal(a),
                lambda a: parse_datetime(a),
                lambda a: UUID(a),
            ]

            for caster in casters:
                try:
                    casted_value = caster(_arg)

                    if casted_value:
                        _arg = casted_value
                        break
                except ValueError:
                    pass
                except InvalidOperation:
                    pass

        return _arg

    def _parse_arg(_arg):
        if dict_count == 0 and list_count == 0 and tuple_count == 0:
            _arg = _eval_arg(_arg)
            found_args.append(_arg)
            # found_args.append(literal_eval(_arg))
            return ""

        return _arg

    for c in args:
        if not c.strip():
            continue

        if c == "," and dict_count == 0 and list_count == 0 and tuple_count == 0:
            if arg:
                arg = _eval_arg(arg)
                found_args.append(arg)
                arg = ""

                # arg_list = get_args(arg)
                # raise Exception("arg_list", arg_list)

                # if arg_list:
                #     found_args.extend(arg_list)
                # found_args.append(literal_eval(arg))

            continue
        # elif c == ",":
        #     if arg:
        #         arg = _eval_arg(arg)

        arg += c

        if c == "{":
            dict_count += 1
        elif c == "}":
            dict_count -= 1
            arg = _parse_arg(arg)
        elif c == "[":
            list_count += 1
        elif c == "]":
            list_count -= 1
            arg = _parse_arg(arg)
        elif c == "(":
            tuple_count += 1
        elif c == ")":
            tuple_count -= 1
            arg = _parse_arg(arg)

    if arg:
        arg = _eval_arg(arg)
        found_args.append(arg)
        # arg = ""

        # print("arg", arg)

        # if arg:
        #     arg = _eval_arg(arg)
        #     found_args.append(arg)
        #     # arg = ""

        # if arg:
        #     try:
        #         evaled_arg = literal_eval(arg)

        #         if isinstance(evaled_arg, float):
        #             arg = Decimal(arg)
        #         else:
        #             arg = evaled_arg
        #     except SyntaxError:
        #         casters = [
        #             # lambda a: int(a),
        #             # lambda a: Decimal(a),
        #             lambda a: parse_datetime(a),
        #             lambda a: UUID(a),
        #         ]

        #         for caster in casters:
        #             try:
        #                 casted_value = caster(arg)

        #                 if casted_value:
        #                     # raise Exception("got here", type(casted_value))
        #                     arg = casted_value
        #                     break
        #             except ValueError:
        #                 pass
        #             except InvalidOperation:
        #                 pass

        # if arg:
        #     found_args.append(arg)

    # raise Exception("found_args", found_args)

    # for a in found_args:

    #     # raise Exception("a", a, type(a))
    #     if isinstance(a, list):
    #         for b in a:
    #             if b
    #             raise Exception("b", b, type(b))

    return found_args


def parse_call_method_name(call_method_name: str) -> Tuple[str, List[Any]]:
    """
    Parses the method name from the request payload into a set of parameters to pass to a method.

    Args:
        param call_method_name: String representation of a method name with parameters, e.g. "set_name('Bob')"

    Returns:
        Tuple of method_name and a list of arguments.
    """

    method_name = call_method_name
    params: List[Any] = []

    if "(" in call_method_name and call_method_name.endswith(")"):
        param_idx = call_method_name.index("(")
        params_str = call_method_name[param_idx:]

        # Remove the arguments from the method name
        method_name = call_method_name.replace(params_str, "")

        # Remove parenthesis
        params_str = params_str[1:-1]

        if params_str == "":
            return (method_name, params)

        # Split up mutiple args
        # params = params_str.split(",")

        # for idx, arg in enumerate(params):
        #     params[idx] = handle_arg(arg)

        params = get_args(params_str)

        # params = handle_arg(params_str)

        # TODO: Handle kwargs

    return (method_name, params)


def handle_arg(arg: str) -> Any:
    """
    Clean up arguments. Try to convert arguments to the correct type.

    Currently supported types: str, int, decimal, list, tuple, dict, set, datetime (via parse_datetime: https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.dateparse.parse_datetime).

    Returns:
        Cleaned up argument.
    """

    def _parse_list(_arg):
        _arg = _arg[1:-1]
        val = []

        for a in _arg.split(","):
            val.append(handle_arg(a.strip()))

        return val

    if (arg.startswith("'") and arg.endswith("'")) or (
        arg.startswith('"') and arg.endswith('"')
    ):
        return arg[1:-1]

    if arg.startswith("[") and arg.endswith("]"):
        return _parse_list(arg)

    if arg.startswith("(") and arg.endswith(")"):
        return tuple(_parse_list(arg))

    # Attempt to handle dictionaries and sets
    if arg.startswith("{") and arg.endswith("}"):
        try:
            val = orjson.loads(arg)
            return val
        except orjson.JSONDecodeError as json_error:
            logger.debug(f"JSONDecodeError while parsing: '{arg}'", exc_info=True)

            try:
                arg_pieces = arg[1:-1].split(",")
                parsed_arg = "{"

                for arg_piece in arg_pieces:
                    key_value = arg_piece.split(":")

                    # Assumes that keys will be strings
                    key = key_value[0]

                    value = arg_piece.replace(f"{key}:", "").strip()

                    if value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                        value = f'"{value}"'
                    else:
                        value = handle_arg(value)

                        # Handle nested dictionaries
                        if isinstance(value, dict):
                            stringified_dict = "{"

                            for k, v in value.items():
                                stringified_dict += f'"{k}":{v}'

                            value = stringified_dict + "}"

                    key = key.strip()

                    if key.startswith("'") and key.endswith("'"):
                        key = key[1:-1]
                        key = f'"{key}"'
                    else:
                        # TODO: Handle non-string keys
                        pass

                    parsed_arg = f"{parsed_arg}{key}:{value},"

                parsed_arg = parsed_arg[:-1]
                parsed_arg += "}"

                val = orjson.loads(parsed_arg)
                return val
            except Exception as e:
                logger.debug(
                    f"Exception while parsing single quotes for: '{arg}'", exc_info=True
                )

                try:
                    set_arg = _parse_list(arg)
                    return set(set_arg)
                except Exception as e:
                    logger.debug(e)

                    raise UnicornViewError(
                        f"Invalid dict method argument. Could not parse: {arg}"
                    ) from json_error

    casters = [
        lambda a: int(a),
        lambda a: Decimal(a),
        lambda a: parse_datetime(a),
        lambda a: UUID(a),
    ]

    for caster in casters:
        try:
            casted_value = caster(arg)

            if casted_value:
                return casted_value
        except ValueError:
            pass
        except InvalidOperation:
            pass

    raise UnicornViewError(f"Invalid method argument. Could not parse: '{arg}'")
