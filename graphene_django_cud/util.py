from collections import OrderedDict

from django.db import models
from graphene_django.registry import get_global_registry
from graphene_django.utils import get_model_fields
from graphql import GraphQLError
from graphql_relay import from_global_id
from typing import Union

from graphene_django_cud.converter import convert_django_field_with_choices, convert_many_to_many_field
from graphene_django_cud.registry import get_input_registry


def disambiguate_id(ambiguous_id: Union[int, float, str]):
    """
    disambiguate_id takes an id which may either be an integer-parsable
    variable, either as a string or a number; or it might be a base64 encoded
    global relay value.

    The method then attempts to extract from this token the actual id.

    :return:
    """
    # First see if it is an integer, if so
    # it is definitely not a relay global id
    final_id = -1
    try:
        final_id = int(ambiguous_id)
        return final_id
    except ValueError:
        # Try global value
        (_, final_id) = from_global_id(ambiguous_id)
    finally:
        return final_id


def disambiguate_ids(ids):
    if not hasattr(ids, "__iter__"):
        return [disambiguate_id(ids)]
    return [disambiguate_id(_id) for _id in ids]


def overload_nested_fields(nested_fields):
    if nested_fields is None:
        return {}
    elif isinstance(nested_fields, dict):
        return nested_fields
    elif hasattr(nested_fields, "__iter__"):
        result = {}
        for el in nested_fields:
            # Should be a string
            if not isinstance(el, str):
                raise ValueError(
                    f"Nested field iterable entry has to be a string. Got {type(el)}"
                )

            result[el] = ["all"]
        return result
    else:
        return {}


def get_input_fields_for_model(
    model,
    only_fields,
    exclude_fields,
    optional_fields=(),
    required_fields=(),
    many_to_many_extras=None,
    foreign_key_extras=None
) -> OrderedDict:

    registry = get_global_registry()
    model_fields = get_model_fields(model)

    many_to_many_extras = many_to_many_extras or {}
    foreign_key_extras = foreign_key_extras or {}

    fields = OrderedDict()
    fields_lookup = {}
    for name, field in model_fields:
        # We ignore the primary key
        if getattr(field, "primary_key", False):
            continue

        # Save for later
        fields_lookup[name] = field

        is_not_in_only = only_fields and name not in only_fields
        # is_already_created = name in options.fields
        is_excluded = name in exclude_fields  # or is_already_created
        # https://docs.djangoproject.com/en/1.10/ref/models/fields/#django.db.models.ForeignKey.related_query_name
        is_no_backref = str(name).endswith("+")
        if is_not_in_only or is_excluded or is_no_backref:
            # We skip this field if we specify only_fields and is not
            # in there. Or when we exclude this field in exclude_fields.
            # Or when there is no back reference.
            continue

        required = None
        if name in optional_fields:
            required = False
        elif name in required_fields:
            required = True

        converted = convert_django_field_with_choices(
            field,
            registry,
            required,
            many_to_many_extras.get(name, {}).get('exact'),
            foreign_key_extras.get(name, {})
        )
        fields[name] = converted

    # Create extra many_to_many_fields
    for name, extras in many_to_many_extras.items():
        field = fields_lookup.get(name)
        if field is None:
            raise GraphQLError(f"Error adding extras for {name} in model f{model}. Field {name} does not exist.")

        for extra_name, data in extras.items():

            # This is handled above
            if extra_name == "exact":
                continue

            if isinstance(data, bool):
                data = {}

            _type_name = data.get('type')
            _field = convert_many_to_many_field(
                field,
                registry,
                False,
                data,
                None
            )

            # Default to the same as the "exact" version
            if not _field:
                _field = fields[name]

            # operation = data.get('operation') or get_likely_operation_from_name(extra_name)
            fields[name + "_" + extra_name] = _field

    return fields


def get_all_optional_input_fields_for_model(
        model,
        only_fields,
        exclude_fields,
        many_to_many_extras=None,
        foreign_key_extras=None
):
    registry = get_global_registry()
    model_fields = get_model_fields(model)

    many_to_many_extras = many_to_many_extras or {}
    foreign_key_extras = foreign_key_extras or {}

    fields = OrderedDict()
    fields_lookup = {}
    for name, field in model_fields:
        # We ignore the primary key
        if getattr(field, "primary_key", False):
            continue

        # Save for later
        fields_lookup[name] = field

        is_not_in_only = only_fields and name not in only_fields
        # is_already_created = name in options.fields
        is_excluded = name in exclude_fields  # or is_already_created
        # https://docs.djangoproject.com/en/1.10/ref/models/fields/#django.db.models.ForeignKey.related_query_name
        is_no_backref = str(name).endswith("+")
        if is_not_in_only or is_excluded or is_no_backref:
            # We skip this field if we specify only_fields and is not
            # in there. Or when we exclude this field in exclude_fields.
            # Or when there is no back reference.
            continue

        converted = convert_django_field_with_choices(
            field,
            registry,
            False,
            many_to_many_extras.get(name, {}).get('exact'),
            foreign_key_extras.get(name, {})
        )

        fields[name] = converted

    # Create extra many_to_many_fields
    for name, extras in many_to_many_extras.items():
        field = fields_lookup.get(name)
        if field is None:
            raise GraphQLError(f"Error adding extras for {name} in model f{model}. Field {name} does not exist.")

        for extra_name, data in extras.items():

            # This is handled above
            if extra_name == "exact":
                continue

            if isinstance(data, bool):
                data = {}

            _type_name = data.get('type')
            _field = convert_many_to_many_field(
                field,
                registry,
                False,
                data,
                None
            )

            # Default to the same as the "exact" version
            if not _field:
                _field = fields[name]

            # operation = data.get('operation') or get_likely_operation_from_name(extra_name)
            fields[name + "_" + extra_name] = _field

    return fields



def get_likely_operation_from_name(extra_name):
    extra_name = extra_name.lower()
    if extra_name == "update" or extra_name == "patch":
        return "update"

    if extra_name == "add" or extra_name == "append" or extra_name == "exact":
        return "add"

    if extra_name == "delete" or extra_name == "remove":
        return "remove"

    raise GraphQLError(f"Unknown extra operation {extra_name}")



def _validate_create_many_to_many_extras(extras):
    pass


def _validate_update_many_to_many_extras(extras):
    pass


def validate_many_to_many_extras(extras, operation_type):
    pass


def _validate_create_foreign_key_extras(extras):
    pass


def _validate_update_foreign_key_extras(extras):
    pass


def validate_foreign_key_extras(extras, operation_type):
    pass


def is_many_to_many(field):
    return type(field) in (
        models.ManyToManyField,
        models.ManyToManyRel,
        models.ManyToOneRel
    )

def get_m2m_all_extras_field_names(extras):
    res = []
    if not extras:
        return []
    for name, extra in extras.items():
        for extra_name, _ in extra.items():
            if extra_name != "exact":
                res.append(name + "_" + extra_name)
            else:
                res.append(name)

    return res


def get_fk_all_extras_field_names(extras):
    res = []
    if not extras:
        return []
    return extras.keys()