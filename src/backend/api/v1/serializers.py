from drf_spectacular.utils import extend_schema_field
from rest_framework_json_api import serializers
from rest_framework_json_api.serializers import ValidationError

from api.models import StateChoices, Provider, Scan
from api.rls import Tenant
from api.utils import merge_dicts


# Base


class BaseSerializerV1(serializers.ModelSerializer):
    def get_root_meta(self, _resource, _many):
        return {"version": "v1"}


class BaseWriteSerializer(BaseSerializerV1):
    def validate(self, data):
        if hasattr(self, "initial_data"):
            initial_data = set(self.initial_data.keys()) - {"id", "type"}
            unknown_keys = initial_data - set(self.fields.keys())
            if unknown_keys:
                raise ValidationError(f"Invalid fields: {unknown_keys}")
        return data


class RLSSerializer(BaseSerializerV1):
    def create(self, validated_data):
        tenant_id = self.context.get("tenant_id")
        validated_data["tenant_id"] = tenant_id
        return super().create(validated_data)


class StateEnumSerializerField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        kwargs["choices"] = StateChoices.choices
        super().__init__(**kwargs)


# Tasks


class DelayedTaskSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.CharField()

    class JSONAPIMeta:
        resource_name = "Task"

    def to_representation(self, obj):
        return {"id": obj.id, "status": obj.status}


# Tenants


class TenantSerializer(BaseSerializerV1):
    """
    Serializer for the Tenant model.
    """

    class Meta:
        model = Tenant
        fields = "__all__"


# Providers
class ProviderEnumSerializerField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        kwargs["choices"] = Provider.ProviderChoices.choices
        super().__init__(**kwargs)


class ProviderSerializer(RLSSerializer):
    """
    Serializer for the Provider model.
    """

    provider = ProviderEnumSerializerField()
    connection = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Provider
        fields = [
            "id",
            "inserted_at",
            "updated_at",
            "provider",
            "provider_id",
            "alias",
            "connection",
            "scanner_args",
            "url",
        ]

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "connected": {"type": "boolean"},
                "last_checked_at": {"type": "string", "format": "date-time"},
            },
        }
    )
    def get_connection(self, obj):
        return {
            "connected": obj.connected,
            "last_checked_at": obj.connection_last_checked_at,
        }


class ProviderCreateSerializer(RLSSerializer, BaseWriteSerializer):
    class Meta:
        model = Provider
        fields = ["alias", "provider", "provider_id", "scanner_args"]


class ProviderUpdateSerializer(BaseWriteSerializer):
    """
    Serializer for updating the Provider model.
    Only allows "alias" and "scanner_args" fields to be updated.
    """

    class Meta:
        model = Provider
        fields = ["alias", "scanner_args"]


# Scans


class ScanTypeEnumSerializerField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        kwargs["choices"] = Scan.TypeChoices.choices
        super().__init__(**kwargs)


class ScanSerializer(RLSSerializer):
    type_ = serializers.ChoiceField(choices=Scan.TypeChoices.choices, read_only=True)
    state = StateEnumSerializerField(read_only=True)

    class Meta:
        model = Scan
        fields = [
            "id",
            "name",
            "type_",
            "state",
            "unique_resource_count",
            "progress",
            "scanner_args",
            "duration",
            "provider",
            "started_at",
            "completed_at",
            "scheduled_at",
            "url",
        ]

    def get_fields(self):
        """`type` is a Python reserved keyword."""
        fields = super().get_fields()
        type_ = fields.pop("type_")
        fields["type"] = type_
        return fields


class ScanCreateSerializer(RLSSerializer, BaseWriteSerializer):
    class Meta:
        model = Scan
        # TODO: add mutelist when implemented
        fields = ["provider", "scanner_args", "name"]

    def create(self, validated_data):
        provider = validated_data.get("provider")

        if not validated_data.get("scanner_args"):
            validated_data["scanner_args"] = provider.scanner_args
        else:
            validated_data["scanner_args"] = merge_dicts(
                provider.scanner_args, validated_data["scanner_args"]
            )

        if not validated_data.get("type"):
            validated_data["type"] = Scan.TypeChoices.MANUAL.value

        return RLSSerializer.create(self, validated_data)


class ScanUpdateSerializer(BaseWriteSerializer):
    """
    Serializer for updating the Provider model.
    Only allows "alias" and "scanner_args" fields to be updated.
    """

    class Meta:
        model = Scan
        # TODO: add mutelist when implemented
        fields = ["id", "name"]
        extra_kwargs = {
            "id": {"read_only": True},
        }
