import hmac
import logging
from functools import wraps
from typing import Any, Dict, List, Union

import orjson
import shortuuid
from django.conf import settings
from django.db.models import Model
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .components import UnicornField, UnicornView
from .errors import UnicornViewError
from .call_method_parser import handle_arg, parse_call_method_name


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def handle_error(view_func):
    def wrapped_view(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except UnicornViewError as e:
            return JsonResponse({"error": str(e)})
        except AssertionError as e:
            return JsonResponse({"error": str(e)})

    return wraps(view_func)(wrapped_view)


def _set_property_from_data(
    component_or_field: Union[UnicornView, UnicornField, Model], name: str, value,
) -> None:
    """
    Sets properties on the component based on passed-in data.
    """

    if hasattr(component_or_field, name):
        field = getattr(component_or_field, name)

        # UnicornField and Models are always a dictionary (can be nested)
        if isinstance(field, UnicornField) or isinstance(field, Model):
            for key in value.keys():
                key_value = value[key]
                _set_property_from_data(field, key, key_value)
        else:
            if hasattr(component_or_field, "_set_property"):
                # Can assume that `component_or_field` is a component
                component_or_field._set_property(name, value)
            else:
                setattr(component_or_field, name, value)


def _set_property_from_payload(
    component: UnicornView, payload: Dict, data: Dict
) -> None:
    """
    Sets properties on the component based on the payload.
    Also updates the data dictionary which gets set back as part of the payload.

    Args:
        param component: Component to set attributes on.
        param payload: Dictionary that comes with request.
        param data: Dictionary that gets sent back with the response.
    """

    property_name = payload.get("name")
    property_value = payload.get("value")
    component.updating(property_name, property_value)

    if property_name is not None and property_value is not None:
        """
        Handles nested properties. For example, for the following component:

        class Author(UnicornField):
            name = "Neil"

        class TestView(UnicornView):
            author = Author()
        
        `payload` would equal `{'name': 'author.name', 'value': 'Neil Gaiman'}`

        The following code updates UnicornView.author.name based the payload's `author.name`.
        """
        property_name_parts = property_name.split(".")
        component_or_field = component
        data_or_dict = data  # Could be an internal portion of data that gets set

        for (idx, property_name_part) in enumerate(property_name_parts):
            if hasattr(component_or_field, property_name_part):
                if idx == len(property_name_parts) - 1:
                    if hasattr(component_or_field, "_set_property"):
                        # Can assume that `component_or_field` is a component
                        component_or_field._set_property(
                            property_name_part, property_value
                        )
                    else:
                        # Handle calling the updating/updated method for nested properties
                        property_name_snake_case = property_name.replace(".", "_")
                        updating_function_name = f"updating_{property_name_snake_case}"
                        updated_function_name = f"updated_{property_name_snake_case}"

                        if hasattr(component, updating_function_name):
                            getattr(component, updating_function_name)(property_value)

                        setattr(component_or_field, property_name_part, property_value)

                        if hasattr(component, updated_function_name):
                            getattr(component, updated_function_name)(property_value)

                    data_or_dict[property_name_part] = property_value
                else:
                    component_or_field = getattr(component_or_field, property_name_part)
                    data_or_dict = data_or_dict.get(property_name_part, {})
            elif isinstance(component_or_field, dict):
                if idx == len(property_name_parts) - 1:
                    component_or_field[property_name_part] = property_value
                    data_or_dict[property_name_part] = property_value
                else:
                    component_or_field = component_or_field[property_name_part]
                    data_or_dict = data_or_dict.get(property_name_part, {})

    component.updated(property_name, property_value)


# def _parse_call_method_name(call_method_name: str) -> Tuple[str, List[Any]]:
#     """
#     Parses the method name from the request payload into a set of parameters to pass to a method.

#     Args:
#         param call_method_name: String representation of a method name with parameters, e.g. "set_name('Bob')"

#     Returns:
#         Tuple of method_name and a list of arguments.
#     """

#     method_name = call_method_name
#     params: List[Any] = []

#     if "(" in call_method_name and call_method_name.endswith(")"):
#         param_idx = call_method_name.index("(")
#         params_str = call_method_name[param_idx:]

#         # Remove the arguments from the method name
#         method_name = call_method_name.replace(params_str, "")

#         # Remove parenthesis
#         params_str = params_str[1:-1]

#         if params_str == "":
#             return (method_name, params)

#         # Split up mutiple args
#         # params = params_str.split(",")

#         # for idx, arg in enumerate(params):
#         #     params[idx] = _handle_arg(arg)

#         params = _handle_arg(params_str)

#         # TODO: Handle kwargs

#     return (method_name, params)


# def _handle_arg(arg: str) -> Any:
#     """
#     Clean up arguments. Try to convert arguments to the correct type.

#     Currently supported types: str, int, decimal, list, tuple, dict, set, datetime (via parse_datetime: https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.dateparse.parse_datetime).

#     Returns:
#         Cleaned up argument.
#     """

#     def _parse_list(_arg):
#         _arg = _arg[1:-1]
#         val = []

#         for a in _arg.split(","):
#             val.append(_handle_arg(a.strip()))

#         return val

#     if (arg.startswith("'") and arg.endswith("'")) or (
#         arg.startswith('"') and arg.endswith('"')
#     ):
#         return arg[1:-1]

#     if arg.startswith("[") and arg.endswith("]"):
#         return _parse_list(arg)

#     if arg.startswith("(") and arg.endswith(")"):
#         return tuple(_parse_list(arg))

#     # Attempt to handle dictionaries and sets
#     if arg.startswith("{") and arg.endswith("}"):
#         try:
#             val = orjson.loads(arg)
#             return val
#         except orjson.JSONDecodeError as json_error:
#             logger.debug(f"JSONDecodeError while parsing: '{arg}'", exc_info=True)

#             try:
#                 arg_pieces = arg[1:-1].split(",")
#                 parsed_arg = "{"

#                 for arg_piece in arg_pieces:
#                     key_value = arg_piece.split(":")

#                     # Assumes that keys will be strings
#                     key = key_value[0]

#                     value = arg_piece.replace(f"{key}:", "").strip()

#                     if value.startswith("'") and value.endswith("'"):
#                         value = value[1:-1]
#                         value = f'"{value}"'
#                     else:
#                         value = _handle_arg(value)

#                         # Handle nested dictionaries
#                         if isinstance(value, dict):
#                             stringified_dict = "{"

#                             for k, v in value.items():
#                                 stringified_dict += f'"{k}":{v}'

#                             value = stringified_dict + "}"

#                     key = key.strip()

#                     if key.startswith("'") and key.endswith("'"):
#                         key = key[1:-1]
#                         key = f'"{key}"'
#                     else:
#                         # TODO: Handle non-string keys
#                         pass

#                     parsed_arg = f"{parsed_arg}{key}:{value},"

#                 parsed_arg = parsed_arg[:-1]
#                 parsed_arg += "}"

#                 val = orjson.loads(parsed_arg)
#                 return val
#             except Exception as e:
#                 logger.debug(
#                     f"Exception while parsing single quotes for: '{arg}'", exc_info=True
#                 )

#                 try:
#                     set_arg = _parse_list(arg)
#                     return set(set_arg)
#                 except Exception as e:
#                     logger.debug(e)

#                     raise UnicornViewError(
#                         f"Invalid dict method argument. Could not parse: {arg}"
#                     ) from json_error

#     from uuid import UUID

#     casters = [
#         lambda a: int(a),
#         lambda a: Decimal(a),
#         lambda a: parse_datetime(a),
#         lambda a: UUID(a),
#     ]

#     for caster in casters:
#         try:
#             casted_value = caster(arg)

#             if casted_value:
#                 return casted_value
#         except ValueError:
#             pass
#         except InvalidOperation:
#             pass

#     raise UnicornViewError(f"Invalid method argument. Could not parse: '{arg}'")


def _call_method_name(
    component: UnicornView, method_name: str, params: List[Any]
) -> None:
    """
    Calls the method name with parameters.
    Also updates the data dictionary which gets set back as part of the payload.

    Args:
        param component: Component to call method on.
        param method_name: Method name to call.
        param params: List of arguments for the method.
    """

    if method_name is not None and hasattr(component, method_name):
        func = getattr(component, method_name)

        if params:
            func(*params)
        else:
            func()


class ComponentRequest:
    """
    Parses, validates, and stores all of the data from the message request.
    """

    def __init__(self, request):
        self.body = {}

        try:
            self.body = orjson.loads(request.body)
            assert self.body, "Invalid JSON body"
        except orjson.JSONDecodeError as e:
            raise UnicornViewError("Body could not be parsed") from e

        self.data = self.body.get("data")
        assert self.data is not None, "Missing data"  # data could theoretically be {}

        self.id = self.body.get("id")
        assert self.id, "Missing component id"

        self.validate_checksum()

        self.action_queue = self.body.get("actionQueue", [])

    def validate_checksum(self):
        """
        Validates that the checksum in the request matches the data.

        Returns:
            Raises `AssertionError` if the checksums don't match.
        """
        checksum = self.body.get("checksum")
        assert checksum, "Missing checksum"

        generated_checksum = hmac.new(
            str.encode(settings.SECRET_KEY),
            orjson.dumps(self.data),
            digestmod="sha256",
        ).hexdigest()
        generated_checksum = shortuuid.uuid(generated_checksum)[:8]
        assert checksum == generated_checksum, "Checksum does not match"


@handle_error
@csrf_protect
@require_POST
def message(request: HttpRequest, component_name: str = None) -> JsonResponse:
    """
    Endpoint that instantiates the component and does the correct action
    (set an attribute or call a method) depending on the JSON payload in the body.

    Args:
        param request: HttpRequest for the function-based view.
        param: component_name: Name of the component, e.g. "hello-world".
    
    Returns:
        JSON with the following structure:
        {
            "id": component_id,
            "dom": html,  // re-rendered version of the component after actions in the payload are completed
            "data": {},  // updated data after actions in the payload are completed
        }
    """

    assert component_name, "Missing component name in url"

    component_request = ComponentRequest(request)
    component = UnicornView.create(
        component_id=component_request.id, component_name=component_name
    )
    validate_all_fields = False

    # Get a copy of the data passed in to determine what fields are updated later
    original_data = component_request.data.copy()

    # Set component properties based on request data
    for (name, value) in component_request.data.items():
        _set_property_from_data(component, name, value)
    component.hydrate()

    is_reset_called = False

    for action in component_request.action_queue:
        action_type = action.get("type")
        payload = action.get("payload", {})

        if action_type == "syncInput":
            _set_property_from_payload(component, payload, component_request.data)
        elif action_type == "callMethod":
            call_method_name = payload.get("name", "")
            assert call_method_name, "Missing 'name' key for callMethod"

            if call_method_name == "reset" or call_method_name == "reset()":
                # Handle the reset special action
                component = UnicornView.create(
                    component_id=component_request.id,
                    component_name=component_name,
                    use_cache=False,
                )

                #  Explicitly remove all errors and prevent validation from firing before render()
                component.errors = {}
                is_reset_called = True
            elif call_method_name == "refresh" or call_method_name == "refresh()":
                # Handle the refresh special action
                component = UnicornView.create(
                    component_id=component_request.id,
                    component_name=component_name,
                    use_cache=True,
                )
            elif call_method_name == "validate" or call_method_name == "validate()":
                # Handle the validate special action
                validate_all_fields = True
            elif "=" in call_method_name:
                call_method_name_split = call_method_name.split("=")
                property_name = call_method_name_split[0]
                property_value = handle_arg(call_method_name_split[1])

                if hasattr(component, property_name):
                    component.calling(f"set_{property_name}", property_value)
                    setattr(component, property_name, property_value)
                    component.called(f"set_{property_name}", property_value)
                    component_request.data[property_name] = property_value
            else:
                (method_name, params) = parse_call_method_name(call_method_name)
                component.calling(method_name, params)
                _call_method_name(component, method_name, params)
                component.called(method_name, params)
        else:
            raise UnicornViewError(f"Unknown action_type '{action_type}'")

    # Re-load frontend context variables to deal with non-serializable properties
    component_request.data = orjson.loads(component.get_frontend_context_variables())

    if not is_reset_called:
        if validate_all_fields:
            component.validate()
        else:
            model_names_to_validate = []

            for key, value in original_data.items():
                if value != component_request.data[key]:
                    model_names_to_validate.append(key)

            component.validate(model_names=model_names_to_validate)

    rendered_component = component.render()

    res = {
        "id": component_request.id,
        "dom": rendered_component,
        "data": component_request.data,
        "errors": component.errors,
    }

    return JsonResponse(res)
