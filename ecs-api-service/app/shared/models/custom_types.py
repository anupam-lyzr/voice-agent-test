# In app/shared/models/custom_types.py

from bson import ObjectId
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

class PyObjectId(ObjectId):
    """
    Custom Pydantic type for MongoDB's ObjectId, compatible with Pydantic v2.
    """
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: any, handler: any
    ) -> CoreSchema:
        """
        Return a Pydantic CoreSchema that defines how to validate and serialize the ObjectId.
        """
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [
                            core_schema.str_schema(),
                            core_schema.no_info_plain_validator_function(cls.validate),
                        ]
                    ),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: str(instance)
            ),
        )

    @classmethod
    def validate(cls, value: str) -> ObjectId:
        """Validate that the given string is a valid ObjectId."""
        if not ObjectId.is_valid(value):
            raise ValueError(f"Invalid ObjectId: {value}")
        return ObjectId(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """
        Modify the JSON schema to represent the ObjectId as a string.
        """
        return handler(core_schema.json_schema)