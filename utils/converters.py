import base64
import io
import re
from decimal import Decimal
from itertools import chain
from typing import List, Dict, Union

from django.db import models
from django.db.models import QuerySet

from utils.constants.environment_variables import EXTENSION_MAPPER


class ModelConverter:
    @staticmethod
    def _get_new_field_name(fields: List, name: str) -> str:
        new_name = name.replace("__", "_")
        if new_name not in fields:
            name = new_name
        return name

    @staticmethod
    def model_to_dict(
        instance: models.Model,
        fields: List = None,
        exclude: List = None,
        detailed_fields: Dict[str, Dict[str, Union[List, Dict]]] = None,
        fields_as: Dict[str, str] = None,
    ) -> Dict:
        """
        Returns desired dict of the model instance
        Foreign key fields can be passed in detailed list when detailed information is needed
        otherwise the dict only returns the id of the field
        IMPORTANT: Using detailed fields will affect performance since it causes database hits
                   Related name fields should be explicitly added to fields to be fetched and returned
                   i.e. book has one_to_many rel to book_progresses. Add fields=['progresses']
                   to see progresses listed in results
        """

        def get_reflected_name(field_name: str):
            return fields_as.get(field_name, field_name) if fields_as else field_name

        if instance is None:
            return {}
        opts = instance._meta
        data = {}
        fields = (
            fields + list(detailed_fields.keys())
            if isinstance(detailed_fields, dict) and isinstance(fields, List)
            else fields
        )
        for f in chain(opts.concrete_fields, opts.private_fields):
            if fields and f.name not in fields:
                continue
            if exclude and f.name in exclude:
                continue
            if (
                isinstance(f, models.ForeignKey)
                and detailed_fields
                and f.name in detailed_fields.keys()
            ):
                data[get_reflected_name(f.name)] = ModelConverter.model_to_dict(
                    instance.__getattribute__(f.name), **detailed_fields[f.name]
                )
            else:
                data[get_reflected_name(f.name)] = f.value_from_object(instance)
        for f in opts.many_to_many:
            if fields and f.name not in fields:
                continue
            if exclude and f.name in exclude:
                continue
            if detailed_fields and f.name in detailed_fields.keys():
                data[get_reflected_name(f.name)] = [
                    ModelConverter.model_to_dict(i)
                    for i in f.value_from_object(instance)
                ]
            else:
                data[get_reflected_name(f.name)] = [
                    i.id for i in f.value_from_object(instance)
                ]
        for f in opts.related_objects:
            if fields is None or f.name not in fields:
                continue
            if exclude and f.name in exclude:
                continue

            if detailed_fields and f.name in detailed_fields.keys():
                data[get_reflected_name(f.name)] = [
                    ModelConverter.model_to_dict(i, **detailed_fields[f.name])
                    for i in instance.__getattribute__(f.name).all()
                ]
            else:
                data[get_reflected_name(f.name)] = [
                    i.id for i in instance.__getattribute__(f.name).all()
                ]
        return data

    @staticmethod
    def model_queryset_to_dict_queryset(
        queryset: QuerySet, fields: List = None, exclude: List = None
    ) -> List[Dict]:
        if queryset is None:
            return []
        opts = queryset.model._meta
        if fields is None:
            fields = list(
                map(lambda x: x.name, chain(opts.concrete_fields, opts.private_fields))
            )
        if exclude is not None:
            fields = [field for field in fields if field not in exclude]
        return queryset.values(*fields)

    @staticmethod
    def model_list_to_nosql_dict_with_desired_key_field(
        queryset: List[models.Model], desired_key: str = "id"
    ) -> Dict[any, Dict]:
        """
        Returns a nosql type dict of model in which the key is a selected field of model
        If two of the same key exist, it is overriden
        """
        if queryset is None:
            return {}
        result = {}
        for model in queryset:
            model_dict = ModelConverter.model_to_dict(model)
            result[model_dict[desired_key]] = model_dict

        return result

    @staticmethod
    def model_list_to_nosql_with_desired_key_field(
        queryset: List[models.Model], desired_key: str = "id"
    ) -> Dict[any, models.Model]:
        """
        Returns a nosql type dict of model in which the key is a selected field of model
        If two of the same key exist, it is overriden
        """
        if queryset is None:
            return {}
        result = {}
        for model in queryset:
            result[getattr(model, desired_key)] = model

        return result


class FileConverter:
    @staticmethod
    def ImageBase64ToBytes(image_data: str) -> (bytes, str):
        file_format, encoded_image = image_data.split(";base64,")  # remove prefix
        file_extension = file_format.split("/")[-1]
        ext = EXTENSION_MAPPER.get(file_extension, None)
        ext = ext if ext is not None else file_extension
        image_bytes = base64.b64decode(encoded_image)

        image_file = io.BytesIO(image_bytes)
        return image_file, ext


class ValueConverter:
    @staticmethod
    def str2bool(v: str, empty_is_true: bool = False) -> bool:
        """
        Convert string to boolean. Any form of yes, y, true, t, 1 are accepted as true
        :param v: String to convert to bool
        :param empty_is_true: Bool value to indicate if empty string will be converter to true
        :return: Boolean form of the input
        """
        return v.lower() in ("yes", "y", "true", "t", "1") or (
            empty_is_true and v == ""
        )

    @staticmethod
    def safeStr2Decimal(v: str) -> Decimal:
        pattern = r"[^\d,\.]"
        cleaned_string = re.sub(pattern, "", v).replace(",", ".")
        return Decimal(cleaned_string)

    @staticmethod
    def micros2decimal(v: int, max_decimal_places: int = 2):
        v = v / 1000000
        decimal_value = Decimal(str(v))
        decimal_value = decimal_value.quantize(Decimal(10) ** -max_decimal_places)
        return decimal_value
